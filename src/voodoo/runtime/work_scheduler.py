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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SchedulingDecision:
    intent_id: str
    status: WorkEligibility
    reason: str
    priority: int


class RuntimeScheduler:
    """Deterministic eligibility and ordering over canonical Intents."""

    def evaluate(
        self,
        work: ScheduledWork,
        *,
        completed: set[str] | None = None,
        now: datetime | None = None,
    ) -> SchedulingDecision:
        current = now or datetime.now(UTC)
        completed_ids = completed or set()
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
        return SchedulingDecision(
            work.intent.id, WorkEligibility.ELIGIBLE, "work is eligible", work.priority
        )

    def eligible(
        self,
        work: tuple[ScheduledWork, ...],
        *,
        completed: set[str] | None = None,
        now: datetime | None = None,
    ) -> tuple[ScheduledWork, ...]:
        current = now or datetime.now(UTC)
        selected = [
            item
            for item in work
            if self.evaluate(item, completed=completed, now=current).status
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
