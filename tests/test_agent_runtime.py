"""Tests for Agent × Runtime integration.

Agent tool calls flow through the runtime authorization path:
Agent → Intent → capability check → Tool → Effect → Mesh.
"""

from __future__ import annotations

from voodoo.primitives.capability import Capability as Cap
from voodoo.primitives.intent import Intent
from voodoo.runtime import (
    ComputeResult,
    ExecutionContext,
    ExecutionEngine,
    ExecutionStatus,
    Task,
    TaskStatus,
    use_context,
)


def _make_agent_with_gated_tool(granted: list[str] | None):
    from voodoo.ai.agent import Agent
    from voodoo.ai.tools.registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()

    def send_email(to: str) -> str:
        return f"sent to {to}"

    spec = ToolSpec(
        name="send_email",
        description="Send an email",
        input_schema={"type": "object"},
        output_schema={"type": "string"},
        permissions=["email.send"],
        func=send_email,
    )
    registry.register(spec)
    agent = Agent(model="mock:test", registry=registry, capabilities=granted)
    return agent, registry


class TestAgentRuntimeIntegration:
    async def test_tool_denied_without_capability(self):
        agent, _ = _make_agent_with_gated_tool(granted=None)
        result = await agent._execute_tool_call("send_email", {"to": "a@b.c"})
        assert isinstance(result, dict)
        assert "CapabilityDenied" in result["error"]

    async def test_tool_allowed_with_capability(self):
        agent, _ = _make_agent_with_gated_tool(granted=["email.send"])
        result = await agent._execute_tool_call("send_email", {"to": "a@b.c"})
        assert result == "sent to a@b.c"

    async def test_context_capability_grants_tool_and_records_effect(self):
        agent, _ = _make_agent_with_gated_tool(granted=None)
        ctx = ExecutionContext()
        ctx.grant(Cap(name="email.send"))

        async with use_context(ctx):
            result = await agent._execute_tool_call("send_email", {"to": "a@b.c"})
        assert result == "sent to a@b.c"
        assert len(ctx.effects) == 1
        assert ctx.effects[0].name == "tool.send_email"
        assert ctx.effects[0].capability_name == "email.send"
        assert ctx.effects[0].succeeded

    async def test_denied_tool_records_failed_effect(self):
        agent, _ = _make_agent_with_gated_tool(granted=None)
        ctx = ExecutionContext()
        async with use_context(ctx):
            await agent._execute_tool_call("send_email", {"to": "a@b.c"})
        assert len(ctx.effects) == 1
        assert ctx.effects[0].failed
        assert "capability denied" in ctx.effects[0].error

    async def test_agent_run_inside_engine_records_effects_on_execution(self):
        engine = ExecutionEngine()
        agent, _ = _make_agent_with_gated_tool(granted=["email.send"])

        async def compute(ctx: ExecutionContext) -> ComputeResult:
            await agent._execute_tool_call("send_email", {"to": "x@y.z"})
            return ComputeResult(value="done")

        ex = await engine.execute(Intent(name="notify"), compute)
        assert ex.status is ExecutionStatus.COMPLETED
        assert [e.name for e in ex.effects] == ["tool.send_email"]

    async def test_task_with_agent_compute(self):
        from voodoo.ai.agent import Agent

        agent = Agent(model="mock:test")
        t = Task(name="ask", description="hello", agent=agent)
        ex = await t.run()
        assert t.status is TaskStatus.COMPLETED
        assert isinstance(ex.result, str)

    async def test_workflow_with_agent_task(self):
        from voodoo.ai.agent import Agent
        from voodoo.runtime import Workflow, WorkflowStrategy

        agent = Agent(model="mock:test")
        t = Task(name="answer", description="what is 2+2", agent=agent)
        wf = Workflow(tasks=[t], strategy=WorkflowStrategy.SEQUENTIAL)
        run = await wf.run()
        assert run.status == "completed"
        assert run.task_statuses["answer"] == "completed"
