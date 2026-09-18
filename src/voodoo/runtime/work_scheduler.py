"""Unified semantic scheduler for Runtime work eligibility.

This scheduler decides *when* work is eligible. Placement decides *where* it
runs, and canonical Execution remains responsible for authority and effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from voodoo.primitives.intent import Intent
from voodoo.runtime.fabric import PlacementRequirement


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
        if work.intent.expired:
            return SchedulingDecision(
                work.intent.id, WorkEligibility.EXPIRED, "intent deadline passed", work.priority
            )
        if work.not_before is not None and current < work.not_before:
            return SchedulingDecision(
                work.intent.id, WorkEligibility.WAITING, "not_before has not arrived", work.priority
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


__all__ = [
    "RuntimeScheduler",
    "ScheduledWork",
    "SchedulingDecision",
    "WorkEligibility",
]
