import pytest

from voodoo import App
from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import (
    ApplicationNodeKind,
    ChangeReason,
    ComputeParticipant,
    ConvergenceStatus,
    Goal,
    GoalStatus,
    Invalidation,
    ReconcileAction,
    ReconcileDecision,
    Runtime,
    RuntimeCycle,
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


@pytest.mark.asyncio
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

    runtime.register_goal(
        goal,
        observes=(metric.id,),
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


def test_runtime_keeps_goal_reconciliation_scoped_per_goal():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    world.observe("business", "conversion", 0.08, source="analytics")

    runtime = Runtime(world=world)
    metric = runtime.graph.node(ApplicationNodeKind.RESOURCE, "conversion")
    growth = Goal(id="growth", name="growth", target_entity_id="business")
    retention = Goal(id="retention", name="retention", target_entity_id="business")

    runtime.register_goal(
        growth,
        observes=(metric.id,),
        satisfied=lambda item, snapshot: False,
        propose=lambda item, snapshot: Intent(name="grow"),
    )
    runtime.register_goal(
        retention,
        observes=(metric.id,),
        satisfied=lambda item, snapshot: True,
        propose=lambda item, snapshot: Intent(name="retain"),
    )

    decisions = runtime.reconcile(
        runtime.invalidate(
            metric.id,
            reason=ChangeReason.OBSERVATION,
            revision="obs-multi",
        )
    )
    by_node = {decision.node_id: decision for decision in decisions}

    assert by_node["goal:growth"].action is ReconcileAction.PROPOSE_INTENT
    assert by_node["goal:growth"].intents[0].name == "grow"
    assert by_node["goal:retention"].action is ReconcileAction.SATISFIED


def test_runtime_goal_registration_is_idempotent_but_rejects_identity_conflict():
    runtime = Runtime()
    goal = Goal(id="growth", name="growth")
    runtime.register_goal(goal, satisfied=lambda item, snapshot: True)
    runtime.register_goal(goal, satisfied=lambda item, snapshot: True)

    conflicting = runtime.graph.get("goal:growth")
    assert conflicting is not None

    other = Goal(id="growth", name="different")
    with pytest.raises(ValueError, match="conflicts with Goal"):
        runtime.register_goal(other, satisfied=lambda item, snapshot: True)


@pytest.mark.asyncio
async def test_runtime_owns_adaptive_goal_execution():
    runtime = Runtime()
    runtime.engine.capabilities.register(Capability(name="inventory.read"))
    runtime.register_compute(
        ComputeParticipant(
            name="reader",
            kind="compute",
            capabilities=["inventory.read"],
            compute=lambda ctx: {"stock": 2},
        )
    )

    goal = Goal(name="inspect-inventory")
    run = await runtime.achieve(
        goal,
        intents=[Intent(name="inspect").require("inventory.read")],
    )

    assert runtime.goals.supervisor is runtime.supervisor
    assert runtime.supervisor.engine is runtime.engine
    assert runtime.planner.engine is runtime.engine
    assert run.status is GoalStatus.COMPLETED
    assert run.result == {"stock": 2}


@pytest.mark.asyncio
async def test_runtime_executes_only_proposed_reconciliation_work():
    runtime = Runtime()
    calls = []

    async def compute(ctx):
        calls.append(ctx.execution_id)
        return ComputeResult(value="ran")

    satisfied = ReconcileDecision(
        node_id="goal:done",
        action=ReconcileAction.SATISFIED,
        reason="already done",
    )
    assert await runtime.execute_decision(satisfied, compute) == ()
    assert calls == []


@pytest.mark.asyncio
async def test_runtime_cycle_is_bounded_and_structured():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    world.observe("business", "conversion", 0.08, source="analytics")

    runtime = Runtime(world=world)
    runtime.engine.capabilities.register(Capability(name="conversion.adjust"))
    metric = runtime.graph.node(ApplicationNodeKind.RESOURCE, "conversion")
    goal = Goal(id="cycle-growth", name="cycle-growth", target_entity_id="business")
    runtime.register_goal(
        goal,
        observes=(metric.id,),
        satisfied=lambda item, snapshot: (
            snapshot is not None
            and snapshot.entity.properties.get("conversion", 0) >= 0.10
        ),
        propose=lambda item, snapshot: Intent(
            name="improve-conversion",
            requires=["conversion.adjust"],
        ),
    )

    calls = []

    async def compute(ctx):
        calls.append(ctx.execution_id)
        world.observe("business", "conversion", 0.11, source="effect-ack")
        return ComputeResult(value="adjusted")

    cycle = await runtime.cycle(
        metric.id,
        compute,
        reason=ChangeReason.OBSERVATION,
        revision="cycle-1",
    )

    goal_decisions = [
        item for item in cycle.decisions if item.node_id == "goal:cycle-growth"
    ]
    assert len(goal_decisions) == 1
    assert goal_decisions[0].action is ReconcileAction.PROPOSE_INTENT
    assert len(cycle.executions) == 1
    assert len(calls) == 1

    # The observation produced during compute does not recursively trigger
    # another reconciliation cycle.
    assert cycle.invalidation.revision == "cycle-1"


@pytest.mark.asyncio
async def test_runtime_observation_binding_drives_one_bounded_cycle():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    runtime = Runtime(world=world)
    runtime.engine.capabilities.register(Capability(name="conversion.adjust"))

    resource_id = runtime.bind_observation("business", "conversion")
    goal = Goal(
        id="observed-growth", name="observed-growth", target_entity_id="business"
    )
    runtime.register_goal(
        goal,
        observes=(resource_id,),
        satisfied=lambda item, snapshot: (
            snapshot is not None
            and snapshot.entity.properties.get("conversion", 0) >= 0.10
        ),
        propose=lambda item, snapshot: Intent(
            name="improve-conversion",
            requires=["conversion.adjust"],
        ),
    )

    async def compute(ctx):
        return ComputeResult(value="scheduled")

    cycle = await runtime.observe(
        "business",
        "conversion",
        0.08,
        source="analytics",
        compute=compute,
    )

    assert cycle is not None
    assert cycle.invalidation.source == resource_id
    assert len(cycle.executions) == 1
    goal_decision = next(
        item for item in cycle.decisions if item.node_id == "goal:observed-growth"
    )
    assert goal_decision.action is ReconcileAction.PROPOSE_INTENT


@pytest.mark.asyncio
async def test_unbound_observation_updates_world_without_runtime_work():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    runtime = Runtime(world=world)

    cycle = await runtime.observe(
        "business",
        "visitors",
        42,
        source="analytics",
    )

    assert cycle is None
    assert world.entity("business").properties["visitors"] == 42


@pytest.mark.asyncio
async def test_runtime_convergence_has_hard_observation_bound():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    runtime = Runtime(world=world)

    result = await runtime.converge(
        [
            {
                "entity_id": "business",
                "property": "visitors",
                "value": value,
                "source": "analytics",
            }
            for value in (1, 2, 3)
        ],
        max_cycles=2,
    )

    assert result.processed == 2
    assert result.exhausted is True
    assert result.status is ConvergenceStatus.LIMIT_REACHED
    assert result.cycles == ()
    assert world.entity("business").properties["visitors"] == 2


@pytest.mark.asyncio
async def test_runtime_convergence_rejects_unbounded_or_invalid_input():
    runtime = Runtime(world=WorldModel())

    with pytest.raises(ValueError, match="max_cycles"):
        await runtime.converge([], max_cycles=0)

    with pytest.raises(ValueError, match="missing required field: source"):
        await runtime.converge(
            [{"entity_id": "business", "property": "visitors", "value": 1}]
        )


@pytest.mark.asyncio
async def test_runtime_convergence_reports_stable_when_no_semantic_work_remains():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    runtime = Runtime(world=world)

    result = await runtime.converge(
        [
            {
                "entity_id": "business",
                "property": "visitors",
                "value": 1,
                "source": "analytics",
            }
        ]
    )

    assert result.status is ConvergenceStatus.STABLE
    assert result.exhausted is False


def test_runtime_convergence_status_prioritizes_failure_and_blocking():
    failed = Runtime._convergence_status(
        [
            RuntimeCycle(
                invalidation=Invalidation(
                    source="resource:x",
                    affected=("goal:x",),
                    reason=ChangeReason.STATE,
                ),
                decisions=(
                    ReconcileDecision(
                        node_id="goal:x",
                        action=ReconcileAction.FAILED,
                        reason="failed",
                    ),
                ),
                executions=(),
            )
        ],
        limit_reached=False,
    )
    assert failed is ConvergenceStatus.FAILED


def test_app_owns_canonical_runtime_without_building_asgi_app():
    app = App()
    assert isinstance(app.runtime, Runtime)
    assert app._starlette is None
    assert app.world is app.runtime.world


def test_app_adaptive_facade_delegates_to_canonical_runtime():
    world = WorldModel()
    runtime = Runtime(world=world)
    app = App(runtime=runtime)
    capability = Capability(name="orders.read")
    goal = Goal(id="orders-visible", name="orders-visible")

    assert app.capability(capability) is app
    assert app.goal(goal, satisfied=lambda item, snapshot: True) is app
    assert runtime.engine.capabilities.resolve("orders.read").value == "allowed"
    assert runtime.graph.get("goal:orders-visible") is not None


@pytest.mark.asyncio
async def test_app_observation_handle_is_the_public_reactive_source():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    app = App(runtime=Runtime(world=world))

    conversion = app.observation("business", "conversion")

    assert conversion.resource_id == "resource:business:conversion"
    result = await conversion.set(0.08, source="analytics")
    assert result is not None
    assert result.invalidation.source == conversion.resource_id
    assert world.entity("business").properties["conversion"] == 0.08


def test_app_goal_accepts_observation_handles_directly():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    app = App(runtime=Runtime(world=world))
    conversion = app.observation("business", "conversion")
    goal = Goal(id="growth-handle", name="growth-handle")

    assert (
        app.goal(
            goal,
            observes=(conversion,),
            satisfied=lambda item, snapshot: True,
        )
        is app
    )
    node = app.runtime.graph.get("goal:growth-handle")
    assert node is not None
    assert conversion.resource_id in {
        dependency.id for dependency in app.runtime.graph.dependencies(node.id)
    }


def test_app_capability_decorator_registers_authority_and_compute():
    app = App()

    @app.capability("orders.read")
    async def read_orders(ctx):
        return {"orders": []}

    assert app.runtime.engine.capabilities.resolve("orders.read").value == "allowed"
    participant = app.runtime.planner.participants["read_orders"]
    assert participant.compute is read_orders
    assert participant.capabilities == ["orders.read"]


@pytest.mark.asyncio
async def test_app_goal_decorator_builds_canonical_goal_and_reconciles():
    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    app = App(runtime=Runtime(world=world))
    conversion = app.observation("business", "conversion")

    @app.goal(
        "grow",
        observes=(conversion,),
        target_entity_id="business",
        propose=lambda goal, snapshot: Intent(name="conversion.adjust"),
    )
    def growth(snapshot):
        return (
            snapshot is not None
            and snapshot.entity.properties.get("conversion", 0) >= 0.10
        )

    cycle = await conversion.set(0.08, source="analytics")

    assert growth.__name__ == "growth"
    assert cycle is not None
    decision = next(item for item in cycle.decisions if item.node_id == "goal:grow")
    assert decision.action is ReconcileAction.PROPOSE_INTENT
    assert decision.intents[0].name == "conversion.adjust"


def test_app_starlette_uses_the_same_canonical_runtime():
    runtime = Runtime()
    app = App(runtime=runtime)

    starlette = app.starlette

    assert app.runtime is runtime
    assert starlette is app._starlette
