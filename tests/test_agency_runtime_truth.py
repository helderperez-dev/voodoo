from __future__ import annotations

from types import SimpleNamespace

import pytest

from voodoo.agents.registry import InMemoryAgentRegistry
from voodoo.ai.agent import Agent
from voodoo.ai.providers import ProviderResponse, ToolCall
from voodoo.ai.providers.mock import MockProvider
from voodoo.memory.interfaces import InMemoryMemoryStore, MemoryLayer
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.errors import AgentExecutionError
from voodoo.runtime.task import Task
from voodoo.tools.registry import ToolRegistry, build_spec


class FailingProvider(MockProvider):
    async def complete(self, messages, **kwargs):
        raise RuntimeError("provider exploded")


class ToolFailureThenTextProvider(MockProvider):
    def __init__(self):
        super().__init__(model="test")
        self.calls = 0

    async def complete(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                content="",
                model=self.model,
                tool_calls=[ToolCall(name="boom", arguments={}, id="call-1")],
            )
        return ProviderResponse(content="recovered", model=self.model)


def _failing_agent(*, engine=None, registry=None, memory=None, agent_id="agent-a"):
    agent = Agent(
        model="mock:test",
        engine=engine,
        agent_registry=registry,
        memory=memory,
        agent_id=agent_id,
    )
    agent.provider = FailingProvider(model="test")
    return agent


@pytest.mark.asyncio
async def test_engine_backed_agent_failure_fails_canonical_execution_and_lineage():
    engine = ExecutionEngine()
    registry = InMemoryAgentRegistry()
    memory = InMemoryMemoryStore()
    agent = _failing_agent(
        engine=engine,
        registry=registry,
        memory=memory,
        agent_id="agent-a",
    )

    with pytest.raises(AgentExecutionError):
        await agent.run("do work")

    executions = engine.recent()
    assert len(executions) == 1
    execution = executions[0]
    assert execution.failed
    assert "provider exploded" in (execution.error or "")

    runs = await registry.get_runs("agent-a")
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].execution_id == execution.id
    assert runs[0].trace_id == execution.trace_id

    entries = memory.list_entries(entity_id="agent-a", layers=[MemoryLayer.EPISODIC])
    assert len(entries) == 1
    assert entries[0].entity_id == "agent-a"
    assert entries[0].source_execution_id == execution.id
    assert entries[0].metadata["execution_id"] == execution.id
    assert entries[0].metadata["trace_id"] == execution.trace_id


@pytest.mark.asyncio
async def test_standalone_agent_failure_remains_backward_compatible():
    agent = _failing_agent()
    run = await agent.run("do work")
    assert run.status == "failed"
    assert run.execution_id is None
    assert "provider exploded" in (run.error or "")


@pytest.mark.asyncio
async def test_two_agents_write_private_episodic_memory():
    memory = InMemoryMemoryStore()
    first = Agent(model="mock:test", memory=memory, agent_id="agent-a")
    second = Agent(model="mock:test", memory=memory, agent_id="agent-b")

    await first.run("alpha memory")
    await second.run("beta memory")

    a_entries = memory.list_entries(entity_id="agent-a")
    b_entries = memory.list_entries(entity_id="agent-b")
    assert len(a_entries) == 1
    assert len(b_entries) == 1
    assert "alpha memory" in a_entries[0].content
    assert "beta memory" in b_entries[0].content


@pytest.mark.asyncio
async def test_failed_tool_is_failed_child_execution_while_agent_can_recover():
    engine = ExecutionEngine()
    tools = ToolRegistry()

    def boom() -> str:
        raise ValueError("tool exploded")

    tools.register(build_spec(boom, name="boom"))
    agent = Agent(model="mock:test", engine=engine, tools=["boom"], registry=tools)
    agent.provider = ToolFailureThenTextProvider()

    run = await agent.run("try the tool")
    assert run.status == "completed"
    assert run.output == "recovered"

    executions = engine.recent()
    parent = next(item for item in executions if item.parent_execution_id is None)
    child = next(item for item in executions if item.parent_execution_id == parent.id)
    assert parent.succeeded
    assert child.failed
    assert "tool exploded" in (child.error or "")


@pytest.mark.asyncio
async def test_task_agent_receives_actual_upstream_results():
    captured: dict[str, object] = {}

    class CaptureAgent:
        model = "capture:test"

        async def run(self, prompt, context=None):
            captured["prompt"] = prompt
            captured["context"] = context
            return SimpleNamespace(
                output="ok",
                cost=0.0,
                tokens_in=0,
                tokens_out=0,
                timings={},
            )

    upstream = {"first": {"value": 42}}
    task = Task(name="second", description="Use prior result", agent=CaptureAgent())
    execution = await task.run(engine=ExecutionEngine(), results=upstream)

    assert execution.succeeded
    assert "Upstream results" in str(captured["prompt"])
    assert "first" in str(captured["prompt"])
    context = captured["context"]
    assert isinstance(context, dict)
    assert context["upstream"] == upstream
