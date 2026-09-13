"""World-model primitives for Voodoo's agency layer.

The world layer deliberately separates identity, relationships, and evidence:

- ``Entity`` is stable identity plus the current projected properties.
- ``Relationship`` is a typed directed edge between entities.
- ``Observation`` is append-only evidence about an entity property.
- ``WorldSnapshot`` is a read projection suitable for reasoning/policy.

Observations are facts *reported by a source*; they are not commands and they
are not automatically true merely because an Effect was issued.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

__all__ = ["Entity", "Relationship", "Observation", "WorldSnapshot"]


def _now() -> datetime:
    return datetime.now(UTC)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass
class Entity:
    """A stable thing known to the Voodoo world model.

    ``properties`` contains the current projection of observed state. Historical
    evidence lives in ``Observation`` records, never inside this mapping.
    """

    type: str
    id: str = field(default_factory=lambda: _id("ent"))
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def get(self, path: str, default: Any = None) -> Any:
        """Read a dotted property path from the current projection."""
        node: Any = self.properties
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value: Any) -> None:
        """Set a dotted property path on the current projection."""
        if not path or any(not part for part in path.split(".")):
            raise ValueError("property path must contain non-empty segments")
        parts = path.split(".")
        node = self.properties
        for part in parts[:-1]:
            child = node.get(part)
            if child is None:
                child = {}
                node[part] = child
            if not isinstance(child, dict):
                raise ValueError(
                    f"cannot set {path!r}: segment {part!r} is not an object"
                )
            node = child
        node[parts[-1]] = deepcopy(value)
        self.updated_at = _now()


@dataclass
class Relationship:
    """A typed, directed relationship between two entities."""

    source_id: str
    predicate: str
    target_id: str
    id: str = field(default_factory=lambda: _id("rel"))
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise ValueError("relationship endpoints must be non-empty")
        if not self.predicate or "." == self.predicate:
            raise ValueError("relationship predicate must be non-empty")


@dataclass
class Observation:
    """Append-only evidence about one property of an entity.

    ``confidence`` is normalized to the inclusive range 0..1. ``observed_at``
    is source/event time; ``received_at`` is when the runtime ingested it.
    Keeping both allows the world projection to reject stale evidence while
    retaining it in history.
    """

    entity_id: str
    property: str
    value: Any
    source: str
    confidence: float = 1.0
    observed_at: datetime = field(default_factory=_now)
    received_at: datetime = field(default_factory=_now)
    trace_id: str | None = None
    execution_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: _id("obs"))

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("observation entity_id must be non-empty")
        if not self.property or any(not p for p in self.property.split(".")):
            raise ValueError("observation property must be a valid dotted path")
        if not self.source:
            raise ValueError("observation source must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("observation confidence must be between 0 and 1")
        if self.observed_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("observation timestamps must be timezone-aware")


@dataclass
class WorldSnapshot:
    """Immutable-by-convention reasoning projection for one entity."""

    entity: Entity
    relationships: list[Relationship] = field(default_factory=list)
    latest_observations: dict[str, Observation] = field(default_factory=dict)
    captured_at: datetime = field(default_factory=_now)
