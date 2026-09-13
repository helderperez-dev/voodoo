"""Durable SQLite storage for Voodoo world state.

The store persists entities, typed relationships, and append-only observations.
Projection semantics remain in :mod:`voodoo.world.model`; this module only
implements the :class:`~voodoo.world.store.WorldStore` contract.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from voodoo.world.models import Entity, Observation, Relationship

__all__ = ["SQLiteWorldStore"]


_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS world_entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    properties TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS world_relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    target_id TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES world_entities(id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES world_entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_world_relationships_source
    ON world_relationships(source_id, predicate);
CREATE INDEX IF NOT EXISTS idx_world_relationships_target
    ON world_relationships(target_id, predicate);

CREATE TABLE IF NOT EXISTS world_observations (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    property TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL,
    observed_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    trace_id TEXT,
    execution_id TEXT,
    metadata TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES world_entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_world_observations_entity_property_time
    ON world_observations(entity_id, property, observed_at, id);
"""


def _dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _load(value: str) -> Any:
    return json.loads(value)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SQLiteWorldStore:
    """SQLite-backed implementation of the world persistence contract.

    SQLite is deliberately the default durable implementation for the world
    layer: it keeps local development zero-infrastructure while preserving the
    exact same ``WorldStore`` semantics a production adapter must implement.
    """

    def __init__(self, path: str = "data/world.db") -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def put_entity(self, entity: Entity) -> None:
        self._conn.execute(
            """
            INSERT INTO world_entities
                (id, type, properties, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                properties=excluded.properties,
                metadata=excluded.metadata,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at
            """,
            (
                entity.id,
                entity.type,
                _dump(entity.properties),
                _dump(entity.metadata),
                entity.created_at.isoformat(),
                entity.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_entity(self, entity_id: str) -> Entity | None:
        row = self._conn.execute(
            "SELECT * FROM world_entities WHERE id = ?", (entity_id,)
        ).fetchone()
        return self._entity(row) if row is not None else None

    def list_entities(self, *, entity_type: str | None = None) -> list[Entity]:
        if entity_type is None:
            rows = self._conn.execute(
                "SELECT * FROM world_entities ORDER BY created_at, id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM world_entities WHERE type = ? ORDER BY created_at, id",
                (entity_type,),
            ).fetchall()
        return [self._entity(row) for row in rows]

    def put_relationship(self, relationship: Relationship) -> None:
        self._conn.execute(
            """
            INSERT INTO world_relationships
                (id, source_id, predicate, target_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_id=excluded.source_id,
                predicate=excluded.predicate,
                target_id=excluded.target_id,
                metadata=excluded.metadata,
                created_at=excluded.created_at
            """,
            (
                relationship.id,
                relationship.source_id,
                relationship.predicate,
                relationship.target_id,
                _dump(relationship.metadata),
                relationship.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def list_relationships(
        self,
        entity_id: str,
        *,
        predicate: str | None = None,
        direction: str = "both",
    ) -> list[Relationship]:
        if direction not in {"in", "out", "both"}:
            raise ValueError("direction must be 'in', 'out', or 'both'")

        clauses: list[str] = []
        params: list[Any] = []
        if direction == "in":
            clauses.append("target_id = ?")
            params.append(entity_id)
        elif direction == "out":
            clauses.append("source_id = ?")
            params.append(entity_id)
        else:
            clauses.append("(source_id = ? OR target_id = ?)")
            params.extend([entity_id, entity_id])
        if predicate is not None:
            clauses.append("predicate = ?")
            params.append(predicate)

        rows = self._conn.execute(
            "SELECT * FROM world_relationships WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at, id",
            params,
        ).fetchall()
        return [self._relationship(row) for row in rows]

    def append_observation(self, observation: Observation) -> None:
        # INSERT OR IGNORE makes observation identity the idempotency key.
        self._conn.execute(
            """
            INSERT OR IGNORE INTO world_observations
                (id, entity_id, property, value, source, confidence,
                 observed_at, received_at, trace_id, execution_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.id,
                observation.entity_id,
                observation.property,
                _dump(observation.value),
                observation.source,
                observation.confidence,
                observation.observed_at.isoformat(),
                observation.received_at.isoformat(),
                observation.trace_id,
                observation.execution_id,
                _dump(observation.metadata),
            ),
        )
        self._conn.commit()

    def list_observations(
        self,
        entity_id: str,
        *,
        property: str | None = None,
    ) -> list[Observation]:
        if property is None:
            rows = self._conn.execute(
                """
                SELECT * FROM world_observations
                WHERE entity_id = ?
                ORDER BY observed_at, id
                """,
                (entity_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM world_observations
                WHERE entity_id = ? AND property = ?
                ORDER BY observed_at, id
                """,
                (entity_id, property),
            ).fetchall()
        return [self._observation(row) for row in rows]

    @staticmethod
    def _entity(row: sqlite3.Row) -> Entity:
        return Entity(
            id=row["id"],
            type=row["type"],
            properties=_load(row["properties"]),
            metadata=_load(row["metadata"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    @staticmethod
    def _relationship(row: sqlite3.Row) -> Relationship:
        return Relationship(
            id=row["id"],
            source_id=row["source_id"],
            predicate=row["predicate"],
            target_id=row["target_id"],
            metadata=_load(row["metadata"]),
            created_at=_dt(row["created_at"]),
        )

    @staticmethod
    def _observation(row: sqlite3.Row) -> Observation:
        return Observation(
            id=row["id"],
            entity_id=row["entity_id"],
            property=row["property"],
            value=_load(row["value"]),
            source=row["source"],
            confidence=float(row["confidence"]),
            observed_at=_dt(row["observed_at"]),
            received_at=_dt(row["received_at"]),
            trace_id=row["trace_id"],
            execution_id=row["execution_id"],
            metadata=_load(row["metadata"]),
        )
