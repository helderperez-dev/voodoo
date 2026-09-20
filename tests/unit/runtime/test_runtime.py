"""Tests for the Voodoo unified runtime.

Covers the spec's critical invariants (Section 62):
  1. unauthorized effects cannot execute
  2. constraints are enforced
  3. execution context propagates
  4. parent/child executions are traceable
  5. state changes are observable
  6. errors retain execution identity
  7. cancellation propagates
  8. retries respect limits
  9. resource accounting is consistent
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel as PydBaseModel

from voodoo.primitives import Capability, Constraint, Effect, Resource, State
from voodoo.primitives.intent import IntentStatus
from voodoo.runtime import (
    ComputeResult,
    ConstraintEnforcer,
    Decision,
    ExecutionContext,
    ExecutionEngine,
    ExecutionGraph,
    ExecutionStatus,
    ResourceAccountant,
    Task,
    TaskStatus,
    Workflow,
    WorkflowStrategy,
    current_context,
)
from voodoo.runtime import (
    Intent as RTIntent,
)
from voodoo.runtime.capability import CapabilityResolver, Resolution
from voodoo.runtime.errors import (
    ApprovalRequired,
    CapabilityDenied,
    ConstraintViolation,
    ExecutionCancelled,
    ExecutionError,
    ResourceExceeded,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Engine — fresh engine per test to avoid cross-test state leakage
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> ExecutionEngine:
    return ExecutionEngine()


# ---------------------------------------------------------------------------
# Execution Context
# ---------------------------------------------------------------------------


class TestExecutionContext:
    def test_defaults(self):
        ctx = ExecutionContext()
        assert ctx.execution_id
        assert ctx.trace_id
        assert ctx.actor == "system"
        assert ctx.cancelled is False

    def test_child_inherits_trace_and_records_parent(self):
        parent = ExecutionContext(actor="agent-a")
        child = parent.child(actor="agent-b")
        assert child.trace_id == parent.trace_id
        assert child.parent_execution_id == parent.execution_id
        assert child.actor == "agent-b"

    def test_grant_and_check_capability(self):
        ctx = ExecutionContext()
        ctx.grant(Capability(name="db.read", scope="customer:1"))
        assert ctx.has_capability("db.read") is True
        assert ctx.has_capability("db.read", scope="customer:1") is True
        assert ctx.has_capability("db.write") is False

    def test_revoked_capability_not_held(self):
        ctx = ExecutionContext()
        cap = Capability(name="email.send")
        ctx.grant(cap)
        assert ctx.has_capability("email.send") is True
        cap.revoke()
        assert ctx.has_capability("email.send") is False

    def test_deadline_expiry(self):
        ctx = ExecutionContext().with_deadline(0.01)
        assert ctx.deadline_expired is False
        ctx.deadline = datetime.now(UTC) - timedelta(seconds=1)
        assert ctx.deadline_expired is True

    def test_cancel(self):
        ctx = ExecutionContext()
        ctx.cancel()
        assert ctx.cancelled is True

    @pytest.mark.asyncio
    async def test_context_propagation_inside_compute(self):
        seen: list[ExecutionContext | None] = []

        async def compute(ctx: ExecutionContext) -> ComputeResult:
            seen.append(current_context())
            return ComputeResult(value=1)

        eng = ExecutionEngine()
        await eng.execute(RTIntent(name="t"), compute)
        assert seen[0] is not None
        assert seen[0].intent is not None
        assert seen[0].intent.name == "t"


# ---------------------------------------------------------------------------
# Capability resolution
# ---------------------------------------------------------------------------


class TestCapabilityResolver:
    def test_allowed_when_registered(self):
        r = CapabilityResolver()
        r.register(Capability(name="db.read"))
        assert r.resolve("db.read") is Resolution.ALLOWED

    def test_denied_when_missing(self):
        r = CapabilityResolver()
        assert r.resolve("db.write") is Resolution.DENIED

    def test_denied_when_revoked(self):
        r = CapabilityResolver()
        cap = Capability(name="db.read")
        r.register(cap)
        cap.revoke()
        assert r.resolve("db.read") is Resolution.DENIED

    def test_scope_mismatch_denied(self):
        r = CapabilityResolver()
        r.register(Capability(name="db.read", scope="customer:1"))
        assert r.resolve("db.read", scope="customer:2") is Resolution.DENIED
        assert r.resolve("db.read", scope="customer:1") is Resolution.ALLOWED

    def test_context_grant_takes_precedence(self):
        r = CapabilityResolver()
        ctx = ExecutionContext()
        ctx.grant(Capability(name="db.read"))
        assert r.resolve("db.read", context=ctx) is Resolution.ALLOWED

    def test_authorize_raises_on_denial(self):
        r = CapabilityResolver()
        with pytest.raises(CapabilityDenied):
            r.authorize("db.write", execution_id="ex1")

    def test_authorize_raises_on_approval(self):
        r = CapabilityResolver()
        r.register(Capability(name="deploy.rollback"))
        r.require_approval("deploy.rollback")
        with pytest.raises(ApprovalRequired):
            r.authorize("deploy.rollback")


# ---------------------------------------------------------------------------
# Constraint enforcement & resource accounting
# ---------------------------------------------------------------------------


class TestConstraintEnforcer:
    def test_continue_when_no_violation(self):
        e = ConstraintEnforcer()
        ctx = ExecutionContext()
        assert e.evaluate(ctx, cost=0.01) is Decision.CONTINUE

    def test_fail_on_cost_violation(self):
        e = ConstraintEnforcer()
        ctx = ExecutionContext()
        ctx.constrain(Constraint.cost(maximum=0.05))
        assert e.evaluate(ctx, cost=0.10) is Decision.FAIL

    def test_stop_on_deadline_expired(self):
        e = ConstraintEnforcer()
        ctx = ExecutionContext()
        ctx.deadline = datetime.now(UTC) - timedelta(seconds=1)
        assert e.evaluate(ctx) is Decision.STOP

    def test_stop_on_cancelled(self):
        e = ConstraintEnforcer()
        ctx = ExecutionContext()
        ctx.cancel()
        assert e.evaluate(ctx) is Decision.STOP

    def test_request_approval_constraint(self):
        e = ConstraintEnforcer()
        ctx = ExecutionContext()
        ctx.constrain(Constraint.approval_required())
        assert e.evaluate(ctx) is Decision.REQUEST_APPROVAL

    def test_enforce_raises_constraint_violation(self):
        e = ConstraintEnforcer()
        ctx = ExecutionContext()
        ctx.constrain(Constraint.cost(maximum=0.05))
        with pytest.raises(ConstraintViolation):
            e.enforce(ctx, cost=0.10, execution_id="ex1")


class TestResourceAccountant:
    def test_accumulates(self):
        a = ResourceAccountant(budget=Resource(cost=1.0))
        a.account(Resource(cost=0.3))
        a.account(Resource(cost=0.4))
        assert a.consumed.cost == pytest.approx(0.7)

    def test_raises_on_budget_exceeded(self):
        a = ResourceAccountant(budget=Resource(cost=0.5))
        with pytest.raises(ResourceExceeded):
            a.account(Resource(cost=0.6), execution_id="ex1")

    def test_remaining(self):
        a = ResourceAccountant(budget=Resource(cost=1.0, tokens=1000))
        a.account(Resource(cost=0.3, tokens=200))
        rem = a.remaining()
        assert rem.cost == pytest.approx(0.7)
        assert rem.tokens == 800


# ---------------------------------------------------------------------------
# Execution engine — end-to-end
# ---------------------------------------------------------------------------


class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_happy_path(self, engine: ExecutionEngine):
        async def compute(ctx):
            return ComputeResult(
                value={"ok": True},
                effects=[Effect(name="lead.created")],
                resources=Resource(cost=0.01, tokens=10),
            )

        ex = await engine.execute(
            RTIntent(name="qualify", params={"id": 1}).require("crm.write"),
            compute,
            capabilities=["crm.write"],
        )
        assert ex.status is ExecutionStatus.COMPLETED
        assert ex.result == {"ok": True}
        assert len(ex.effects) == 1
        assert ex.cost == pytest.approx(0.01)
        assert ex.intent.status == IntentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_unauthorized_effect_cannot_execute(self, engine: ExecutionEngine):
        async def compute(ctx):
            return ComputeResult(value=1)

        with pytest.raises(CapabilityDenied):
            await engine.execute(
                RTIntent(name="refund").require("payment.execute"),
                compute,
            )

    @pytest.mark.asyncio
    async def test_constraint_enforced_post_compute(self, engine: ExecutionEngine):
        async def compute(ctx):
            return ComputeResult(value=1, resources=Resource(cost=0.5))

        with pytest.raises(ConstraintViolation):
            await engine.execute(
                RTIntent(name="cheap").constrain(Constraint.cost(maximum=0.1)),
                compute,
            )

    @pytest.mark.asyncio
    async def test_structured_output_validation(self, engine: ExecutionEngine):
        class Result(PydBaseModel):
            summary: str
            confidence: float

        async def compute(ctx):
            return ComputeResult(
                value={"summary": "ok", "confidence": 0.9},
                output_type=Result,
            )

        ex = await engine.execute(RTIntent(name="analyze"), compute, output_type=Result)
        assert isinstance(ex.result, Result)
        assert ex.result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_validation_failure_is_structured(self, engine: ExecutionEngine):
        class Result(PydBaseModel):
            summary: str

        async def compute(ctx):
            return ComputeResult(value={"wrong_field": 1}, output_type=Result)

        with pytest.raises(ValidationError):
            await engine.execute(RTIntent(name="analyze"), compute, output_type=Result)

    @pytest.mark.asyncio
    async def test_state_change_recorded(self, engine: ExecutionEngine):
        st = State(kind="lead", data={"name": "Ada"})

        async def compute(ctx):
            return ComputeResult(value=1, states=[st])

        ex = await engine.execute(RTIntent(name="create_lead"), compute)
        assert len(ex.state_changes) == 1
        assert ex.state_changes[0].kind == "lead"

    @pytest.mark.asyncio
    async def test_errors_retain_execution_identity(self, engine: ExecutionEngine):
        async def compute(ctx):
            raise RuntimeError("boom")

        with pytest.raises(ExecutionError) as ei:
            await engine.execute(RTIntent(name="explode"), compute)
        assert ei.value.execution_id is not None
        # the failed execution is recorded & inspectable
        rec = engine.get(ei.value.execution_id)
        assert rec is not None
        assert rec.status is ExecutionStatus.FAILED
        assert "boom" in (rec.error or "")

    @pytest.mark.asyncio
    async def test_parent_child_traceable(self, engine: ExecutionEngine):
        async def parent_compute(ctx):
            # delegate a child execution
            async def child_compute(c):
                return ComputeResult(value="child-result")

            await engine.delegate(
                RTIntent(name="child_task"),
                child_compute,
                parent=ctx,
                actor="sub-agent",
            )
            return ComputeResult(value="parent-result")

        ex = await engine.execute(RTIntent(name="parent_task"), parent_compute)
        assert ex.status is ExecutionStatus.COMPLETED
        # find the child execution
        children = [e for e in engine.recent() if e.parent_execution_id == ex.id]
        assert len(children) == 1
        assert children[0].actor == "sub-agent"

    @pytest.mark.asyncio
    async def test_cancellation_propagates_to_compute(self, engine: ExecutionEngine):
        cancelled_seen: list[bool] = []

        async def compute(ctx):
            ctx.cancel()
            cancelled_seen.append(ctx.cancelled)
            return ComputeResult(value=1)

        # Cancelling mid-execution stops the execution (post-compute enforce).
        with pytest.raises(ExecutionCancelled):
            await engine.execute(RTIntent(name="cancellable"), compute)
        assert cancelled_seen == [True]
        rec = engine.recent()[-1]
        assert rec.status is ExecutionStatus.CANCELLED


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


class TestTask:
    @pytest.mark.asyncio
    async def test_runs_through_runtime(self):
        async def compute(ctx):
            return ComputeResult(value=42)

        t = Task(name="answer", compute=compute)
        ex = await t.run()
        assert t.status is TaskStatus.COMPLETED
        assert ex.result == 42

    @pytest.mark.asyncio
    async def test_conditional_skip(self):
        async def compute(ctx):
            return ComputeResult(value="ran")

        t = Task(name="maybe", compute=compute, condition=lambda r: False)
        await t.run()
        assert t.status is TaskStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_retries_respect_limit(self):
        attempts = {"n": 0}

        async def compute(ctx):
            attempts["n"] += 1
            raise RuntimeError("always fails")

        t = Task(name="flaky", compute=compute, retries=2)
        with pytest.raises(ExecutionError):
            await t.run()
        assert attempts["n"] == 3  # 1 initial + 2 retries


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class TestWorkflow:
    @pytest.mark.asyncio
    async def test_sequential_with_dependencies(self):
        async def mk(v):
            async def c(ctx):
                return ComputeResult(value=v)

            return c

        a = Task(name="a", compute=await mk("A"))
        b = Task(name="b", compute=await mk("B"), depends_on=[a])
        c = Task(name="c", compute=await mk("C"), depends_on=[b])
        wf = Workflow(tasks=[a, b, c], strategy=WorkflowStrategy.SEQUENTIAL)
        run = await wf.run()
        assert run.status == "completed"
        assert list(run.task_statuses.values()) == ["completed"] * 3
        assert run.task_results["c"] == "C"

    @pytest.mark.asyncio
    async def test_parallel_runs_independent(self):
        a = Task(name="a", compute=lambda ctx: ComputeResult(value=1))
        b = Task(name="b", compute=lambda ctx: ComputeResult(value=2))
        wf = Workflow(tasks=[a, b], strategy=WorkflowStrategy.PARALLEL)
        run = await wf.run()
        assert run.status == "completed"
        assert set(run.task_statuses.values()) == {"completed"}

    @pytest.mark.asyncio
    async def test_iterative_until_predicate(self):
        counter = {"n": 0}

        def inc(ctx):
            counter["n"] += 1
            return ComputeResult(value=counter["n"])

        t = Task(name="tick", compute=inc)
        wf = Workflow(
            tasks=[t],
            strategy=WorkflowStrategy.ITERATIVE,
            until=lambda r: r.task_results.get("tick", 0) >= 3,
            max_iterations=10,
        )
        run = await wf.run()
        assert run.status == "completed"
        assert run.iterations == 3
        assert counter["n"] == 3

    @pytest.mark.asyncio
    async def test_no_crew_terminology(self):
        # The Voodoo naming rule: never use "Crew".
        import voodoo.runtime as rt

        assert not hasattr(rt, "Crew")
        assert "Crew" not in rt.__all__


# ---------------------------------------------------------------------------
# Execution graph
# ---------------------------------------------------------------------------


class TestExecutionGraph:
    @pytest.mark.asyncio
    async def test_graph_links_parent_and_child(self, engine: ExecutionEngine):
        async def parent_compute(ctx):
            async def child_compute(c):
                return ComputeResult(value="child")

            await engine.delegate(
                RTIntent(name="child"), child_compute, parent=ctx, actor="sub"
            )
            return ComputeResult(value="parent")

        await engine.execute(RTIntent(name="parent"), parent_compute)
        graph = ExecutionGraph.from_executions(engine.recent())
        assert len(graph.roots) >= 1
        root = graph.roots[-1]
        assert len(root.children) == 1
        assert root.children[0].execution.actor == "sub"


# ---------------------------------------------------------------------------
# Agent × Runtime integration
# ---------------------------------------------------------------------------


class TestAgentRuntimeIntegration:
    """Agent tool calls flow through the runtime authorization path."""

    def _make_agent_with_gated_tool(self, granted: list[str] | None):
        from unittest.mock import MagicMock

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

        provider = MagicMock()
        provider.name = "mock"
        agent = Agent(
            model="mock:test",
            registry=registry,
            capabilities=granted,
        )
        agent.provider = provider
        return agent, registry

    @pytest.mark.asyncio
    async def test_tool_denied_without_capability(self):
        agent, registry = self._make_agent_with_gated_tool(granted=None)
        result = await agent._execute_tool_call("send_email", {"to": "a@b.c"})
        assert isinstance(result, dict)
        assert "CapabilityDenied" in result["error"]
        # the tool must NOT have executed
        assert result.get("error") != "sent to a@b.c"

    @pytest.mark.asyncio
    async def test_tool_allowed_with_capability(self):
        agent, registry = self._make_agent_with_gated_tool(granted=["email.send"])
        result = await agent._execute_tool_call("send_email", {"to": "a@b.c"})
        assert result == "sent to a@b.c"

    @pytest.mark.asyncio
    async def test_context_capability_grants_tool(self):
        from voodoo.primitives.capability import Capability as Cap

        agent, registry = self._make_agent_with_gated_tool(granted=None)
        ctx = ExecutionContext()
        ctx.grant(Cap(name="email.send"))
        from voodoo.runtime.context import use_context

        async with use_context(ctx):
            result = await agent._execute_tool_call("send_email", {"to": "a@b.c"})
        assert result == "sent to a@b.c"
        # the effect was recorded on the context
        assert len(ctx.effects) == 1
        assert ctx.effects[0].name == "tool.send_email"
        assert ctx.effects[0].succeeded

    @pytest.mark.asyncio
    async def test_agent_run_inside_engine_records_effects(
        self, engine: ExecutionEngine
    ):
        """A tool call inside an agent executed via the runtime lands on the Execution."""
        agent, registry = self._make_agent_with_gated_tool(granted=["email.send"])

        async def compute(ctx):
            # simulate an agent-initiated tool call under the runtime context
            await agent._execute_tool_call("send_email", {"to": "x@y.z"})
            return ComputeResult(value="done")

        ex = await engine.execute(RTIntent(name="notify"), compute)
        assert ex.status is ExecutionStatus.COMPLETED
        assert [e.name for e in ex.effects] == ["tool.send_email"]
        assert ex.effects[0].capability_name == "email.send"

    @pytest.mark.asyncio
    async def test_task_with_agent_compute(self):
        """Task(agent=...) runs the agent through the common runtime."""
        from voodoo.ai.agent import Agent as VoodooAgent

        agent = VoodooAgent(model="mock:test")

        t = Task(name="ask", description="hello", agent=agent)
        ex = await t.run()
        assert t.status is TaskStatus.COMPLETED
        assert isinstance(ex.result, str)
