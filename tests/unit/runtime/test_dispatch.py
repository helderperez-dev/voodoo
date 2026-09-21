from voodoo.primitives.intent import Intent
from voodoo.runtime.reconciliation import ReconcileAction, ReconcileDecision
from voodoo.runtime.scheduling.dispatch import RuntimeDispatcher
from voodoo.runtime.scheduling.work import WorkEligibility


def test_dispatcher_ignores_non_proposal_decisions():
    decision = ReconcileDecision(
        node_id="goal:x",
        action=ReconcileAction.SATISFIED,
        reason="done",
    )

    assert RuntimeDispatcher().prepare(decision) == ()


def test_dispatcher_prepares_eligible_work_without_executing():
    intent = Intent(name="adjust")
    decision = ReconcileDecision(
        node_id="goal:x",
        action=ReconcileAction.PROPOSE_INTENT,
        reason="target unmet",
        intents=(intent,),
    )

    plan = RuntimeDispatcher().prepare(decision)[0]

    assert plan.scheduling.status is WorkEligibility.ELIGIBLE
    assert plan.placement is None
    assert intent.status.value == "created"


def test_dispatcher_preserves_waiting_scheduler_decision():
    intent = Intent(name="sync")
    decision = ReconcileDecision(
        node_id="goal:x",
        action=ReconcileAction.PROPOSE_INTENT,
        reason="target unmet",
        intents=(intent,),
    )

    from voodoo.runtime.scheduling.work import RuntimeScheduler, ScheduledWork

    work = ScheduledWork(intent=intent, concurrency_key="sync")
    scheduler = RuntimeScheduler()
    assert (
        scheduler.evaluate(work, backpressured={"sync"}).status
        is WorkEligibility.WAITING
    )

    plan = RuntimeDispatcher().prepare(decision)[0]

    # No implicit execution or placement occurs merely because work exists.
    assert plan.placement is None
    assert intent.status.value == "created"
