from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import (
    ApplicationNodeKind,
    ChangeReason,
    Goal,
    GoalReconciliation,
    ReconcileAction,
    Runtime,
)
from voodoo.runtime.engine import ComputeResult
from voodoo.world import Entity, WorldModel


def test_runtime_owns_one_connected_control_plane():
    runtime = Runtime(store_config=None)

    assert runtime.reconciler.graph is runtime.graph
    assert runtime.dispatcher.scheduler is runtime.scheduler
    assert runtime.handoff.engine is runtime.engine
    assert runtime.dispatcher.lineage is runtime.lineage
    assert runtime.handoff.lineage is runtime.lineage


async def test_runtime_composes_reconcile_dispatch_and_execution():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    world.observe("business", "conversion", 0.08, source="analytics")

    runtime = Runtime(world=world, local_node_id="runtime-1")
    runtime.engine.capabilities.register(Capability(name="conversion.adjust"))

    metric = runtime.graph.node(ApplicationNodeKind.RESOURCE, "conversion")
    goal = Goal(id="growth", name="growth", target_entity_id="business")
    goal_node = runtime.graph.node(
        ApplicationNodeKind.GOAL,
        goal.name,
        node_id=f"goal:{goal.id}",
    )
    runtime.graph.connect(goal_node.id, "observes", metric.id)

    runtime.register_reconciler(
        ApplicationNodeKind.GOAL,
        GoalReconciliation(
            goal,
            satisfied=lambda item, snapshot: (
                snapshot is not None
                and snapshot.entity.properties.get("conversion", 0) >= 0.10
            ),
            propose=lambda item, snapshot: Intent(
                name="improve-conversion",
                params={"entity_id": "business"},
                requires=["conversion.adjust"],
            ),
        ),
    )

    invalidation = runtime.invalidate(
        metric.id,
        reason=ChangeReason.OBSERVATION,
        revision="obs-1",
    )
    decision = runtime.reconcile(invalidation)[0]
    assert decision.action is ReconcileAction.PROPOSE_INTENT

    plan = runtime.prepare(decision)[0]

    async def compute(ctx):
        world.observe(
            "business",
            "conversion",
            0.11,
            source="effect-ack",
            execution_id=ctx.execution_id,
        )
        return ComputeResult(value="adjusted")

    execution = await runtime.execute(plan, compute)
    assert execution.succeeded
    assert runtime.lineage.chain(execution.id)[-1] == execution.id

    settled = runtime.reconcile(
        runtime.invalidate(
            metric.id,
            reason=ChangeReason.OBSERVATION,
            revision="obs-2",
        )
    )[0]
    assert settled.action is ReconcileAction.SATISFIED
