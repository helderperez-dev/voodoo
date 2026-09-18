"""Runtime-discovered dependencies and bounded invalidation state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from voodoo.runtime.application_graph import ChangeReason, Invalidation


@dataclass(frozen=True, slots=True)
class DependencyRevision:
    source: str
    revision: str
    reason: ChangeReason
    sequence: int


@dataclass(frozen=True, slots=True)
class DirtyNode:
    node_id: str
    sources: tuple[str, ...]
    reasons: tuple[ChangeReason, ...]
    revision: str | None
    sequence: int


class DependencyGraph:
    """Dynamic dependency overlay kept separate from ApplicationGraph structure."""

    def __init__(self) -> None:
        self._dependencies: dict[str, set[str]] = {}
        self._dependents: dict[str, set[str]] = {}
        self._dirty: dict[str, DirtyNode] = {}
        self._revisions: dict[str, DependencyRevision] = {}
        self._sequence = 0

    def observe(self, consumer: str, source: str) -> None:
        """Record a dependency discovered while the consumer is evaluated."""
        if consumer == source:
            return
        self._dependencies.setdefault(consumer, set()).add(source)
        self._dependents.setdefault(source, set()).add(consumer)

    def replace(self, consumer: str, sources: set[str]) -> None:
        """Replace runtime dependencies after a fresh evaluation."""
        previous = self._dependencies.pop(consumer, set())
        for source in previous:
            dependents = self._dependents.get(source)
            if dependents is not None:
                dependents.discard(consumer)
                if not dependents:
                    self._dependents.pop(source, None)
        for source in sources:
            self.observe(consumer, source)

    def dependencies(self, consumer: str) -> tuple[str, ...]:
        return tuple(sorted(self._dependencies.get(consumer, ())))

    def dependents(self, source: str, *, transitive: bool = False) -> tuple[str, ...]:
        direct = set(self._dependents.get(source, ()))
        if not transitive:
            return tuple(sorted(direct))
        seen: set[str] = set()
        pending = list(direct)
        while pending:
            node_id = pending.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            pending.extend(self._dependents.get(node_id, ()))
        return tuple(sorted(seen))

    def invalidate(
        self,
        source: str,
        *,
        reason: ChangeReason = ChangeReason.STATE,
        revision: str | None = None,
    ) -> Invalidation:
        self._sequence += 1
        sequence = self._sequence
        if revision is not None:
            self._revisions[source] = DependencyRevision(
                source=source,
                revision=revision,
                reason=reason,
                sequence=sequence,
            )
        affected = self.dependents(source, transitive=True)
        for node_id in affected:
            existing = self._dirty.get(node_id)
            sources = set(existing.sources if existing else ())
            reasons = set(existing.reasons if existing else ())
            sources.add(source)
            reasons.add(reason)
            self._dirty[node_id] = DirtyNode(
                node_id=node_id,
                sources=tuple(sorted(sources)),
                reasons=tuple(sorted(reasons, key=lambda item: item.value)),
                revision=revision or (existing.revision if existing else None),
                sequence=sequence,
            )
        return Invalidation(source, affected, reason, revision)

    def dirty(self) -> tuple[DirtyNode, ...]:
        return tuple(sorted(self._dirty.values(), key=lambda item: (item.sequence, item.node_id)))

    def consume(self, node_id: str) -> DirtyNode | None:
        return self._dirty.pop(node_id, None)

    def revision(self, source: str) -> DependencyRevision | None:
        return self._revisions.get(source)

    def explain(self, node_id: str) -> dict[str, Any]:
        dirty = self._dirty.get(node_id)
        return {
            "node_id": node_id,
            "dependencies": list(self.dependencies(node_id)),
            "dirty": dirty is not None,
            "sources": list(dirty.sources) if dirty else [],
            "reasons": [reason.value for reason in dirty.reasons] if dirty else [],
            "revision": dirty.revision if dirty else None,
            "sequence": dirty.sequence if dirty else None,
        }
