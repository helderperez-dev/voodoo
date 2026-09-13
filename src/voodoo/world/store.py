"""Persistence contract for Voodoo world state.

The store keeps ontology records; projection semantics live in ``WorldModel``.
Backends must preserve append-only observations and stable relationship IDs.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from voodoo.world.models import Entity, Observation, Relationship

__all__ = ["WorldStore", "InMemoryWorldStore"]


class WorldStore(Protocol):
    """Minimal persistence surface required by :class:`WorldModel`."""

    def put_entity(self, entity: Entity) -> None: ...

    def get_entity(self, entity_id: str) -> Entity | None: ...

    def list_entities(self, *, entity_type: str | None = None) -> list[Entity]: ...

    def put_relationship(self, relationship: Relationship) -> None: ...

    def list_relationships(
        self,
        entity_id: str,
        *,
        predicate: str | None = None,
        direction: str = "both",
    ) -> list[Relationship]: ...

    def append_observation(self, observation: Observation) -> None: ...

    def list_observations(
        self,
        entity_id: str,
        *,
        property: str | None = None,
    ) -> list[Observation]: ...


class InMemoryWorldStore:
    """Dependency-free world store for local use and contract tests."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
        self._observations: dict[str, Observation] = {}

    def put_entity(self, entity: Entity) -> None:
        self._entities[entity.id] = deepcopy(entity)

    def get_entity(self, entity_id: str) -> Entity | None:
        entity = self._entities.get(entity_id)
        return deepcopy(entity) if entity is not None else None

    def list_entities(self, *, entity_type: str | None = None) -> list[Entity]:
        entities = self._entities.values()
        if entity_type is not None:
            entities = (e for e in entities if e.type == entity_type)
        return [deepcopy(e) for e in entities]

    def put_relationship(self, relationship: Relationship) -> None:
        self._relationships[relationship.id] = deepcopy(relationship)

    def list_relationships(
        self,
        entity_id: str,
        *,
        predicate: str | None = None,
        direction: str = "both",
    ) -> list[Relationship]:
        if direction not in {"in", "out", "both"}:
            raise ValueError("direction must be 'in', 'out', or 'both'")

        result: list[Relationship] = []
        for relationship in self._relationships.values():
            if predicate is not None and relationship.predicate != predicate:
                continue
            outbound = relationship.source_id == entity_id
            inbound = relationship.target_id == entity_id
            if direction == "out" and outbound:
                result.append(deepcopy(relationship))
            elif direction == "in" and inbound:
                result.append(deepcopy(relationship))
            elif direction == "both" and (outbound or inbound):
                result.append(deepcopy(relationship))
        return result

    def append_observation(self, observation: Observation) -> None:
        if observation.id in self._observations:
            # Idempotency by observation identity. A duplicated transport
            # delivery must not create duplicate historical evidence.
            return
        self._observations[observation.id] = deepcopy(observation)

    def list_observations(
        self,
        entity_id: str,
        *,
        property: str | None = None,
    ) -> list[Observation]:
        observations = [
            observation
            for observation in self._observations.values()
            if observation.entity_id == entity_id
            and (property is None or observation.property == property)
        ]
        observations.sort(key=lambda observation: (observation.observed_at, observation.id))
        return [deepcopy(observation) for observation in observations]
