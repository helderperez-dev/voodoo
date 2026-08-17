"""Tests for the Planner (Phase 12) and Adaptive supervisor (Phase 13)."""

from __future__ import annotations

from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.adaptive import (
    AdaptiveSupervisor,
    SupervisorConfig,
    SupervisorDecision,
)
from voodoo.runtime.planner import ComputeParticipant, Planner
from voodoo.runtime.workflow import WorkflowStrategy

# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class TestPlanner:
    def test_exact_capability_match(self):
        planner = Planner()
        planner.register(
            ComputeParticipant(name="emailer", kind="tool", capabilities=["email.send"])
        )
        plan = planner.plan(Intent(name="notify").require("email.send"))
        assert plan.unresolved == []
        assert len(plan.steps) == 1
        assert plan.steps[0].participant == "emailer"
        assert plan.steps[0].kind == "tool"

    def test_unresolved_capability(self):
        planner = Planner()
        plan = planner.plan(Intent(name="x").require("missing.cap"))
        assert plan.unresolved == ["missing.cap"]
        assert plan.steps == []

    def test_fallback_when_multiple_participants_match(self):
        planner = Planner()
        planner.register(
            ComputeParticipant(name="general", kind="compute", capabilities=["search", "read"])
        )
        planner.register(
            ComputeParticipant(name="dedicated", kind="compute", capabilities=["search"])
        )
        plan = planner.plan(Intent(name="search").require("search"))
        # most-specific (fewest other capabilities) is primary
        assert plan.steps[0].participant == "dedicated"
        assert plan.steps[0].fallback == "general"

    def test_approval_required_flag(self):
        planner = Planner()
        planner.register(
            ComputeParticipant(name="payout", kind="human", capabilities=["pay.debit"])
        )
        planner.require_approval("pay.debit")
        plan = planner.plan(Intent(name="payout").require("pay.debit"))
        assert plan.steps[0].requires_approval is True

    def test_parallel_strategy_when_multiple_capabilities(self):
        planner = Planner()
        planner.register(ComputeParticipant(name="a", kind="compute", capabilities=["cap.a"]))
        planner.register(ComputeParticipant(name="b", kind="compute", capabilities=["cap.b"]))
        plan = planner.plan(
            Intent(name="multi").require("cap.a").require("cap.b")
        )
        assert plan.strategy is WorkflowStrategy.PARALLEL

    def test_describe_lists_participants(self):
        planner = Planner()
        planner.register(ComputeParticipant(name="x", kind="tool", capabilities=["c"]))
        d = planner.describe()
        assert d["participants"][0]["name"] == "x"
        assert d["approval_capabilities"] == []


# ---------------------------------------------------------------------------
# AdaptiveSupervisor
# ---------------------------------------------------------------------------


class TestAdaptiveSupervisor:
    async def test_successful_single_step(self):
        from voodoo.primitives.capability import Capability

        engine = ExecutionEngine()
        engine.capabilities.register(Capability(name="math.double"))
        planner = Planner(engine=engine)
        planner.register(
            ComputeParticipant(
                name="doubler",
                kind="compute",
                capabilities=["math.double"],
                compute=lambda ctx: 42,
            )
        )
        intent = Intent(name="double").require("math.double")
        supervisor = AdaptiveSupervisor(planner, engine=engine)
        run = await supervisor.run(intent)
        assert run.status == "completed"
        assert run.result == 42
        assert run.execution_id is not None
        assert run.trace_id is not None
        assert any(d.startswith(SupervisorDecision.CONTINUE.value) for d in run.decisions)

    async def test_unresolved_capability_fails(self):
        engine = ExecutionEngine()
        planner = Planner(engine=engine)
        supervisor = AdaptiveSupervisor(planner, engine=engine)
        run = await supervisor.run(Intent(name="x").require("missing.cap"))
        assert run.status == "failed"
        assert "missing.cap" in (run.error or "")
        assert run.decisions[-1].startswith(SupervisorDecision.FAIL.value)

    async def test_human_step_waits(self):
        engine = ExecutionEngine()
        planner = Planner(engine=engine)
        planner.register(
            ComputeParticipant(
                name="approver",
                kind="human",
                capabilities=["approve.x"],
            )
        )
        intent = Intent(name="needs_approval").require("approve.x")
        supervisor = AdaptiveSupervisor(planner, engine=engine)
        run = await supervisor.run(intent)
        assert run.status == "waiting"
        assert any(d.startswith(SupervisorDecision.REQUEST_APPROVAL.value) for d in run.decisions)

    async def test_step_without_compute_fails(self):
        engine = ExecutionEngine()
        planner = Planner(engine=engine)
        planner.register(
            ComputeParticipant(name="noisy", kind="compute", capabilities=["c.x"], compute=None)
        )
        supervisor = AdaptiveSupervisor(planner, engine=engine)
        run = await supervisor.run(Intent(name="x").require("c.x"))
        assert run.status == "failed"
        assert "no compute" in (run.error or "")

    async def test_fallback_on_capability_denied(self):
        """When the primary step's compute raises, the supervisor falls back."""
        from voodoo.primitives.capability import Capability
        from voodoo.runtime.errors import CapabilityDenied

        engine = ExecutionEngine()
        engine.capabilities.register(Capability(name="cap.x"))
        planner = Planner(engine=engine)

        def primary_compute(ctx):
            raise CapabilityDenied("denied")

        def fallback_compute(ctx):
            return "fallback-ok"

        planner.register(
            ComputeParticipant(
                name="primary", kind="compute", capabilities=["cap.x"], compute=primary_compute
            )
        )
        planner.register(
            ComputeParticipant(
                name="backup", kind="compute", capabilities=["cap.x"], compute=fallback_compute
            )
        )
        intent = Intent(name="x").require("cap.x")
        supervisor = AdaptiveSupervisor(planner, engine=engine)
        run = await supervisor.run(intent)
        # primary raises CapabilityDenied -> supervisor should try fallback
        assert run.status == "completed"
        assert run.result == "fallback-ok"
        assert any(d.startswith(SupervisorDecision.FALLBACK.value) for d in run.decisions)

    async def test_resource_budget_stops_when_exceeded(self):
        """The supervisor accumulates per-step cost and stops when the
        configured budget is exceeded."""
        from voodoo.primitives.capability import Capability
        from voodoo.primitives.resource import Resource
        from voodoo.runtime.engine import ComputeResult

        engine = ExecutionEngine()
        engine.capabilities.register(Capability(name="cap.x"))
        engine.capabilities.register(Capability(name="cap.y"))
        planner = Planner(engine=engine)

        def expensive(ctx):
            return ComputeResult(value="step", resources=Resource(cost=1.0))

        planner.register(
            ComputeParticipant(name="a", kind="compute", capabilities=["cap.x"], compute=expensive)
        )
        planner.register(
            ComputeParticipant(name="b", kind="compute", capabilities=["cap.y"], compute=expensive)
        )

        intent = Intent(name="multi").require("cap.x").require("cap.y")
        # Budget of 0.5 — first step costs 1.0, should fail immediately.
        supervisor = AdaptiveSupervisor(
            planner,
            engine=engine,
            config=SupervisorConfig(budget=Resource(cost=0.5)),
        )
        run = await supervisor.run(intent)
        assert run.status == "failed"
        assert "budget" in (run.error or "").lower()

    async def test_constraint_retry_hint_drives_supervisor_retry(self):
        """When a constraint says ``retry=True`` and the step fails, the
        supervisor retries instead of failing immediately."""
        from voodoo.primitives.capability import Capability
        from voodoo.primitives.constraint import Constraint

        engine = ExecutionEngine()
        engine.capabilities.register(Capability(name="cap.flaky"))
        planner = Planner(engine=engine)

        attempts = [0]

        def flaky(ctx):
            attempts[0] += 1
            if attempts[0] < 3:
                from voodoo.runtime.errors import ExecutionError

                raise ExecutionError("transient failure")
            return "recovered"

        planner.register(
            ComputeParticipant(
                name="flaky_svc", kind="compute", capabilities=["cap.flaky"], compute=flaky
            )
        )
        intent = Intent(name="flaky").require("cap.flaky")
        intent.constrain(Constraint(kind="retry", value=True))
        supervisor = AdaptiveSupervisor(
            planner, engine=engine, config=SupervisorConfig(max_retries=3)
        )
        run = await supervisor.run(intent)
        assert run.status == "completed"
        assert run.result == "recovered"
        assert any(d.startswith(SupervisorDecision.RETRY.value) for d in run.decisions)
