"""Tests for the Agent: run, stream, tool calls, lifecycle, errors, retries.

Uses the deterministic mock provider so no network calls are needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from voodoo import Agent, AgentRun
from voodoo.ai.agent import AgentState
from voodoo.ai.providers import ProviderEvent, ProviderResponse, ToolCall
from voodoo.ai.providers.mock import MockProvider
from voodoo.tools import registry as tools_module
from voodoo.tools.registry import ToolRegistry, build_spec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ToolThenTextProvider(MockProvider):
    """Returns a tool-call marker on the first call, then a final answer."""

    def __init__(self, tool_marker: str, final: str = "Done"):
        super().__init__(model="test")
        self._call_count = 0
        self._tool_marker = tool_marker
        self._final = final

    async def complete(self, messages, **kwargs):
        self._call_count += 1
        if self._call_count == 1:
            return ProviderResponse(
                content=self._tool_marker,
                model=self.model,
                tokens_in=1,
                tokens_out=1,
                cost=0.0,
            )
        return ProviderResponse(
            content=self._final,
            model=self.model,
            tokens_in=1,
            tokens_out=1,
            cost=0.0,
        )

    async def stream(self, messages, **kwargs):
        self._call_count += 1
        content = self._tool_marker if self._call_count == 1 else self._final
        for word in content.split():
            yield ProviderEvent(type="text", data={"text": word + " "})
        yield ProviderEvent(
            type="done",
            data={
                "model": self.model,
                "tokens_in": 1,
                "tokens_out": 1,
                "cost": 0.0,
                "finish_reason": "stop",
            },
        )


class NativeToolCallProvider(MockProvider):
    """Returns a structured ``ToolCall`` on the first call, then a final answer."""

    def __init__(self, name: str, arguments: dict, final: str = "Done"):
        super().__init__(model="test")
        self._call_count = 0
        self._name = name
        self._arguments = arguments
        self._final = final

    async def complete(self, messages, **kwargs):
        self._call_count += 1
        if self._call_count == 1:
            return ProviderResponse(
                content="",
                model=self.model,
                tokens_in=1,
                tokens_out=1,
                cost=0.0,
                tool_calls=[
                    ToolCall(name=self._name, arguments=self._arguments, id="call_1")
                ],
            )
        return ProviderResponse(
            content=self._final,
            model=self.model,
            tokens_in=1,
            tokens_out=1,
            cost=0.0,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    """Fresh default registry per test — no leaked tool registrations."""
    fresh = ToolRegistry()
    monkeypatch.setattr(tools_module, "default_registry", fresh)
    return fresh


@pytest.fixture(autouse=True)
def _clean_mesh_handlers():
    """Clear mesh handlers between tests so they don't leak."""
    from voodoo.mesh import mesh

    mesh.event_handlers.clear()
    mesh.active_nodes.clear()
    yield
    mesh.event_handlers.clear()
    mesh.active_nodes.clear()


@pytest.fixture(autouse=True)
def _clean_telemetry():
    """Reset telemetry agent metrics between tests."""
    from voodoo.telemetry import telemetry_store

    telemetry_store.metrics["agent_runs"].clear()
    telemetry_store.metrics["tool_calls"].clear()
    yield
    telemetry_store.metrics["agent_runs"].clear()
    telemetry_store.metrics["tool_calls"].clear()


# ---------------------------------------------------------------------------
# Basic run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_agent_run_record():
    agent = Agent(model="mock:test")
    result = await agent.run("Hello")
    assert isinstance(result, AgentRun)
    assert result.model == "mock:test"
    assert result.provider == "mock"
    assert result.status == "completed"
    assert "Mock response to: Hello" in result.output
    assert result.error is None
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_run_has_token_accounting():
    agent = Agent(model="mock:test")
    result = await agent.run("hello world")
    assert result.tokens_in > 0
    assert result.tokens_out > 0
    assert result.cost == 0.0  # mock provider cost is always zero
    assert "total_ms" in result.timings
    assert result.timings["total_ms"] >= 0


@pytest.mark.asyncio
async def test_run_with_system_prompt():
    agent = Agent(model="mock:test", system_prompt="You are a pirate.")
    result = await agent.run("hello")
    assert result.status == "completed"
    assert result.output  # non-empty


@pytest.mark.asyncio
async def test_run_with_history_prepends_turns():
    # Multi-turn: prior turns are prepended before the new user message.
    agent = Agent(model="mock:test")
    seen: list[list[dict[str, Any]]] = []
    original_complete = agent.provider.complete

    async def spy_complete(messages, **kwargs):  # type: ignore[no-untyped-def]
        seen.append([dict(m) for m in messages])
        return await original_complete(messages, **kwargs)

    agent.provider.complete = spy_complete  # type: ignore[method-assign]
    history = [
        {"role": "user", "content": "My name is Ana."},
        {"role": "assistant", "content": "Hello Ana!"},
    ]
    await agent.run("What is my name?", history=history)
    assert len(seen) == 1
    msgs = seen[0]
    assert msgs[0] == history[0]
    assert msgs[1] == history[1]
    assert msgs[-1] == {"role": "user", "content": "What is my name?"}


@pytest.mark.asyncio
async def test_stream_with_history_prepends_turns():
    agent = Agent(model="mock:test")
    seen: list[list[dict[str, Any]]] = []
    original_stream = agent.provider.stream

    async def spy_stream(messages, **kwargs):  # type: ignore[no-untyped-def]
        seen.append([dict(m) for m in messages])
        async for ev in original_stream(messages, **kwargs):
            yield ev

    agent.provider.stream = spy_stream  # type: ignore[method-assign]
    history = [{"role": "user", "content": "hi"}]
    async for _ in agent.stream("again", history=history):
        pass
    assert len(seen) == 1
    assert seen[0][0] == history[0]
    assert seen[0][-1] == {"role": "user", "content": "again"}


@pytest.mark.asyncio
async def test_run_with_context():
    agent = Agent(model="mock:test")
    result = await agent.run("hello", context={"user_id": 42})
    assert result.status == "completed"
    assert result.prompt == "hello"


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_yields_text_events():
    agent = Agent(model="mock:test")
    events = []
    async for event in agent.stream("hello"):
        events.append(event)

    text_events = [e for e in events if e.type == "text"]
    assert len(text_events) > 0  # mock streams word-by-word
    completed = [e for e in events if e.type == "completed"]
    assert len(completed) == 1
    assert "Mock response to: hello" in completed[0].data["output"]


@pytest.mark.asyncio
async def test_stream_event_types_are_normalized():
    agent = Agent(model="mock:test")
    events = []
    async for event in agent.stream("test"):
        events.append(event)

    valid_types = {
        "text",
        "tool_started",
        "tool_finished",
        "thinking",
        "error",
        "completed",
    }
    for e in events:
        assert e.type in valid_types, f"unexpected event type: {e.type}"


@pytest.mark.asyncio
async def test_stream_completed_has_tokens():
    agent = Agent(model="mock:test")
    events = []
    async for event in agent.stream("hello world"):
        events.append(event)

    completed = [e for e in events if e.type == "completed"][0]
    assert completed.data["tokens_in"] > 0
    assert completed.data["tokens_out"] > 0


# ---------------------------------------------------------------------------
# Tool calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_executes_tool_call_via_marker():
    """Agent parses [TOOL: name] in the response and calls the registered tool."""
    registry = ToolRegistry()

    def greet(name: str) -> str:
        """Greet someone."""
        return f"Hello, {name}!"

    spec = build_spec(greet, name="greet")
    registry.register(spec)

    provider = ToolThenTextProvider(
        '[TOOL: greet] args: {"name": "World"}', "Greeting done"
    )
    agent = Agent(model="mock:test", tools=["greet"], registry=registry)
    agent.provider = provider

    result = await agent.run("greet the user")

    assert result.status == "completed"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "greet"
    assert result.tool_calls[0]["result"] == "Hello, World!"


@pytest.mark.asyncio
async def test_stream_executes_tool_call():
    registry = ToolRegistry()

    async def fetch_data(query: str) -> str:
        """Fetch data."""
        return f"data:{query}"

    spec = build_spec(fetch_data, name="fetch_data")
    registry.register(spec)

    provider = ToolThenTextProvider(
        '[TOOL: fetch_data] args: {"query": "test"}', "Fetch done"
    )
    agent = Agent(model="mock:test", tools=["fetch_data"], registry=registry)
    agent.provider = provider

    events = []
    async for event in agent.stream("fetch"):
        events.append(event)

    tool_started = [e for e in events if e.type == "tool_started"]
    tool_finished = [e for e in events if e.type == "tool_finished"]
    assert len(tool_started) == 1
    assert tool_started[0].data["tool"] == "fetch_data"
    assert len(tool_finished) == 1
    assert "data:test" in str(tool_finished[0].data["result"])


@pytest.mark.asyncio
async def test_tool_call_records_latency():
    registry = ToolRegistry()

    def slow_tool() -> str:
        """Slow tool."""
        return "done"

    spec = build_spec(slow_tool, name="slow_tool")
    registry.register(spec)

    provider = ToolThenTextProvider("[TOOL: slow_tool] args: {}", "Done")
    agent = Agent(model="mock:test", tools=["slow_tool"], registry=registry)
    agent.provider = provider

    result = await agent.run("run it")
    assert len(result.tool_calls) == 1
    assert "latency_ms" in result.tool_calls[0]
    assert result.tool_calls[0]["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_tool_call_error_captured():
    """If a tool raises, the error is captured in the tool_call record."""
    registry = ToolRegistry()

    def boom(x: str) -> str:
        """Always fails."""
        raise ValueError("boom")

    spec = build_spec(boom, name="boom")
    registry.register(spec)

    provider = ToolThenTextProvider('[TOOL: boom] args: {"x": "a"}', "Done")
    agent = Agent(model="mock:test", tools=["boom"], registry=registry)
    agent.provider = provider

    result = await agent.run("call it")
    assert len(result.tool_calls) == 1
    assert "error" in result.tool_calls[0]["result"]


# ---------------------------------------------------------------------------
# Native tool-call protocol
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_executes_native_tool_call():
    """Agent consumes structured ``tool_calls`` (the native protocol)."""
    registry = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    registry.register(build_spec(add, name="add"))

    provider = NativeToolCallProvider("add", {"a": 2, "b": 3}, "Sum done")
    agent = Agent(model="mock:test", tools=["add"], registry=registry)
    agent.provider = provider

    result = await agent.run("add 2 and 3")

    assert result.status == "completed"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "add"
    assert result.tool_calls[0]["result"] == 5
    assert result.output == "Sum done"


@pytest.mark.asyncio
async def test_native_tool_call_builds_structured_follow_up():
    """Native tool calls are echoed back in the provider's own format."""
    registry = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    registry.register(build_spec(add, name="add"))

    provider = NativeToolCallProvider("add", {"a": 1, "b": 1}, "Two")
    agent = Agent(model="mock:test", tools=["add"], registry=registry)
    agent.provider = provider

    captured: list[list[dict]] = []
    original_complete = agent.provider.complete

    async def spy(messages, **kwargs):
        captured.append(messages)
        return await original_complete(messages, **kwargs)

    agent.provider.complete = spy  # type: ignore[method-assign]

    await agent.run("add 1 and 1")

    assert len(captured) == 2
    assistant = [m for m in captured[1] if m["role"] == "assistant"][0]
    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert assistant["tool_calls"][0]["function"]["name"] == "add"
    tool_msg = [m for m in captured[1] if m["role"] == "tool"][0]
    assert tool_msg["tool_call_id"] == "call_1"
    assert tool_msg["content"] == "2"


@pytest.mark.asyncio
async def test_multiple_tool_calls_in_one_run():
    """Agent can chain multiple tool calls before reaching a final answer."""
    registry = ToolRegistry()

    def step1() -> str:
        """Step 1."""
        return "result1"

    def step2() -> str:
        """Step 2."""
        return "result2"

    registry.register(build_spec(step1, name="step1"))
    registry.register(build_spec(step2, name="step2"))

    # First call returns step1 marker, second returns step2 marker, third returns final
    class MultiStepProvider(MockProvider):
        def __init__(self):
            super().__init__(model="test")
            self._call_count = 0

        async def complete(self, messages, **kwargs):
            self._call_count += 1
            if self._call_count == 1:
                content = "[TOOL: step1] args: {}"
            elif self._call_count == 2:
                content = "[TOOL: step2] args: {}"
            else:
                content = "All done"
            return ProviderResponse(
                content=content,
                model=self.model,
                tokens_in=1,
                tokens_out=1,
                cost=0.0,
            )

    agent = Agent(model="mock:test", tools=["step1", "step2"], registry=registry)
    agent.provider = MultiStepProvider()

    result = await agent.run("run steps")
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0]["name"] == "step1"
    assert result.tool_calls[1]["name"] == "step2"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_agent_lifecycle_created_to_configured():
    agent = Agent(model="mock:test")
    assert agent.state == AgentState.configured


@pytest.mark.asyncio
async def test_agent_lifecycle_transitions_to_completed():
    agent = Agent(model="mock:test")
    assert agent.state == AgentState.configured
    await agent.run("test")
    assert agent.state == AgentState.completed


@pytest.mark.asyncio
async def test_agent_lifecycle_error_on_provider_failure():
    agent = Agent(model="mock:test")
    agent.provider = AsyncMock()
    agent.provider.complete = AsyncMock(side_effect=Exception("provider down"))
    agent.provider.name = "mock"

    result = await agent.run("test")
    assert result.status == "failed"
    assert result.error is not None
    assert "provider down" in result.error


@pytest.mark.asyncio
async def test_agent_lifecycle_error_on_stream_failure():
    agent = Agent(model="mock:test")
    agent.provider.name = "mock"

    async def _bad_stream(messages, **kwargs):
        yield ProviderEvent(type="error", data={"error": "stream broke"})

    agent.provider.stream = _bad_stream

    events = []
    async for event in agent.stream("test"):
        events.append(event)

    error_events = [e for e in events if e.type == "error"]
    assert len(error_events) >= 1
    assert agent.state == AgentState.failed


# ---------------------------------------------------------------------------
# Telemetry correlation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_records_telemetry():
    from voodoo.telemetry import telemetry_store

    agent = Agent(model="mock:test")
    await agent.run("hello")
    summary = telemetry_store.get_summary()
    assert summary["agent_runs"] >= 1


@pytest.mark.asyncio
async def test_tool_call_records_telemetry():
    from voodoo.telemetry import telemetry_store

    registry = ToolRegistry()

    def my_tool() -> str:
        """Tool."""
        return "ok"

    spec = build_spec(my_tool, name="my_tool")
    registry.register(spec)

    provider = ToolThenTextProvider("[TOOL: my_tool] args: {}", "Done")
    agent = Agent(model="mock:test", tools=["my_tool"], registry=registry)
    agent.provider = provider

    await agent.run("run it")

    assert len(telemetry_store.metrics["tool_calls"]) >= 1
    assert telemetry_store.metrics["tool_calls"][-1]["tool"] == "my_tool"


@pytest.mark.asyncio
async def test_agent_run_correlates_with_trace_id():
    from voodoo.telemetry import trace_id_var

    trace_id_var.set("test-trace-123")
    try:
        agent = Agent(model="mock:test")
        result = await agent.run("hello")
        assert result.trace_id == "test-trace-123"
    finally:
        trace_id_var.set(None)


# ---------------------------------------------------------------------------
# Mesh events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_publishes_mesh_events():
    from voodoo.mesh import mesh

    received = []

    @mesh.on("agent.started")
    async def on_started(payload):
        received.append(("agent.started", payload))

    @mesh.on("agent.completed")
    async def on_completed(payload):
        received.append(("agent.completed", payload))

    agent = Agent(model="mock:test")
    await agent.run("hello")

    event_names = [name for name, _ in received]
    assert "agent.started" in event_names
    assert "agent.completed" in event_names


@pytest.mark.asyncio
async def test_run_publishes_tool_mesh_events():
    from voodoo.mesh import mesh

    received = []

    @mesh.on("agent.tool.started")
    async def on_tool_started(payload):
        received.append(("agent.tool.started", payload))

    @mesh.on("agent.tool.completed")
    async def on_tool_completed(payload):
        received.append(("agent.tool.completed", payload))

    registry = ToolRegistry()

    def my_tool() -> str:
        """Tool."""
        return "ok"

    spec = build_spec(my_tool, name="my_tool")
    registry.register(spec)

    provider = ToolThenTextProvider("[TOOL: my_tool] args: {}", "Done")
    agent = Agent(model="mock:test", tools=["my_tool"], registry=registry)
    agent.provider = provider

    await agent.run("run it")

    event_names = [name for name, _ in received]
    assert "agent.tool.started" in event_names
    assert "agent.tool.completed" in event_names


@pytest.mark.asyncio
async def test_run_publishes_failed_mesh_event():
    from voodoo.mesh import mesh

    received = []

    @mesh.on("agent.failed")
    async def on_failed(payload):
        received.append(("agent.failed", payload))

    agent = Agent(model="mock:test")
    agent.provider = AsyncMock()
    agent.provider.complete = AsyncMock(side_effect=Exception("kaboom"))
    agent.provider.name = "mock"

    await agent.run("test")
    assert any(name == "agent.failed" for name, _ in received)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def test_agent_exported_from_voodoo():
    from voodoo import Agent as ExportedAgent

    assert ExportedAgent is Agent


def test_agent_run_exported_from_voodoo():
    from voodoo import AgentRun as ExportedAgentRun

    assert ExportedAgentRun is AgentRun


def test_agent_reexport_from_voodoo_agent_module():
    from voodoo.agent import Agent as ReExportedAgent

    assert ReExportedAgent is Agent
