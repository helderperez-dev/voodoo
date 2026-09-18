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


def test_scheduler_preserves_placement_without_deciding_location():
    from voodoo.runtime.fabric import PlacementRequirement

    requirement = PlacementRequirement(capability="camera", location="edge")
    work = ScheduledWork(Intent(name="capture"), placement=requirement)

    eligible = RuntimeScheduler().eligible((work,))

    assert eligible[0].placement is requirement
    assert not hasattr(eligible[0], "node_id")


def test_scheduler_waits_for_unavailable_resource():
    work = ScheduledWork(Intent(name="render"), resource_key="gpu")

    decision = RuntimeScheduler().evaluate(
        work, unavailable_resources={"gpu"}
    )

    assert decision.status is WorkEligibility.WAITING
    assert decision.details == {"resource": "gpu"}


def test_scheduler_enforces_concurrency_limit():
    work = ScheduledWork(
        Intent(name="send"),
        concurrency_key="outbound",
        max_concurrency=2,
    )

    decision = RuntimeScheduler().evaluate(work, running={"outbound": 2})

    assert decision.status is WorkEligibility.WAITING
    assert decision.reason == "concurrency limit reached"
    assert decision.details["limit"] == 2


def test_scheduler_respects_backpressure_without_rejecting_work():
    work = ScheduledWork(Intent(name="sync"), concurrency_key="sync")

    decision = RuntimeScheduler().evaluate(work, backpressured={"sync"})

    assert decision.status is WorkEligibility.WAITING
    assert decision.reason == "work class is backpressured"
    assert work.intent.status.value == "created"


def test_scheduler_explains_placement_without_selecting_node():
    from voodoo.runtime.fabric import PlacementRequirement

    work = ScheduledWork(
        Intent(name="capture"),
        placement=PlacementRequirement(capability="camera", location="edge"),
    )

    explanation = RuntimeScheduler().explain(work)

    assert explanation["status"] == "eligible"
    assert explanation["placement"]["capability"] == "camera"
    assert explanation["placement"]["location"] == "edge"
    assert "node_id" not in explanation["placement"]


def test_scheduled_work_derives_intent_semantics():
    from voodoo.primitives.constraint import Constraint
    from voodoo.runtime.work_scheduler import scheduled_work_from_intent

    intent = Intent(
        name="capture",
        params={
            "_priority": 7,
            "_dependencies": ["boot"],
            "_concurrency_key": "camera",
            "_max_concurrency": 1,
        },
        constraints=[Constraint.locality("edge")],
    ).require("camera.capture")

    work = scheduled_work_from_intent(intent)

    assert work.priority == 7
    assert work.dependencies == ("boot",)
    assert work.concurrency_key == "camera"
    assert work.max_concurrency == 1
    assert work.placement.capability == "camera.capture"
    assert work.placement.location == "edge"
