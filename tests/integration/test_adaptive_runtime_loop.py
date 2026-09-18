import pytest

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime.application_graph import (
    ApplicationGraph,
    ApplicationNodeKind,
    ChangeReason,
    InvalidationEngine,
)
from voodoo.runtime.dispatch import RuntimeDispatcher
from voodoo.runtime.engine import ComputeResult, ExecutionEngine
from types import SimpleNamespace
from voodoo.runtime.persistence import JSONFileExecutionStore
from voodoo.runtime.policy import PolicyDecision
from voodoo.runtime.goal import Goal
from voodoo.runtime.handoff import ExecutionHandoff
from voodoo.runtime.reconcile import (
    GoalReconciliation,
    ReconcileAction,
    Reconciler,
)
from voodoo.world import Entity, WorldModel


@pytest.mark.asyncio
async def test_observation_to_goal_to_execution_to_satisfied_loop(tmp_path):
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    world.observe("business", "conversion", 0.08, source="analytics")

    goal = Goal(
        id="growth",
        name="growth",
        target_entity_id="business",
        requires=[],
    )
    graph = ApplicationGraph()
    metric = graph.node(ApplicationNodeKind.RESOURCE, "conversion")
    goal_node = graph.node(
        ApplicationNodeKind.GOAL, goal.name, node_id=f"goal:{goal.id}"
    )
    graph.connect(goal_node.id, "observes", metric.id)

    handler = GoalReconciliation(
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
    )
    reconciler = Reconciler(graph).register(ApplicationNodeKind.GOAL, handler)
    invalidation = InvalidationEngine(graph).invalidate(
        metric.id, reason=ChangeReason.OBSERVATION, revision="obs-1"
    )

    proposed = reconciler.reconcile(invalidation, world=world)[0]
    assert proposed.action is ReconcileAction.PROPOSE_INTENT

    class LocalFabric:
        def place(self, requirement):
            assert requirement.capability == "conversion.adjust"
            return SimpleNamespace(
                node_id="runtime-1",
                reasons=("capability:conversion.adjust",),
            )

    plan = RuntimeDispatcher(fabric=LocalFabric()).prepare(proposed)[0]
    assert plan.placement is not None
    assert plan.placement.node_id == "runtime-1"

    store_path = tmp_path / "executions.jsonl"
    engine = ExecutionEngine()
    engine.use_store(JSONFileExecutionStore(store_path))
    engine.capabilities.register(Capability(name="conversion.adjust"))
    engine.capabilities.policy.use_world(world)
    engine.capabilities.policy.register(
        lambda request: (
            PolicyDecision.ALLOW
            if request.target_entity_id == "business"
            else PolicyDecision.DENY
        ),
        name="business-only",
    )

    async def compute(ctx):
        world.observe(
            "business",
            "conversion",
            0.11,
            source="effect-ack",
            execution_id=ctx.execution_id,
        )
        return ComputeResult(value="adjusted")

    execution = await ExecutionHandoff(engine, local_node_id="runtime-1").execute(
        plan, compute
    )
    assert execution.succeeded
    assert engine.capabilities.last_policy_result is not None
    assert engine.capabilities.last_policy_result.decision is PolicyDecision.ALLOW

    restarted = ExecutionEngine()
    restarted.use_store(JSONFileExecutionStore(store_path))
    assert restarted.recover() == []
    persisted = JSONFileExecutionStore(store_path).load_latest()
    assert persisted[execution.id].succeeded

    next_invalidation = InvalidationEngine(graph).invalidate(
        metric.id, reason=ChangeReason.OBSERVATION, revision="obs-2"
    )
    settled = reconciler.reconcile(next_invalidation, world=world)[0]

    assert settled.action is ReconcileAction.SATISFIED
    assert settled.intents == ()
