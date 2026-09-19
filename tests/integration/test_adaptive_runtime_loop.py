import pytest

from voodoo import App
from voodoo.primitives.intent import Intent
from voodoo.runtime import ReconcileAction, Runtime
from voodoo.runtime.engine import ComputeResult
from voodoo.world import Entity, WorldModel


@pytest.mark.asyncio
async def test_public_app_observation_goal_capability_loop():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    app = App(runtime=Runtime(world=world))
    conversion = app.observation("business", "conversion")

    @app.goal(
        "growth",
        observes=(conversion,),
        target_entity_id="business",
        propose=lambda goal, snapshot: Intent(
            name="conversion.adjust",
            requires=["conversion.adjust"],
        ),
    )
    def growth(snapshot):
        return (
            snapshot is not None
            and snapshot.entity.properties.get("conversion", 0) >= 0.10
        )

    @app.capability("conversion.adjust")
    async def improve(ctx):
        return ComputeResult(value="adjusted")

    first = await conversion.set(0.08, source="analytics")
    assert first is not None
    proposed = next(item for item in first.decisions if item.node_id == "goal:growth")
    assert proposed.action is ReconcileAction.PROPOSE_INTENT
    assert len(first.executions) == 1
    assert first.executions[0].succeeded

    second = await conversion.set(0.11, source="effect-ack")
    assert second is not None
    settled = next(item for item in second.decisions if item.node_id == "goal:growth")
    assert settled.action is ReconcileAction.SATISFIED
    assert settled.intents == ()
    assert second.executions == ()
