from __future__ import annotations

from types import SimpleNamespace

from voodoo.primitives.capability import Capability
from voodoo.primitives.constraint import Constraint
from voodoo.primitives.intent import Intent
from voodoo.runtime.adaptive import AdaptiveSupervisor, SupervisorConfig
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.errors import ExecutionError
from voodoo.runtime.planner import ComputeParticipant, Planner


def _agent_run(output: str):
    return SimpleNamespace(
        output=output,
        cost=0.0,
        tokens_in=1,
        tokens_out=1,
        timings={"total_ms": 1.0},
    )


async def test_agent_participant_is_executable_compute():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="reason.answer"))
    planner = Planner(engine=engine)

    seen: dict[str, object] = {}

    class AgentParticipant:
        async def run(self, prompt, context=None):
            seen["prompt"] = prompt
            seen["context"] = context
            return _agent_run("agent-result")

    planner.register(
        ComputeParticipant(
            name="reasoner",
            kind="agent",
            capabilities=["reason.answer"],
            agent=AgentParticipant(),
        )
    )

    run = await AdaptiveSupervisor(planner, engine=engine).run(
        Intent(name="answer").require("reason.answer"),
        context={"request_id": "req-1"},
    )

    assert run.status == "completed"
    assert run.result == "agent-result"
    assert run.step_results == {"reasoner": "agent-result"}
    assert "reason.answer" in str(seen["prompt"])
    assert seen["context"]["request_id"] == "req-1"


async def test_max_iterations_is_a_real_hard_bound():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="cap.one"))
    engine.capabilities.register(Capability(name="cap.two"))
    planner = Planner(engine=engine)
    planner.register(
        ComputeParticipant(
            name="one",
            kind="compute",
            capabilities=["cap.one"],
            compute=lambda ctx: "one",
        )
    )
    planner.register(
        ComputeParticipant(
            name="two",
            kind="compute",
            capabilities=["cap.two"],
            compute=lambda ctx: "two",
        )
    )

    intent = Intent(name="bounded").require("cap.one").require("cap.two")
    run = await AdaptiveSupervisor(
        planner,
        engine=engine,
        config=SupervisorConfig(max_iterations=1),
    ).run(intent)

    assert run.status == "failed"
    assert run.iterations == 1
    assert "max_iterations=1" in (run.error or "")
    assert run.step_results == {"one": "one"}


async def test_retry_budget_is_step_local_not_global():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="cap.one"))
    engine.capabilities.register(Capability(name="cap.two"))
    planner = Planner(engine=engine)
    attempts = {"one": 0, "two": 0}

    def first(ctx):
        attempts["one"] += 1
        if attempts["one"] == 1:
            raise ExecutionError("one transient")
        return "one-ok"

    def second(ctx):
        attempts["two"] += 1
        if attempts["two"] == 1:
            raise ExecutionError("two transient")
        return "two-ok"

    planner.register(
        ComputeParticipant(
            name="one", kind="compute", capabilities=["cap.one"], compute=first
        )
    )
    planner.register(
        ComputeParticipant(
            name="two", kind="compute", capabilities=["cap.two"], compute=second
        )
    )

    intent = Intent(name="retry-both").require("cap.one").require("cap.two")
    intent.constrain(Constraint(kind="retry", value=True))
    run = await AdaptiveSupervisor(
        planner,
        engine=engine,
        config=SupervisorConfig(max_retries=1, max_iterations=4),
    ).run(intent)

    assert run.status == "completed"
    assert attempts == {"one": 2, "two": 2}
    assert run.iterations == 4
    assert run.step_results == {"one": "one-ok", "two": "two-ok"}
    assert sum(decision.startswith("retry") for decision in run.decisions) == 2


async def test_execution_error_can_select_declared_fallback():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="search"))
    planner = Planner(engine=engine)

    def primary(ctx):
        raise ExecutionError("primary unavailable")

    planner.register(
        ComputeParticipant(
            name="primary",
            kind="compute",
            capabilities=["search"],
            compute=primary,
        )
    )
    planner.register(
        ComputeParticipant(
            name="general",
            kind="compute",
            capabilities=["search", "read"],
            compute=lambda ctx: "fallback-ok",
        )
    )

    run = await AdaptiveSupervisor(planner, engine=engine).run(
        Intent(name="find").require("search")
    )

    assert run.status == "completed"
    assert run.result == "fallback-ok"
    assert run.step_results["general"] == "fallback-ok"
    assert any(decision.startswith("fallback") for decision in run.decisions)


async def test_previous_step_outputs_reach_following_agent():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="data.fetch"))
    engine.capabilities.register(Capability(name="data.explain"))
    planner = Planner(engine=engine)
    captured: dict[str, object] = {}

    planner.register(
        ComputeParticipant(
            name="fetcher",
            kind="compute",
            capabilities=["data.fetch"],
            compute=lambda ctx: {"temperature": 31},
        )
    )

    class Explainer:
        async def run(self, prompt, context=None):
            captured["prompt"] = prompt
            captured["context"] = context
            return _agent_run("hot")

    planner.register(
        ComputeParticipant(
            name="explainer",
            kind="agent",
            capabilities=["data.explain"],
            agent=Explainer(),
        )
    )

    intent = Intent(name="explain-weather").require("data.fetch").require(
        "data.explain"
    )
    run = await AdaptiveSupervisor(planner, engine=engine).run(intent)

    assert run.status == "completed"
    context = captured["context"]
    assert context["upstream"]["fetcher"] == {"temperature": 31}
    assert "fetcher" in str(captured["prompt"])


def test_decision_records_are_structured():
    from voodoo.runtime.adaptive import AdaptiveDecisionRecord, SupervisorDecision

    record = AdaptiveDecisionRecord(
        decision=SupervisorDecision.RETRY,
        detail="attempt 1",
        step="worker",
        iteration=2,
        execution_id="exec-1",
        trace_id="trace-1",
    )
    assert record.describe() == {
        "decision": "retry",
        "detail": "attempt 1",
        "step": "worker",
        "iteration": 2,
        "execution_id": "exec-1",
        "trace_id": "trace-1",
    }
