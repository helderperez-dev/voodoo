from datetime import UTC, datetime, timedelta

from voodoo.primitives.intent import Intent
from voodoo.runtime.work_scheduler import (
    RuntimeScheduler,
    ScheduledWork,
    WorkEligibility,
)


def test_scheduler_separates_time_eligibility_from_execution():
    now = datetime.now(UTC)
    intent = Intent(name="sync")
    work = ScheduledWork(intent=intent, not_before=now + timedelta(minutes=1))

    decision = RuntimeScheduler().evaluate(work, now=now)

    assert decision.status is WorkEligibility.WAITING
    assert intent.status.value == "created"


def test_scheduler_blocks_until_semantic_dependencies_complete():
    intent = Intent(name="publish")
    work = ScheduledWork(intent=intent, dependencies=("prepare",))

    blocked = RuntimeScheduler().evaluate(work, completed=set())
    eligible = RuntimeScheduler().evaluate(work, completed={"prepare"})

    assert blocked.status is WorkEligibility.BLOCKED
    assert eligible.status is WorkEligibility.ELIGIBLE


def test_scheduler_orders_by_priority_then_deadline():
    now = datetime.now(UTC)
    normal = ScheduledWork(
        Intent(name="normal", deadline=now + timedelta(minutes=1)), priority=0
    )
    urgent_later = ScheduledWork(
        Intent(name="urgent-later", deadline=now + timedelta(minutes=5)), priority=10
    )
    urgent_soon = ScheduledWork(
        Intent(name="urgent-soon", deadline=now + timedelta(minutes=2)), priority=10
    )

    ordered = RuntimeScheduler().eligible(
        (normal, urgent_later, urgent_soon), now=now
    )

    assert tuple(item.intent.name for item in ordered) == (
        "urgent-soon",
        "urgent-later",
        "normal",
    )
