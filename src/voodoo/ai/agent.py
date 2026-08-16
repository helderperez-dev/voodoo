"""Agent — provider-driven execution loop with tool calling.

The Agent turns a prompt into a final answer by iterating:

    prompt → provider → tool calls (via registry) → final

``run()`` returns a full :class:`AgentRun` record with token/cost accounting;
``stream()`` yields normalized :class:`AgentEvent` objects so the UI can react
to agent activity in real time. Lifecycle states (created → configured →
running → tool_call ⇄ thinking → completed | error → retry/failed) are
captured for telemetry and surfaced through mesh events (S7-2).

The ``context`` parameter is an explicit, opaque dict passed to every tool
call; it is neither memory nor a database — keep the concepts separate.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.ai.providers import LLMProvider, Message, get_provider
from voodoo.tools.registry import ToolRegistry, default_registry

__all__ = ["Agent", "AgentRun", "AgentEvent"]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class AgentState(StrEnum):
    created = "created"
    configured = "configured"
    running = "running"
    tool_call = "tool_call"
    thinking = "thinking"
    completed = "completed"
    error = "error"
    retry = "retry"
    failed = "failed"


# ---------------------------------------------------------------------------
# Records & events
# ---------------------------------------------------------------------------


@dataclass
class AgentRun:
    """Full run record with token/cost accounting."""

    run_id: str
    model: str
    provider: str
    prompt: str
    output: str
    timings: dict[str, float] = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    status: str = "completed"
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    trace_id: str | None = None


@dataclass
class AgentEvent:
    """Normalized streaming event.

    ``type`` is one of: ``text``, ``tool_started``, ``tool_finished``,
    ``thinking``, ``error``, ``completed``.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class Agent:
    """Agent with provider-driven execution and tool calling.

    Parameters
    ----------
    model:
        ``"provider:model"`` string resolved via :func:`get_provider`.
    tools:
        List of :class:`ToolSpec` objects or tool names registered in the
        chosen registry. ``None`` means "no tools available".
    system_prompt:
        Optional system message prepended to the message list.
    registry:
        Tool registry used for tool lookup; defaults to the global registry.
    max_iterations:
        Maximum tool-call iterations before forcing a final answer.
    """

    def __init__(
        self,
        model: str = "mock:test",
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
        registry: ToolRegistry | None = None,
        max_iterations: int = 10,
        **provider_kwargs: Any,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.registry = registry or default_registry
        self.max_iterations = max_iterations
        self.state: AgentState = AgentState.created
        self.provider: LLMProvider = get_provider(model, **provider_kwargs)

        # Resolve tool specs/names into a list of names for tool calling.
        self._tool_names: list[str] = []
        if tools:
            for t in tools:
                if isinstance(t, str):
                    self._tool_names.append(t)
                elif hasattr(t, "name"):
                    self._tool_names.append(t.name)
                elif hasattr(t, "__tool_spec__"):
                    self._tool_names.append(t.__tool_spec__.name)

        self.state = AgentState.configured

    # -- helpers -----------------------------------------------------------

    def _build_messages(
        self, prompt: str, context: dict | None = None
    ) -> list[Message]:
        messages: list[Message] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Context: {context}",
                }
            )
        messages.append({"role": "user", "content": prompt})
        return messages

    def _tools_for_provider(self) -> list[dict[str, Any]] | None:
        if not self._tool_names:
            return None
        specs = []
        for name in self._tool_names:
            spec = self.registry.get(name)
            if spec:
                specs.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "input_schema": spec.input_schema,
                    }
                )
        return specs or None

    async def _execute_tool_call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a registered tool, returning its result or an error dict."""
        try:
            result = await self.registry.call(name, **arguments)
            return result
        except Exception as e:  # noqa: BLE001 — capture for telemetry
            return {"error": str(e)}

    # -- run ---------------------------------------------------------------

    async def run(self, prompt: str, context: dict | None = None) -> AgentRun:
        """Execute prompt → provider → tool calls → final; return AgentRun."""
        run_id = str(uuid.uuid4())
        from voodoo.telemetry import telemetry_store

        trace_id = (
            telemetry_store.trace_id_var.get()
            if hasattr(telemetry_store, "trace_id_var")
            else None
        )
        started = time.time()
        self.state = AgentState.running

        messages = self._build_messages(prompt, context)
        tool_calls: list[dict[str, Any]] = []
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        output = ""
        error: str | None = None
        iterations = 0

        await self._broadcast("agent.started", {"run_id": run_id, "model": self.model})

        try:
            while iterations <= self.max_iterations:
                self.state = AgentState.running
                response = await self.provider.complete(
                    messages, tools=self._tools_for_provider()
                )
                tokens_in += response.tokens_in
                tokens_out += response.tokens_out
                cost += response.cost

                # Check if the response requests a tool call.
                tool_request = self._extract_tool_request(response)
                if tool_request and iterations < self.max_iterations:
                    self.state = AgentState.tool_call
                    tool_name = tool_request["name"]
                    tool_args = tool_request.get("arguments", {})

                    await self._broadcast(
                        "agent.tool.started",
                        {"run_id": run_id, "tool": tool_name, "arguments": tool_args},
                    )

                    tool_start = time.time()
                    tool_result = await self._execute_tool_call(tool_name, tool_args)
                    tool_latency = (time.time() - tool_start) * 1000

                    tool_calls.append(
                        {
                            "name": tool_name,
                            "arguments": tool_args,
                            "result": tool_result,
                            "latency_ms": tool_latency,
                        }
                    )
                    telemetry_store.record_tool_call(
                        tool_name,
                        tool_latency,
                        isinstance(tool_result, dict) and "error" in tool_result,
                    )

                    await self._broadcast(
                        "agent.tool.completed",
                        {
                            "run_id": run_id,
                            "tool": tool_name,
                            "latency_ms": tool_latency,
                        },
                    )

                    self.state = AgentState.thinking
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append(
                        {
                            "role": "tool",
                            "content": str(tool_result),
                            "name": tool_name,
                        }
                    )
                    iterations += 1
                    continue
                else:
                    # Final answer
                    output = response.content
                    break

        except Exception as e:  # noqa: BLE001
            self.state = AgentState.error
            error = str(e)
            await self._broadcast("agent.failed", {"run_id": run_id, "error": error})
            self.state = AgentState.failed
        else:
            self.state = AgentState.completed

        completed_at = time.time()
        run_record = AgentRun(
            run_id=run_id,
            model=self.model,
            provider=self.provider.name,
            prompt=prompt,
            output=output,
            timings={
                "total_ms": (completed_at - started) * 1000,
                "iterations": iterations,
            },
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            tool_calls=tool_calls,
            status=self.state.value,
            error=error,
            started_at=started,
            completed_at=completed_at,
            trace_id=trace_id,
        )

        telemetry_store.record_agent_run(run_record)
        await self._broadcast(
            "agent.completed",
            {
                "run_id": run_id,
                "status": run_record.status,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost": cost,
            },
        )
        return run_record

    # -- stream ------------------------------------------------------------

    async def stream(
        self, prompt: str, context: dict | None = None
    ) -> AsyncIterator[AgentEvent]:
        """Yield normalized events: text, tool_started, tool_finished, thinking, error, completed."""
        run_id = str(uuid.uuid4())
        from voodoo.telemetry import telemetry_store

        trace_id = (
            telemetry_store.trace_id_var.get()
            if hasattr(telemetry_store, "trace_id_var")
            else None
        )
        started = time.time()
        self.state = AgentState.running

        messages = self._build_messages(prompt, context)
        tool_calls: list[dict[str, Any]] = []
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        output = ""
        error: str | None = None
        iterations = 0

        await self._broadcast("agent.started", {"run_id": run_id, "model": self.model})

        try:
            while iterations <= self.max_iterations:
                self.state = AgentState.running
                accumulated_text = ""
                async for event in self.provider.stream(
                    messages, tools=self._tools_for_provider()
                ):
                    if event.type == "text":
                        accumulated_text += event.data.get("text", "")
                        yield AgentEvent(type="text", data=event.data)
                    elif event.type == "done":
                        tokens_in += event.data.get("tokens_in", 0)
                        tokens_out += event.data.get("tokens_out", 0)
                        cost += event.data.get("cost", 0.0)
                    elif event.type == "error":
                        raise Exception(event.data.get("error", "Provider error"))

                # Check if a tool call is needed (mock doesn't emit tool_call,
                # so we check based on the accumulated text for a special marker).
                tool_request = self._extract_tool_request_from_stream(accumulated_text)

                if tool_request and iterations < self.max_iterations:
                    self.state = AgentState.tool_call
                    tool_name = tool_request["name"]
                    tool_args = tool_request.get("arguments", {})

                    yield AgentEvent(
                        type="tool_started",
                        data={"tool": tool_name, "arguments": tool_args},
                    )
                    await self._broadcast(
                        "agent.tool.started",
                        {"run_id": run_id, "tool": tool_name, "arguments": tool_args},
                    )

                    tool_start = time.time()
                    tool_result = await self._execute_tool_call(tool_name, tool_args)
                    tool_latency = (time.time() - tool_start) * 1000

                    tool_calls.append(
                        {
                            "name": tool_name,
                            "arguments": tool_args,
                            "result": tool_result,
                            "latency_ms": tool_latency,
                        }
                    )
                    telemetry_store.record_tool_call(
                        tool_name,
                        tool_latency,
                        isinstance(tool_result, dict) and "error" in tool_result,
                    )

                    yield AgentEvent(
                        type="tool_finished",
                        data={
                            "tool": tool_name,
                            "result": tool_result,
                            "latency_ms": tool_latency,
                        },
                    )
                    await self._broadcast(
                        "agent.tool.completed",
                        {
                            "run_id": run_id,
                            "tool": tool_name,
                            "latency_ms": tool_latency,
                        },
                    )

                    self.state = AgentState.thinking
                    yield AgentEvent(type="thinking", data={"tool": tool_name})

                    messages.append({"role": "assistant", "content": accumulated_text})
                    messages.append(
                        {"role": "tool", "content": str(tool_result), "name": tool_name}
                    )
                    iterations += 1
                    continue
                else:
                    output = accumulated_text
                    break

        except Exception as e:  # noqa: BLE001
            self.state = AgentState.error
            error = str(e)
            yield AgentEvent(type="error", data={"error": error})
            await self._broadcast("agent.failed", {"run_id": run_id, "error": error})
            self.state = AgentState.failed
        else:
            self.state = AgentState.completed

        completed_at = time.time()
        run_record = AgentRun(
            run_id=run_id,
            model=self.model,
            provider=self.provider.name,
            prompt=prompt,
            output=output,
            timings={
                "total_ms": (completed_at - started) * 1000,
                "iterations": iterations,
            },
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            tool_calls=tool_calls,
            status=self.state.value,
            error=error,
            started_at=started,
            completed_at=completed_at,
            trace_id=trace_id,
        )

        telemetry_store.record_agent_run(run_record)
        await self._broadcast(
            "agent.completed",
            {
                "run_id": run_id,
                "status": run_record.status,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost": cost,
            },
        )
        yield AgentEvent(
            type="completed",
            data={
                "run_id": run_id,
                "output": output,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost": cost,
                "status": run_record.status,
            },
        )

    # -- tool request extraction ------------------------------------------

    def _extract_tool_request(self, response: Any) -> dict[str, Any] | None:
        """Extract a tool call request from a provider response.

        The mock provider returns plain text; we support a simple convention:
        if the response content contains ``[TOOL: tool_name]`` (optionally with
        JSON arguments after ``args:``), we parse it as a tool request.
        """
        content = getattr(response, "content", "")
        return self._parse_tool_marker(content)

    def _extract_tool_request_from_stream(self, content: str) -> dict[str, Any] | None:
        return self._parse_tool_marker(content)

    @staticmethod
    def _parse_tool_marker(content: str) -> dict[str, Any] | None:
        import json

        marker = "[TOOL:"
        if marker not in content:
            return None
        try:
            start = content.index(marker) + len(marker)
            end = content.index("]", start)
            tool_name = content[start:end].strip()
            args: dict[str, Any] = {}
            # Look for args: after the tool marker
            args_marker = "args:"
            if args_marker in content[end:]:
                args_start = content.index(args_marker, end) + len(args_marker)
                # Try to parse JSON until end of content or next marker
                remaining = content[args_start:].strip()
                # Find end of JSON (try to parse incrementally)
                try:
                    args = json.loads(remaining)
                except json.JSONDecodeError:
                    # Try to find a JSON object
                    brace_start = remaining.find("{")
                    if brace_start >= 0:
                        brace_end = remaining.rfind("}")
                        if brace_end > brace_start:
                            args = json.loads(remaining[brace_start : brace_end + 1])
            return {"name": tool_name, "arguments": args}
        except (ValueError, json.JSONDecodeError):
            return None

    # -- mesh broadcasting -------------------------------------------------

    async def _broadcast(self, event: str, payload: dict[str, Any]) -> None:
        """Publish a namespaced mesh event (best-effort, never breaks the run)."""
        try:
            from voodoo.mesh import mesh

            await mesh.broadcast(event, payload)
        except Exception:  # noqa: BLE001 — mesh is optional in tests
            pass
