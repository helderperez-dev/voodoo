from voodoo.primitives.intent import Intent
from voodoo.runtime.application_graph import (
    ApplicationGraph,
    ApplicationNodeKind,
    ChangeReason,
    InvalidationEngine,
)
from voodoo.runtime.reconcile import ReconcileAction, ReconcileDecision, Reconciler


def test_reconciler_proposes_intent_without_executing_it():
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "analytics")
    goal = graph.node(ApplicationNodeKind.GOAL, "conversion")
    graph.connect(goal.id, "observes", resource.id)

    invalidation = InvalidationEngine(graph).invalidate(
        resource.id,
        reason=ChangeReason.OBSERVATION,
        revision="obs-42",
    )
    proposed = Intent(name="improve_conversion").require("campaign.adjust")

    reconciler = Reconciler(graph).register(
        ApplicationNodeKind.GOAL,
        lambda node, change, world: ReconcileDecision(
            node_id=node.id,
            action=ReconcileAction.PROPOSE_INTENT,
            reason=f"new evidence {change.revision}",
            intents=(proposed,),
        ),
    )

    decisions = reconciler.reconcile(invalidation)

    assert len(decisions) == 1
    assert decisions[0].action is ReconcileAction.PROPOSE_INTENT
    assert decisions[0].intents == (proposed,)
    assert proposed.status.value == "created"


def test_reconciler_waits_when_no_semantic_handler_is_registered():
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "sensor")
    goal = graph.node(ApplicationNodeKind.GOAL, "temperature")
    graph.connect(goal.id, "observes", resource.id)

    invalidation = InvalidationEngine(graph).invalidate(resource.id)
    decision = Reconciler(graph).reconcile(invalidation)[0]

    assert decision.action is ReconcileAction.WAIT
    assert "no reconciler registered" in decision.reason


def test_reconciler_bounds_decision_fanout():
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "source")
    first = graph.node(ApplicationNodeKind.GOAL, "first")
    second = graph.node(ApplicationNodeKind.GOAL, "second")
    graph.connect(first.id, "observes", resource.id)
    graph.connect(second.id, "observes", resource.id)

    invalidation = InvalidationEngine(graph).invalidate(resource.id)
    reconciler = Reconciler(graph, max_decisions=1).register(
        ApplicationNodeKind.GOAL,
        lambda node, change, world: ReconcileDecision(
            node_id=node.id,
            action=ReconcileAction.SATISFIED,
            reason="checked",
        ),
    )

    assert len(reconciler.reconcile(invalidation)) == 1


def test_goal_reconciliation_uses_observed_world_and_preserves_authority_boundary():
    from voodoo.runtime.goal import Goal
    from voodoo.runtime.reconcile import GoalReconciliation
    from voodoo.world import Entity, WorldModel

    world = WorldModel()
    world.put_entity(Entity(id="business", type="business"))
    world.observe("business", "conversion_rate", 0.08, source="analytics")

    goal = Goal(
        id="goal_conversion",
        name="conversion",
        target_entity_id="business",
        requires=["campaign.adjust"],
    )
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "conversion_rate")
    goal_node = graph.node(
        ApplicationNodeKind.GOAL, goal.name, node_id=f"goal:{goal.id}"
    )
    graph.connect(goal_node.id, "observes", resource.id)
    invalidation = InvalidationEngine(graph).invalidate(
        resource.id, reason=ChangeReason.OBSERVATION, revision="obs-1"
    )

    handler = GoalReconciliation(
        goal=goal,
        satisfied=lambda item, snapshot: (
            snapshot is not None
            and snapshot.entity.properties.get("conversion_rate", 0) >= 0.10
        ),
        propose=lambda item, snapshot: Intent(name="improve_conversion"),
    )
    decision = (
        Reconciler(graph)
        .register(ApplicationNodeKind.GOAL, handler)
        .reconcile(invalidation, world=world)[0]
    )

    assert decision.action is ReconcileAction.PROPOSE_INTENT
    assert decision.intents[0].requires == ["campaign.adjust"]
    assert decision.intents[0].params["_goal_id"] == goal.id
    assert decision.intents[0].status.value == "created"


def test_goal_reconciliation_is_satisfied_without_proposing_work():
    from voodoo.runtime.goal import Goal
    from voodoo.runtime.reconcile import GoalReconciliation
    from voodoo.world import Entity, WorldModel

    world = WorldModel()
    world.put_entity(Entity(id="service", type="service"))
    world.observe("service", "healthy", True, source="health")

    goal = Goal(id="goal_health", name="health", target_entity_id="service")
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "health")
    goal_node = graph.node(
        ApplicationNodeKind.GOAL, goal.name, node_id=f"goal:{goal.id}"
    )
    graph.connect(goal_node.id, "observes", resource.id)

    handler = GoalReconciliation(
        goal=goal,
        satisfied=lambda item, snapshot: (
            snapshot is not None and snapshot.entity.properties.get("healthy") is True
        ),
    )
    invalidation = InvalidationEngine(graph).invalidate(resource.id)
    decision = (
        Reconciler(graph)
        .register(ApplicationNodeKind.GOAL, handler)
        .reconcile(invalidation, world=world)[0]
    )

    assert decision.action is ReconcileAction.SATISFIED
    assert decision.intents == ()


def test_reconciler_suppresses_duplicate_intent_proposals():
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "metric")
    goal = graph.node(ApplicationNodeKind.GOAL, "target")
    graph.connect(goal.id, "observes", resource.id)
    invalidation = InvalidationEngine(graph).invalidate(resource.id)

    reconciler = Reconciler(graph).register(
        ApplicationNodeKind.GOAL,
        lambda node, change, world: ReconcileDecision(
            node_id=node.id,
            action=ReconcileAction.PROPOSE_INTENT,
            reason="target unmet",
            intents=(Intent(name="adjust", params={"amount": 1}),),
        ),
    )

    first = reconciler.reconcile(invalidation)[0]
    second = reconciler.reconcile(invalidation)[0]

    assert first.action is ReconcileAction.PROPOSE_INTENT
    assert second.action is ReconcileAction.WAIT
    assert second.reason == "duplicate intent proposal suppressed"


def test_reconciler_allows_duplicate_after_cooldown_window():
    from datetime import UTC, datetime, timedelta

    from voodoo.runtime.reconcile import ReconcileGuard, ReconcileLedger

    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "metric")
    goal = graph.node(ApplicationNodeKind.GOAL, "target")
    graph.connect(goal.id, "observes", resource.id)
    invalidation = InvalidationEngine(graph).invalidate(resource.id)
    ledger = ReconcileLedger()
    reconciler = Reconciler(
        graph,
        guard=ReconcileGuard(cooldown_seconds=1),
        ledger=ledger,
    ).register(
        ApplicationNodeKind.GOAL,
        lambda node, change, world: ReconcileDecision(
            node_id=node.id,
            action=ReconcileAction.PROPOSE_INTENT,
            reason="target unmet",
            intents=(Intent(name="adjust"),),
        ),
    )

    first = reconciler.reconcile(invalidation)[0]
    key = ledger.intent_key(goal.id, first.intents[0])
    ledger._proposals[(key, None)] = datetime.now(UTC) - timedelta(seconds=2)
    second = reconciler.reconcile(invalidation)[0]

    assert second.action is ReconcileAction.PROPOSE_INTENT


def test_reconciler_can_require_revision_evidence():
    from voodoo.runtime.reconcile import ReconcileGuard

    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "metric")
    goal = graph.node(ApplicationNodeKind.GOAL, "target")
    graph.connect(goal.id, "observes", resource.id)
    invalidation = InvalidationEngine(graph).invalidate(resource.id)

    decision = Reconciler(graph, guard=ReconcileGuard(require_revision=True)).reconcile(
        invalidation
    )[0]

    assert decision.action is ReconcileAction.WAIT
    assert decision.reason == "fresh revision evidence is required"


def test_reconciler_allows_same_intent_for_new_evidence_revision():
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "metric")
    goal = graph.node(ApplicationNodeKind.GOAL, "target")
    graph.connect(goal.id, "observes", resource.id)
    reconciler = Reconciler(graph).register(
        ApplicationNodeKind.GOAL,
        lambda node, change, world: ReconcileDecision(
            node_id=node.id,
            action=ReconcileAction.PROPOSE_INTENT,
            reason="target unmet",
            intents=(Intent(name="adjust", params={"amount": 1}),),
        ),
    )

    first = InvalidationEngine(graph).invalidate(resource.id, revision="obs-1")
    second = InvalidationEngine(graph).invalidate(resource.id, revision="obs-2")

    assert reconciler.reconcile(first)[0].action is ReconcileAction.PROPOSE_INTENT
    assert reconciler.reconcile(first)[0].action is ReconcileAction.WAIT
    assert reconciler.reconcile(second)[0].action is ReconcileAction.PROPOSE_INTENT


def test_reconciler_blocks_repeated_non_converging_outcome():
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "metric")
    goal = graph.node(ApplicationNodeKind.GOAL, "target")
    graph.connect(goal.id, "observes", resource.id)
    reconciler = Reconciler(
        graph,
        guard=ReconcileGuard(
            suppress_duplicates=False,
            max_repeated_outcomes=2,
        ),
    ).register(
        ApplicationNodeKind.GOAL,
        lambda node, change, world: ReconcileDecision(
            node_id=node.id,
            action=ReconcileAction.PROPOSE_INTENT,
            reason="same unresolved outcome",
            intents=(Intent(name="adjust"),),
        ),
    )
    invalidation = InvalidationEngine(graph).invalidate(resource.id, revision="obs-1")

    assert reconciler.reconcile(invalidation)[0].action is ReconcileAction.PROPOSE_INTENT
    assert reconciler.reconcile(invalidation)[0].action is ReconcileAction.PROPOSE_INTENT
    blocked = reconciler.reconcile(invalidation)[0]

    assert blocked.action is ReconcileAction.BLOCKED
    assert blocked.evidence["repeated_outcomes"] == 3
