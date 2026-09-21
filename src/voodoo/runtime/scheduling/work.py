"""Unified semantic scheduler for Runtime work eligibility.

This scheduler decides *when* work is eligible. Placement decides *where* it
runs, and canonical Execution remains responsible for authority and effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from voodoo.primitives.intent import Intent, IntentStatus
from voodoo.runtime.distributed.fabric import PlacementRequirement


class WorkEligibility(StrEnum):
    ELIGIBLE = "eligible"
    WAITING = "waiting"
    EXPIRED = "expired"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ScheduledWork:
    intent: Intent
    priority: int = 0
    not_before: datetime | None = None
    dependencies: tuple[str, ...] = ()
    placement: PlacementRequirement = field(default_factory=PlacementRequirement)
    concurrency_key: str | None = None
    max_concurrency: int | None = None
    resource_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SchedulingDecision:
    intent_id: str
    status: WorkEligibility
    reason: str
    priority: int
    details: dict[str, Any] = field(default_factory=dict)


class RuntimeScheduler:
    """Deterministic eligibility and ordering over canonical Intents."""

    def evaluate(
        self,
        work: ScheduledWork,
        *,
        completed: set[str] | None = None,
        running: dict[str, int] | None = None,
        unavailable_resources: set[str] | None = None,
        backpressured: set[str] | None = None,
        now: datetime | None = None,
    ) -> SchedulingDecision:
        current = now or datetime.now(UTC)
        completed_ids = completed or set()
        running_counts = running or {}
        unavailable = unavailable_resources or set()
        pressured = backpressured or set()
        if work.intent.status in {
            IntentStatus.COMPLETED,
            IntentStatus.REJECTED,
            IntentStatus.EXPIRED,
            IntentStatus.CANCELLED,
        }:
            return SchedulingDecision(
                work.intent.id,
                WorkEligibility.BLOCKED,
                f"intent is terminal: {work.intent.status.value}",
                work.priority,
                {"intent_status": work.intent.status.value},
            )
        if work.intent.status in {
            IntentStatus.EXECUTING,
            IntentStatus.PAUSED,
        }:
            return SchedulingDecision(
                work.intent.id,
                WorkEligibility.WAITING,
                f"intent is already {work.intent.status.value}",
                work.priority,
                {"intent_status": work.intent.status.value},
            )
        if work.intent.deadline is not None and current >= work.intent.deadline:
            return SchedulingDecision(
                work.intent.id,
                WorkEligibility.EXPIRED,
                "intent deadline has passed",
                work.priority,
                {"deadline": work.intent.deadline.isoformat()},
            )
        if work.not_before is not None and current < work.not_before:
            return SchedulingDecision(
                work.intent.id,
                WorkEligibility.WAITING,
                "work is not eligible yet",
                work.priority,
                {"not_before": work.not_before.isoformat()},
            )
        missing = tuple(item for item in work.dependencies if item not in completed_ids)
        if missing:
            return SchedulingDecision(
                work.intent.id,
                WorkEligibility.BLOCKED,
                f"waiting for dependencies: {', '.join(missing)}",
                work.priority,
            )
        if work.resource_key is not None and work.resource_key in unavailable:
            return SchedulingDecision(
                work.intent.id,
                WorkEligibility.WAITING,
                "required resource is unavailable",
                work.priority,
                {"resource": work.resource_key},
            )
        if work.concurrency_key is not None and work.max_concurrency is not None:
            active = running_counts.get(work.concurrency_key, 0)
            if active >= work.max_concurrency:
                return SchedulingDecision(
                    work.intent.id,
                    WorkEligibility.WAITING,
                    "concurrency limit reached",
                    work.priority,
                    {
                        "concurrency_key": work.concurrency_key,
                        "active": active,
                        "limit": work.max_concurrency,
                    },
                )
        if work.concurrency_key is not None and work.concurrency_key in pressured:
            return SchedulingDecision(
                work.intent.id,
                WorkEligibility.WAITING,
                "work class is backpressured",
                work.priority,
                {"concurrency_key": work.concurrency_key},
            )
        return SchedulingDecision(
            work.intent.id, WorkEligibility.ELIGIBLE, "work is eligible", work.priority
        )

    def explain(
        self,
        work: ScheduledWork,
        *,
        completed: set[str] | None = None,
        running: dict[str, int] | None = None,
        unavailable_resources: set[str] | None = None,
        backpressured: set[str] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        decision = self.evaluate(
            work,
            completed=completed,
            running=running,
            unavailable_resources=unavailable_resources,
            backpressured=backpressured,
            now=now,
        )
        return {
            "intent_id": decision.intent_id,
            "status": decision.status.value,
            "reason": decision.reason,
            "priority": decision.priority,
            "details": dict(decision.details),
            "dependencies": list(work.dependencies),
            "placement": {
                "capability": work.placement.capability,
                "capabilities": list(work.placement.capabilities),
                "service": work.placement.service,
                "owner": work.placement.owner,
                "location": work.placement.location,
                "preferred_node": work.placement.preferred_node,
            },
        }

    def eligible(
        self,
        work: tuple[ScheduledWork, ...],
        *,
        completed: set[str] | None = None,
        running: dict[str, int] | None = None,
        unavailable_resources: set[str] | None = None,
        backpressured: set[str] | None = None,
        now: datetime | None = None,
    ) -> tuple[ScheduledWork, ...]:
        current = now or datetime.now(UTC)
        selected = [
            item
            for item in work
            if self.evaluate(
                item,
                completed=completed,
                running=running,
                unavailable_resources=unavailable_resources,
                backpressured=backpressured,
                now=current,
            ).status
            is WorkEligibility.ELIGIBLE
        ]
        selected.sort(
            key=lambda item: (
                -item.priority,
                item.intent.deadline or datetime.max.replace(tzinfo=UTC),
                item.intent.created_at,
                item.intent.id,
            )
        )
        return tuple(selected)


def _normalize_not_before(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("_not_before must be an ISO-8601 datetime") from exc
    if value is not None and not isinstance(value, datetime):
        raise TypeError("_not_before must be a datetime or ISO-8601 string")
    if value is None:
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _placement_from_intent(intent: Intent) -> tuple[PlacementRequirement, str | None]:
    placement_kwargs: dict[str, Any] = {}
    resource_key: str | None = None
    for constraint in intent.constraints:
        if constraint.operator != "==":
            continue
        if constraint.kind == "locality":
            placement_kwargs["location"] = str(constraint.value)
        elif constraint.kind == "resource":
            resource_key = str(constraint.value)
        elif constraint.kind == "service":
            placement_kwargs["service"] = str(constraint.value)
    if intent.requires:
        placement_kwargs["capability"] = intent.requires[0]
        placement_kwargs["capabilities"] = tuple(intent.requires)
    return PlacementRequirement(**placement_kwargs), resource_key


def scheduled_work_from_intent(intent: Intent) -> ScheduledWork:
    """Translate canonical Intent semantics into scheduler/placement semantics."""
    concurrency_key = intent.params.get("_concurrency_key")
    max_concurrency = intent.params.get("_max_concurrency")
    priority = int(intent.params.get("_priority", 0))
    not_before = _normalize_not_before(intent.params.get("_not_before"))
    dependencies = tuple(str(item) for item in intent.params.get("_dependencies", ()))
    placement, resource_key = _placement_from_intent(intent)

    return ScheduledWork(
        intent=intent,
        priority=priority,
        not_before=not_before,
        dependencies=dependencies,
        placement=placement,
        concurrency_key=str(concurrency_key) if concurrency_key is not None else None,
        max_concurrency=int(max_concurrency) if max_concurrency is not None else None,
        resource_key=resource_key,
    )


__all__ = [
    "RuntimeScheduler",
    "ScheduledWork",
    "scheduled_work_from_intent",
    "SchedulingDecision",
    "WorkEligibility",
]
