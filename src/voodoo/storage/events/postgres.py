"""Durable PostgreSQL event bus (Sprint 7, Sprint 11).

Same log + replay semantics as :class:`~voodoo.storage.events.sqlite.SQLiteEventBus`
— events are rows in the shared ``events`` table (framework migration v6),
subscribers are notified in-process after a durable publish, and ``replay``
re-reads history in timestamp order. Because the ``VoodooEventBus`` protocol
is *synchronous* (publish/subscribe/replay are blocking), this adapter owns
its own psycopg (sync) connection instead of reusing the async
``PostgresDatabase`` connection, mirroring how the SQLite bus owns a
``sqlite3.Connection``.

Database-connection sharing is still default-on: no async event-loop
dependency, identical call sites for applications, and the registry creates
one instance per configuration. Durability is guaranteed by commit after
INSERT.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING, Any

from voodoo.adapters.capabilities import EventBusCapabilities
from voodoo.storage.database.interfaces import Migration
from voodoo.storage.database.sqlite import register_framework_migration
from voodoo.storage.events.interfaces import VoodooEventBus

EVENTS_MIGRATION_VERSION = 6

EVENTS_MIGRATION = Migration(
    version=EVENTS_MIGRATION_VERSION,
    name="events",
    statements=(
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            subject TEXT,
            correlation_id TEXT,
            causation_id TEXT,
            payload TEXT,
            schema_version INTEGER NOT NULL DEFAULT 1
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type)",
        "CREATE INDEX IF NOT EXISTS idx_events_correlation ON events (correlation_id)",
    ),
)

register_framework_migration(EVENTS_MIGRATION)


def _translate(query: str) -> str:
    """SQLite-style ``?`` → psycopg ``%s`` (punts to the shared DB adapter)."""
    from voodoo.storage.database.postgres import _translate as _pg_translate

    return _pg_translate(query)


class PostgresEventStore:
    """Durable event bus backed by PostgreSQL (log + replay)."""

    provider = "postgres"

    def __init__(self, url: str) -> None:
        self.url = url
        self._lock = Lock()
        self._conn: Any = None
        self._handlers: dict[str, list[Callable]] = {}
        self._connect()
        self._migrate()

    def _connect(self) -> None:
        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(self.url, autocommit=False)
        self._conn.row_factory = dict_row

    def _migrate(self) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    subject TEXT,
                    correlation_id TEXT,
                    causation_id TEXT,
                    payload TEXT,
                    schema_version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_correlation "
                "ON events (correlation_id)"
            )
        self._conn.commit()

    def capabilities(self) -> EventBusCapabilities:
        return EventBusCapabilities(
            provider=self.provider,
            durable=True,
            replay=True,
            ordering=True,
            delivery="at_least_once",
        )

    def publish(self, event_type: str, payload: Any, **envelope: Any) -> dict[str, Any]:
        """Persist to log, then notify subscribers."""
        from voodoo.telemetry import trace_id_var

        ev = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": envelope.get("source", "voodoo"),
            "subject": envelope.get("subject"),
            "correlation_id": envelope.get("correlation_id", trace_id_var.get()),
            "causation_id": envelope.get("causation_id"),
            "payload": payload,
            "schema_version": envelope.get("schema_version", 1),
        }
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (
                    event_id, event_type, timestamp, source, subject,
                    correlation_id, causation_id, payload, schema_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ev["event_id"],
                    ev["event_type"],
                    ev["timestamp"],
                    ev["source"],
                    ev["subject"],
                    ev["correlation_id"],
                    ev["causation_id"],
                    json.dumps(payload, default=str, ensure_ascii=False),
                    ev["schema_version"],
                ),
            )
        self._conn.commit()

        for handler in self._handlers.get(event_type, []):
            try:
                result = handler(ev)
                if result is not None and hasattr(result, "__await__"):
                    asyncio.create_task(result)
            except Exception:
                pass
        return ev

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def replay(self, event_type: str, handler: Callable) -> int:
        """Replay persisted events to a handler. Returns count."""
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM events WHERE event_type = %s ORDER BY timestamp ASC",
                (event_type,),
            )
            rows = cur.fetchall()
        count = 0
        for row in rows:
            ev = {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "timestamp": row["timestamp"],
                "source": row["source"],
                "subject": row["subject"],
                "correlation_id": row["correlation_id"],
                "causation_id": row["causation_id"],
                "payload": json.loads(row["payload"]) if row["payload"] else None,
                "schema_version": row["schema_version"],
            }
            try:
                handler(ev)
                count += 1
            except Exception:
                pass
        return count

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


if TYPE_CHECKING:
    _protocol_check: VoodooEventBus = PostgresEventStore("postgresql://check")
