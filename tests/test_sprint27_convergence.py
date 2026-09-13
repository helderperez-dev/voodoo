"""Sprint 27 convergence acceptance tests."""

from __future__ import annotations

from examples.operational_closed_loop.main import run_canary
from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import AdaptiveSupervisor, ExecutionEngine, Goal, GoalRuntime
from voodoo.runtime.planner import ComputeParticipant, Planner, PlanningContext
from voodoo.world import Entity, WorldModel


def test_world_aware_planner_uses_explicit_operational_context() -> None:
    planner = Planner()
    planner.register(
        ComputeParticipant(
            name="remote-controller",
            kind="compute",
            capabilities=["cooling.set"],
            metadata={"priority": 1},
        )
    )
    planner.register(
        ComputeParticipant(
            name="local-controller",
            kind="compute",
            capabilities=["cooling.set"],
            metadata={
                "entity_id": "device:lab",
                "when": {"temperature": 34.0},
            },
        )
    )
    intent = Intent(name="cool-lab").require("cooling.set")

    plan = planner.plan(
        intent,
        context=PlanningContext(
            target_entity_id="device:lab",
            world={"temperature": 34.0},
        ),
    )

    assert plan.steps[0].participant == "local-controller"
    assert plan.steps[0].fallback == "remote-controller"


def test_world_aware_planner_rejects_context_mismatch() -> None:
    planner = Planner()
    planner.register(
        ComputeParticipant(
            name="hot-only",
            kind="compute",
            capabilities=["cooling.set"],
            metadata={"when": {"temperature": 34.0}},
        )
    )
    intent = Intent(name="cool-lab").require("cooling.set")

    plan = planner.plan(intent, context={"world": {"temperature": 20.0}})

    assert plan.unresolved == ["cooling.set"]


async def test_goal_runtime_automatically_plans_from_latest_world() -> None:
    world = WorldModel()
    world.put_entity(Entity(id="device:lab", type="device"))
    world.observe("device:lab", "temperature", 34.0, source="sensor")

    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="cooling.set"))
    planner = Planner(engine=engine)
    calls: list[str] = []

    def remote(ctx):
        calls.append("remote")
        return "remote"

    def local(ctx):
        calls.append("local")
        return "local"

    planner.register(
        ComputeParticipant(
            name="remote-controller",
            kind="compute",
            capabilities=["cooling.set"],
            compute=remote,
            metadata={"priority": 1},
        )
    )
    planner.register(
        ComputeParticipant(
            name="local-controller",
            kind="compute",
            capabilities=["cooling.set"],
            compute=local,
            metadata={
                "entity_id": "device:lab",
                "when": {"temperature": 34.0},
            },
        )
    )
    runtime = GoalRuntime(AdaptiveSupervisor(planner, engine=engine), world=world)

    run = await runtime.achieve(
        Goal(
            name="cool-lab",
            target_entity_id="device:lab",
            requires=["cooling.set"],
        )
    )

    assert run.status.value == "completed"
    assert run.result == "local"
    assert calls == ["local"]
    assert run.context["world"]["temperature"] == 34.0
    assert run.context["world_observations"]["temperature"]["source"] == "sensor"


async def test_operational_closed_loop_canary() -> None:
    result = await run_canary()

    assert result["goal_status"] == "completed"
    assert result["execution_id"]
    assert result["effect_id"]
    assert result["temperature_before_ack"] == 34.0
    assert result["temperature_after_ack"] == 24.0
    assert result["observation_count"] >= 2
