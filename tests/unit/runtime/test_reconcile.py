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
