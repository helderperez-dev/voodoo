"""SQLite-backed memory store with FTS5 for full-text search (Sprint 16).

The default memory backend. Uses a single ``memory`` table for structured
data and a ``memory_fts`` FTS5 virtual table for full-text search. FTS5 is
built into Python's ``sqlite3`` module — no new dependencies.

WAL mode and ``busy_timeout=5000`` match the execution store pattern.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voodoo.memory.interfaces import (
    MemoryEntry,
    MemoryLayer,
    MemorySearchResult,
)

__all__ = ["SQLiteMemoryStore"]

# Memory migration version — follows the execution migration numbering.
MEMORY_MIGRATION_VERSION = 10

MEMORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL DEFAULT 'default',
    layer TEXT NOT NULL DEFAULT 'durable',
    content TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    tags TEXT NOT NULL DEFAULT '[]',
    source_execution_id TEXT,
    importance REAL NOT NULL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT
)
"""

MEMORY_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content,
    tags,
    content=memory,
    content_rowid=rowid
)
"""

MEMORY_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_memory_entity ON memory (entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory (layer)",
    "CREATE INDEX IF NOT EXISTS idx_memory_source_exec ON memory (source_execution_id)",
)

# Triggers to keep FTS in sync with the memory table.
MEMORY_TRIGGERS_SQL = (
    """
    CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
        INSERT INTO memory_fts(rowid, content, tags)
        VALUES (new.rowid, new.content, new.tags);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content, tags)
        VALUES ('delete', old.rowid, old.content, old.tags);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content, tags)
        VALUES ('delete', old.rowid, old.content, old.tags);
        INSERT INTO memory_fts(rowid, content, tags)
        VALUES (new.rowid, new.content, new.tags);
    END
    """,
)


class SQLiteMemoryStore:
    """Durable memory store backed by SQLite with FTS5.

    Implements the ``MemoryStore`` protocol. The store owns its own sync
    ``sqlite3`` connection — memory reads/writes must not require the async
    VoodooDatabase lifecycle.

    Parameters
    ----------
    path:
        Path to the SQLite database file. Created if it does not exist.
    """

    provider = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._migrate()

    def _migrate(self) -> None:
        """Create tables idempotently."""
        self._conn.execute(MEMORY_TABLE_SQL)
        # FTS5 — may not be available in all SQLite builds. If it fails,
        # we degrade gracefully (search falls back to LIKE).
        try:
            self._conn.execute(MEMORY_FTS_SQL)
            for trigger in MEMORY_TRIGGERS_SQL:
                self._conn.execute(trigger)
            self._has_fts = True
        except sqlite3.OperationalError:
            self._has_fts = False
        for idx in MEMORY_INDEXES_SQL:
            self._conn.execute(idx)
        self._conn.commit()

    # -- MemoryStore protocol ---------------------------------------------

    def write(self, entry: MemoryEntry) -> str:
        """Write (upsert) a memory entry."""
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT INTO memory (id, entity_id, layer, content, metadata, tags,
                source_execution_id, importance, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                entity_id = excluded.entity_id,
                layer = excluded.layer,
                content = excluded.content,
                metadata = excluded.metadata,
                tags = excluded.tags,
                source_execution_id = excluded.source_execution_id,
                importance = excluded.importance,
                updated_at = excluded.updated_at,
                expires_at = excluded.expires_at
            """,
            (
                entry.id,
                entry.entity_id,
                entry.layer.value
                if isinstance(entry.layer, MemoryLayer)
                else entry.layer,
                entry.content,
                json.dumps(entry.metadata),
                json.dumps(entry.tags),
                entry.source_execution_id,
                entry.importance,
                entry.created_at.isoformat(),
                now,
                entry.expires_at.isoformat() if entry.expires_at else None,
            ),
        )
        self._conn.commit()
        return entry.id

    def read(self, entry_id: str) -> MemoryEntry | None:
        """Read a single memory entry by id."""
        row = self._conn.execute(
            "SELECT * FROM memory WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def search(
        self,
        query: str,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """Search memory by text query.

        Uses FTS5 when available, falls back to LIKE otherwise.
        """
        if not query.strip():
            return []

        if self._has_fts:
            return self._search_fts(query, entity_id, layers, tags, limit)
        return self._search_like(query, entity_id, layers, tags, limit)

    def _search_fts(
        self,
        query: str,
        entity_id: str | None,
        layers: list[MemoryLayer] | None,
        tags: list[str] | None,
        limit: int,
    ) -> list[MemorySearchResult]:
        """FTS5-based full-text search."""
        # Build the FTS query — quote terms for phrase matching.
        fts_query = " OR ".join(f'"{term}"' for term in query.split() if term.strip())
        if not fts_query:
            return []

        sql = """
            SELECT m.*, rank
            FROM memory_fts fts
            JOIN memory m ON m.rowid = fts.rowid
            WHERE memory_fts MATCH ?
        """
        params: list[Any] = [fts_query]

        if entity_id:
            sql += " AND m.entity_id = ?"
            params.append(entity_id)
        if layers:
            layer_vals = [lv.value for lv in layers]
            placeholders = ",".join("?" for _ in layer_vals)
            sql += f" AND m.layer IN ({placeholders})"
            params.extend(layer_vals)
        if tags:
            for tag in tags:
                sql += " AND m.tags LIKE ?"
                params.append(f"%{tag}%")

        # FTS5 rank is negative (lower = more relevant). We negate and
        # normalize to 0–1.
        sql += " ORDER BY rank ASC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        if not rows:
            return []

        # Normalize scores: rank is negative, most negative = best.
        best_rank = abs(rows[0]["rank"]) if rows[0]["rank"] else 1.0
        results: list[MemorySearchResult] = []
        for row in rows:
            rank = abs(row["rank"]) if row["rank"] else 1.0
            score = min(1.0, best_rank / rank) if rank > 0 else 1.0
            entry = self._row_to_entry(row)
            snippet = entry.content[:200]
            results.append(
                MemorySearchResult(entry=entry, score=score, snippet=snippet)
            )
        return results

    def _search_like(
        self,
        query: str,
        entity_id: str | None,
        layers: list[MemoryLayer] | None,
        tags: list[str] | None,
        limit: int,
    ) -> list[MemorySearchResult]:
        """Fallback LIKE-based search when FTS5 is unavailable."""
        sql = "SELECT * FROM memory WHERE content LIKE ?"
        params: list[Any] = [f"%{query}%"]

        if entity_id:
            sql += " AND entity_id = ?"
            params.append(entity_id)
        if layers:
            layer_vals = [lv.value for lv in layers]
            placeholders = ",".join("?" for _ in layer_vals)
            sql += f" AND layer IN ({placeholders})"
            params.extend(layer_vals)
        if tags:
            for tag in tags:
                sql += " AND tags LIKE ?"
                params.append(f"%{tag}%")

        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        results: list[MemorySearchResult] = []
        for row in rows:
            entry = self._row_to_entry(row)
            snippet = entry.content[:200]
            results.append(
                MemorySearchResult(entry=entry, score=entry.importance, snippet=snippet)
            )
        return results

    def list_entries(
        self,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        """List memory entries with optional filters."""
        sql = "SELECT * FROM memory WHERE 1=1"
        params: list[Any] = []

        if entity_id:
            sql += " AND entity_id = ?"
            params.append(entity_id)
        if layers:
            layer_vals = [lv.value for lv in layers]
            placeholders = ",".join("?" for _ in layer_vals)
            sql += f" AND layer IN ({placeholders})"
            params.extend(layer_vals)
        if tags:
            for tag in tags:
                sql += " AND tags LIKE ?"
                params.append(f"%{tag}%")

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry. Returns True if found and deleted."""
        cursor = self._conn.execute("DELETE FROM memory WHERE id = ?", (entry_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def count(
        self,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
    ) -> int:
        """Count memory entries with optional filters."""
        sql = "SELECT COUNT(*) FROM memory WHERE 1=1"
        params: list[Any] = []

        if entity_id:
            sql += " AND entity_id = ?"
            params.append(entity_id)
        if layers:
            layer_vals = [lv.value for lv in layers]
            placeholders = ",".join("?" for _ in layer_vals)
            sql += f" AND layer IN ({placeholders})"
            params.extend(layer_vals)

        row = self._conn.execute(sql, params).fetchone()
        return row[0] if row else 0

    # -- helpers -----------------------------------------------------------

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert a SQLite row to a MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            entity_id=row["entity_id"],
            layer=MemoryLayer(row["layer"]),
            content=row["content"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source_execution_id=row["source_execution_id"],
            importance=row["importance"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            expires_at=(
                datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            ),
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
