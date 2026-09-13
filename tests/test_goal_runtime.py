from __future__ import annotations

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import (
    AdaptiveSupervisor,
    ComputeParticipant,
    ExecutionEngine,
    Goal,
    GoalRuntime,
    GoalStatus,
    Planner,
)
from voodoo.world import Entity, WorldModel


def _runtime(*participants: ComputeParticipant, world=None):
    engine = ExecutionEngine()
    planner = Planner(engine=engine)
    for participant in participants:
        for capability in participant.capabilities:
            engine.capabilities.register(Capability(name=capability))
        planner.register(participant)
    supervisor = AdaptiveSupervisor(planner, engine=engine)
    return GoalRuntime(supervisor, world=world), engine


async def test_goal_can_coordinate_multiple_intents():
    runtime, _ = _runtime(
        ComputeParticipant(
            name="reader",
            kind="compute",
            capabilities=["inventory.read"],
            compute=lambda ctx: {"stock": 2},
        ),
        ComputeParticipant(
            name="buyer",
            kind="compute",
            capabilities=["purchase.create"],
            compute=lambda ctx: {"purchase_id": "p-1"},
        ),
    )
    goal = Goal(name="keep-inventory-available")
    intents = [
        Intent(name="inspect-stock").require("inventory.read"),
        Intent(name="replenish-stock").require("purchase.create"),
    ]

    run = await runtime.achieve(goal, intents=intents)

    assert run.status is GoalStatus.COMPLETED
    assert goal.intent_ids == [intents[0].id, intents[1].id]
    assert [item.status for item in run.intent_runs] == ["completed", "completed"]
    assert run.result == [{"stock": 2}, {"purchase_id": "p-1"}]


async def test_goal_decomposer_receives_world_snapshot():
    world = WorldModel()
    world.put_entity(Entity(type="warehouse", id="warehouse-1"))
    world.observe("warehouse-1", "stock.widget", 2, source="erp")
    runtime, _ = _runtime(
        ComputeParticipant(
            name="buyer",
            kind="compute",
            capabilities=["purchase.create"],
            compute=lambda ctx: "ordered",
        ),
        world=world,
    )
    seen = {}

    async def decompose(goal, snapshot):
        seen["stock"] = snapshot.entity.get("stock.widget")
        return [Intent(name="replenish").require("purchase.create")]

    goal = Goal(
        name="keep-stock",
        objective="keep widget stock above zero",
        target_entity_id="warehouse-1",
    )

    run = await runtime.achieve(goal, decomposer=decompose)

    assert seen["stock"] == 2
    assert run.status is GoalStatus.COMPLETED
    assert run.intent_runs[0].result == "ordered"


async def test_goal_waits_when_an_intent_needs_human_approval():
    runtime, engine = _runtime(
        ComputeParticipant(
            name="payer",
            kind="compute",
            capabilities=["payment.execute"],
            compute=lambda ctx: "paid",
        )
    )
    engine.capabilities.require_approval("payment.execute")
    goal = Goal(name="settle-invoice")

    run = await runtime.achieve(
        goal,
        intents=[Intent(name="pay").require("payment.execute")],
    )

    assert run.status is GoalStatus.WAITING
    assert run.intent_runs[0].status == "waiting"


async def test_goal_stops_after_failed_intent():
    calls = []

    def fail(ctx):
        from voodoo.runtime.errors import ExecutionError

        raise ExecutionError("supplier unavailable")

    def should_not_run(ctx):
        calls.append("second")
        return "unexpected"

    runtime, _ = _runtime(
        ComputeParticipant(
            name="supplier",
            kind="compute",
            capabilities=["supplier.quote"],
            compute=fail,
        ),
        ComputeParticipant(
            name="buyer",
            kind="compute",
            capabilities=["purchase.create"],
            compute=should_not_run,
        ),
    )
    goal = Goal(name="replenish")

    run = await runtime.achieve(
        goal,
        intents=[
            Intent(name="quote").require("supplier.quote"),
            Intent(name="buy").require("purchase.create"),
        ],
    )

    assert run.status is GoalStatus.FAILED
    assert "supplier unavailable" in (run.error or "")
    assert calls == []


async def test_goal_can_generate_single_intent_from_required_capabilities():
    runtime, _ = _runtime(
        ComputeParticipant(
            name="inspector",
            kind="compute",
            capabilities=["machine.inspect"],
            compute=lambda ctx: "healthy",
        )
    )
    goal = Goal(
        name="verify-machine",
        objective="ensure the machine is healthy",
        requires=["machine.inspect"],
    )

    run = await runtime.achieve(goal)

    assert run.status is GoalStatus.COMPLETED
    assert run.result == "healthy"
    assert len(goal.intent_ids) == 1
