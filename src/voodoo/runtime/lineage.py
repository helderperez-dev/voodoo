"""Causal lineage records for Runtime inspection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class LineageEvent:
    kind: str
    subject_id: str
    reason: str
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RuntimeLineage:
    """Append-only in-process causal index; durable stores may mirror it."""

    def __init__(self) -> None:
        self._events: list[LineageEvent] = []

    def record(self, event: LineageEvent) -> LineageEvent:
        self._events.append(event)
        return event

    def events(self) -> tuple[LineageEvent, ...]:
        return tuple(self._events)

    def clear(self) -> None:
        self._events.clear()

    def record_transition(
        self,
        kind: str,
        subject_id: str,
        *,
        parent_id: str | None,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> LineageEvent:
        return self.record(
            LineageEvent(
                kind=kind,
                subject_id=subject_id,
                parent_id=parent_id,
                reason=reason,
                metadata=metadata or {},
            )
        )

    def why(self, subject_id: str) -> tuple[LineageEvent, ...]:
        by_subject: dict[str, list[LineageEvent]] = {}
        for event in self._events:
            by_subject.setdefault(event.subject_id, []).append(event)
        result: list[LineageEvent] = []
        pending = [subject_id]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            for event in by_subject.get(current, ()):
                result.append(event)
                if event.parent_id is not None:
                    pending.append(event.parent_id)
        return tuple(result)

    def chain(self, subject_id: str) -> tuple[str, ...]:
        """Return causal subject ids from root cause to requested subject."""
        events = self.why(subject_id)
        parents = {event.subject_id: event.parent_id for event in events}
        chain = [subject_id]
        current = subject_id
        seen = {subject_id}
        while (parent := parents.get(current)) is not None and parent not in seen:
            chain.append(parent)
            seen.add(parent)
            current = parent
        chain.reverse()
        return tuple(chain)

    def describe(self, subject_id: str) -> list[dict[str, Any]]:
        return [
            {
                "kind": event.kind,
                "subject_id": event.subject_id,
                "reason": event.reason,
                "parent_id": event.parent_id,
                "metadata": dict(event.metadata),
                "recorded_at": event.recorded_at.isoformat(),
            }
            for event in self.why(subject_id)
        ]


lineage = RuntimeLineage()

__all__ = ["LineageEvent", "RuntimeLineage", "lineage"]
