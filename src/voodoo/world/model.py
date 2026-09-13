"""Semantic world projection and query service.

``WorldModel`` is intentionally small: it projects append-only observations
onto current entity properties, maintains typed relationships, and exposes
queries useful to planners, policies, agents, and Edge adapters.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from voodoo.world.models import Entity, Observation, Relationship, WorldSnapshot
from voodoo.world.store import InMemoryWorldStore, WorldStore

__all__ = ["WorldModel"]


class WorldModel:
    """Current world projection over a pluggable :class:`WorldStore`.

    The model never treats a desired Effect as observed truth. Callers must feed
    actual evidence through :meth:`observe` (for example from telemetry or an
    Effect ACK) before the projected entity state changes.
    """

    def __init__(self, store: WorldStore | None = None) -> None:
        self.store: WorldStore = store or InMemoryWorldStore()

    def put_entity(self, entity: Entity) -> Entity:
        """Create or replace a stable entity record."""
        self.store.put_entity(entity)
        stored = self.store.get_entity(entity.id)
        assert stored is not None
        return stored

    def entity(self, entity_id: str) -> Entity | None:
        """Return one entity's current projected state."""
        return self.store.get_entity(entity_id)

    def entities(self, *, entity_type: str | None = None) -> list[Entity]:
        """List known entities, optionally restricted by semantic type."""
        return self.store.list_entities(entity_type=entity_type)

    def relate(
        self,
        source_id: str,
        predicate: str,
        target_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        relationship_id: str | None = None,
    ) -> Relationship:
        """Create a typed directed relationship between two known entities."""
        self._require_entity(source_id)
        self._require_entity(target_id)
        if relationship_id is None:
            relationship = Relationship(
                source_id=source_id,
                predicate=predicate,
                target_id=target_id,
                metadata=dict(metadata or {}),
            )
        else:
            relationship = Relationship(
                id=relationship_id,
                source_id=source_id,
                predicate=predicate,
                target_id=target_id,
                metadata=dict(metadata or {}),
            )
        self.store.put_relationship(relationship)
        return deepcopy(relationship)

    def relationships(
        self,
        entity_id: str,
        *,
        predicate: str | None = None,
        direction: str = "both",
    ) -> list[Relationship]:
        """Return typed edges touching an entity."""
        self._require_entity(entity_id)
        return self.store.list_relationships(
            entity_id, predicate=predicate, direction=direction
        )

    def neighbors(
        self,
        entity_id: str,
        *,
        predicate: str | None = None,
        direction: str = "both",
        entity_type: str | None = None,
    ) -> list[Entity]:
        """Resolve relationship endpoints to neighboring entities."""
        relationships = self.relationships(
            entity_id, predicate=predicate, direction=direction
        )
        seen: set[str] = set()
        result: list[Entity] = []
        for relationship in relationships:
            other_id = (
                relationship.target_id
                if relationship.source_id == entity_id
                else relationship.source_id
            )
            if other_id in seen:
                continue
            other = self.store.get_entity(other_id)
            if other is None:
                continue
            if entity_type is not None and other.type != entity_type:
                continue
            seen.add(other_id)
            result.append(other)
        return result

    def observe(
        self,
        entity_id: str,
        property: str,
        value: Any,
        *,
        source: str,
        confidence: float = 1.0,
        observed_at: datetime | None = None,
        trace_id: str | None = None,
        execution_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        observation_id: str | None = None,
        force_projection: bool = False,
    ) -> Observation:
        """Append evidence and project it onto current state when it is current.

        Stale evidence is retained in history but does not overwrite a newer
        projected value. ``force_projection`` is an explicit escape hatch for
        reconciliation/import tooling and should not be used for normal device
        telemetry.
        """
        entity = self._require_entity(entity_id)
        previous = self.history(entity_id, property)
        if observation_id is not None:
            duplicate = next(
                (item for item in previous if item.id == observation_id), None
            )
            if duplicate is not None:
                return duplicate
        latest = previous[-1] if previous else None

        kwargs: dict[str, Any] = {
            "entity_id": entity_id,
            "property": property,
            "value": value,
            "source": source,
            "confidence": confidence,
            "trace_id": trace_id,
            "execution_id": execution_id,
            "metadata": dict(metadata or {}),
        }
        if observed_at is not None:
            kwargs["observed_at"] = observed_at
        if observation_id is not None:
            kwargs["id"] = observation_id
        observation = Observation(**kwargs)
        self.store.append_observation(observation)

        is_current = latest is None or observation.observed_at >= latest.observed_at
        if force_projection or is_current:
            entity.set(property, value)
            self.store.put_entity(entity)

        return deepcopy(observation)

    def history(self, entity_id: str, property: str | None = None) -> list[Observation]:
        """Return observation history ordered by source/event time."""
        self._require_entity(entity_id)
        return self.store.list_observations(entity_id, property=property)

    def snapshot(self, entity_id: str) -> WorldSnapshot:
        """Build a reasoning/policy snapshot for one entity."""
        entity = self._require_entity(entity_id)
        observations = self.history(entity_id)
        latest: dict[str, Observation] = {}
        for observation in observations:
            current = latest.get(observation.property)
            if current is None or observation.observed_at >= current.observed_at:
                latest[observation.property] = observation
        return WorldSnapshot(
            entity=entity,
            relationships=self.relationships(entity_id),
            latest_observations=latest,
        )

    def _require_entity(self, entity_id: str) -> Entity:
        entity = self.store.get_entity(entity_id)
        if entity is None:
            raise KeyError(f"unknown world entity: {entity_id}")
        return entity
