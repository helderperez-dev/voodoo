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


@pytest.mark.asyncio
async def test_growth_bi_reacts_only_to_metrics_each_goal_observes():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    app = App(runtime=Runtime(world=world))

    users = app.observation("business", "users")
    revenue = app.observation("business", "revenue")
    conversion = app.observation("business", "conversion")
    churn = app.observation("business", "churn")

    @app.goal(
        "monetization",
        observes=(users, revenue, conversion),
        target_entity_id="business",
        propose=lambda goal, snapshot: Intent(
            name="monetization.improve",
            requires=["monetization.improve"],
        ),
    )
    def monetization(snapshot):
        if snapshot is None:
            return False
        values = snapshot.entity.properties
        return values.get("conversion", 0) >= 0.10

    @app.goal(
        "retention",
        observes=(churn,),
        target_entity_id="business",
        propose=lambda goal, snapshot: Intent(
            name="retention.improve",
            requires=["retention.improve"],
        ),
    )
    def retention(snapshot):
        if snapshot is None:
            return False
        return snapshot.entity.properties.get("churn", 1.0) <= 0.05

    @app.capability("monetization.improve")
    async def improve_monetization(ctx):
        return ComputeResult(value={"action": "experiment"})

    @app.capability("retention.improve")
    async def improve_retention(ctx):
        return ComputeResult(value={"action": "winback"})

    users_cycle = await users.set(1000, source="analytics")
    assert users_cycle is not None
    assert any(item.node_id == "goal:monetization" for item in users_cycle.decisions)
    assert all(item.node_id != "goal:retention" for item in users_cycle.decisions)
    assert len(users_cycle.executions) == 1

    revenue_cycle = await revenue.set(800.0, source="billing")
    assert revenue_cycle is not None
    assert any(item.node_id == "goal:monetization" for item in revenue_cycle.decisions)
    assert all(item.node_id != "goal:retention" for item in revenue_cycle.decisions)

    conversion_cycle = await conversion.set(0.11, source="analytics")
    assert conversion_cycle is not None
    monetization_done = next(
        item
        for item in conversion_cycle.decisions
        if item.node_id == "goal:monetization"
    )
    assert monetization_done.action is ReconcileAction.SATISFIED
    assert conversion_cycle.executions == ()

    churn_cycle = await churn.set(0.09, source="analytics")
    assert churn_cycle is not None
    assert any(item.node_id == "goal:retention" for item in churn_cycle.decisions)
    assert all(item.node_id != "goal:monetization" for item in churn_cycle.decisions)
    assert len(churn_cycle.executions) == 1

    churn_stable = await churn.set(0.04, source="analytics")
    assert churn_stable is not None
    retention_done = next(
        item for item in churn_stable.decisions if item.node_id == "goal:retention"
    )
    assert retention_done.action is ReconcileAction.SATISFIED
    assert churn_stable.executions == ()
