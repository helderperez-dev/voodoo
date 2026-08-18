"""PostgreSQL implementation of the Voodoo queue capability (spec §12, §7).

Same semantics as :class:`~voodoo.storage.queue.sqlite.SQLiteQueue` —
tasks are rows in the ``tasks`` table; claiming is one atomic
``UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED) RETURNING``
statement so concurrent workers — even across processes — can never claim
the same task (spec §12 "SKIP LOCKED"). Leases make worker death
recoverable via :meth:`release_expired`, identical to the SQLite adapter.

The table schema is shared with SQLite (framework migration v2, translated
by ``PostgresDatabase._translate``), so the application sees no difference
between providers beyond the connection — swapping ``queue: sqlite`` →
``queue: postgres`` in ``voodoo.yaml`` changes zero application code.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from voodoo.storage.database import Migration, register_framework_migration
from voodoo.storage.database.postgres import PostgresDatabase
from voodoo.storage.queue.interfaces import (
    ACTIVE_STATUSES,
    QueueCapabilities,
    QueueStats,
    TaskRecord,
    TaskStatus,
)

TASKS_TABLE = "tasks"

# Same logical DDL as the SQLite queue; _translate rewrites AUTOINCREMENT
# and ? placeholders for PostgreSQL. Registered so a Postgres-backed app
# creates/populates the same tasks table via the migration runner.
TASKS_MIGRATION = Migration(
    version=2,
    name="durable_tasks",
    statements=(
        f"""
        CREATE TABLE IF NOT EXISTS {TASKS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            priority INTEGER NOT NULL DEFAULT 0,
            available_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 1,
            locked_by TEXT,
            locked_at TEXT,
            lease_until TEXT,
            idempotency_key TEXT,
            trace_id TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            last_error TEXT
        )
        """,
        f"""
        CREATE INDEX IF NOT EXISTS idx_tasks_ready
            ON {TASKS_TABLE} (status, priority DESC, available_at, id)
        """,
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_active
            ON {TASKS_TABLE} (idempotency_key)
            WHERE idempotency_key IS NOT NULL
              AND status IN ('pending', 'running', 'retrying')
        """,
    ),
)

register_framework_migration(TASKS_MIGRATION)

_COLUMNS = (
    "id, type, payload, status, priority, available_at, attempts, "
    "max_attempts, locked_by, locked_at, lease_until, idempotency_key, "
    "trace_id, created_at, completed_at, last_error"
)


def _now() -> datetime:
    return datetime.now(UTC)


def _ts(value: datetime) -> str:
    # Fixed-width microseconds keep lexicographic == chronological ordering.
    return value.isoformat(timespec="microseconds")


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _parse_status(value: Any) -> TaskStatus:
    return TaskStatus(str(value))


class PostgresQueue:
    """Durable queue on a shared PostgreSQL database (optional provider)."""

    provider = "postgres"

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db
        self._pg: Any | None = None

    async def setup(self) -> None:
        # TASKS_MIGRATION is registered globally; migrate() applies it
        # idempotently on the shared ledger.
        await self._db.migrate()

    # -- enqueue ---------------------------------------------------------

    async def enqueue(
        self,
        task_type: str,
        payload: Any,
        *,
        priority: int = 0,
        delay: float = 0.0,
        max_attempts: int = 1,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
    ) -> TaskRecord:
        if idempotency_key is not None:
            placeholders = ",".join("%s" for _ in ACTIVE_STATUSES)
            existing = await self._db.fetch_one(
                f"SELECT {_COLUMNS} FROM {TASKS_TABLE} "
                f"WHERE idempotency_key = %s AND status IN ({placeholders})",
                (idempotency_key, *(s.value for s in ACTIVE_STATUSES)),
            )
            if existing is not None:
                return self._record(existing)
        now = _now()
        available_at = now + timedelta(seconds=delay) if delay > 0 else now
        row = await self._db.fetch_one(
            f"INSERT INTO {TASKS_TABLE} "
            "(type, payload, priority, available_at, max_attempts, "
            "idempotency_key, trace_id, created_at) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            f"RETURNING {_COLUMNS}",
            (
                task_type,
                json.dumps(payload) if payload is not None else None,
                priority,
                _ts(available_at),
                max(1, int(max_attempts)),
                idempotency_key,
                trace_id,
                _ts(now),
            ),
        )
        assert row is not None  # RETURNING always yields the inserted row
        return self._record(row)

    # -- claim / lease ------------------------------------------------------

    async def claim(
        self,
        worker: str,
        *,
        types: Sequence[str] | None = None,
        lease_seconds: float = 60.0,
    ) -> TaskRecord | None:
        now = _now()
        lease_until = now + timedelta(seconds=lease_seconds)
        type_filter = ""
        params: list[Any] = [worker, _ts(now), _ts(lease_until), _ts(now)]
        if types:
            type_filter = f"AND type IN ({','.join(['%s'] * len(types))})"
            params.extend(types)
        # FOR UPDATE SKIP LOCKED inside the subquery guarantees two workers
        # never claim the same row: the first locks it, the rest skip it.
        # The RETURNING row is read before commit (autocommit makes each
        # statement atomic; a separate SELECT after the UPDATE would see the
        # row already committed to 'running' — this one round-trip is the
        # only correct form, mirroring SQLite).
        row = await self._db.fetch_one(
            f"""
            UPDATE {TASKS_TABLE} SET
                status = 'running',
                attempts = attempts + 1,
                locked_by = %s, locked_at = %s, lease_until = %s
            WHERE id = (
                SELECT id FROM {TASKS_TABLE}
                WHERE status IN ('pending', 'retrying') AND available_at <= %s
                    {type_filter}
                ORDER BY priority DESC, available_at ASC, id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING {_COLUMNS}
            """,
            params,
        )
        return self._record(row) if row is not None else None

    async def heartbeat(
        self, task_id: int, worker: str, *, lease_seconds: float = 60.0
    ) -> bool:
        now = _now()
        cursor = await self._db.execute(
            f"UPDATE {TASKS_TABLE} SET locked_at = %s, lease_until = %s "
            "WHERE id = %s AND locked_by = %s AND status = 'running'",
            (_ts(now), _ts(now + timedelta(seconds=lease_seconds)), task_id, worker),
        )
        return cursor.rowcount > 0

    async def complete(self, task_id: int, worker: str) -> bool:
        cursor = await self._db.execute(
            f"UPDATE {TASKS_TABLE} SET status = 'completed', completed_at = %s, "
            "locked_by = NULL, locked_at = NULL, lease_until = NULL "
            "WHERE id = %s AND locked_by = %s AND status = 'running'",
            (_ts(_now()), task_id, worker),
        )
        return cursor.rowcount > 0

    async def fail(
        self,
        task_id: int,
        worker: str,
        error: str,
        *,
        backoff_base: float = 1.0,
    ) -> TaskRecord | None:
        row = await self._db.fetch_one(
            f"SELECT {_COLUMNS} FROM {TASKS_TABLE} "
            "WHERE id = %s AND locked_by = %s AND status = 'running'",
            (task_id, worker),
        )
        if row is None:
            return None
        record = self._record(row)
        now = _now()
        if record.attempts < record.max_attempts:
            delay = backoff_base * (2 ** max(0, record.attempts - 1))
            status = TaskStatus.RETRYING
            completed_at: str | None = None
            available_at = _ts(now + timedelta(seconds=delay))
        else:
            status = TaskStatus.FAILED
            completed_at = _ts(now)
            available_at = _ts(now)
        await self._db.execute(
            f"UPDATE {TASKS_TABLE} SET status = %s, available_at = %s, "
            "completed_at = %s, locked_by = NULL, locked_at = NULL, "
            "lease_until = NULL, last_error = %s WHERE id = %s",
            (status.value, available_at, completed_at, error, task_id),
        )
        updated = await self._db.fetch_one(
            f"SELECT {_COLUMNS} FROM {TASKS_TABLE} WHERE id = %s", (task_id,)
        )
        return self._record(updated) if updated is not None else None

    async def release(self, task_id: int, worker: str) -> bool:
        cursor = await self._db.execute(
            f"UPDATE {TASKS_TABLE} SET status = 'pending', "
            "locked_by = NULL, locked_at = NULL, lease_until = NULL "
            "WHERE id = %s AND locked_by = %s AND status = 'running'",
            (task_id, worker),
        )
        return cursor.rowcount > 0

    async def release_expired(self) -> int:
        now = _now()
        cursor = await self._db.execute(
            f"""
            UPDATE {TASKS_TABLE} SET
                status = CASE WHEN attempts >= max_attempts THEN 'failed'
                              ELSE 'pending' END,
                completed_at = CASE WHEN attempts >= max_attempts THEN %s
                                    ELSE NULL END,
                last_error = COALESCE(last_error, 'lease expired'),
                locked_by = NULL, locked_at = NULL, lease_until = NULL
            WHERE status = 'running' AND lease_until IS NOT NULL AND lease_until < %s
            """,
            (_ts(now), _ts(now)),
        )
        return cursor.rowcount or 0

    async def retry(self, task_id: int) -> TaskRecord | None:
        cursor = await self._db.execute(
            f"UPDATE {TASKS_TABLE} SET status = 'pending', attempts = 0, "
            "available_at = %s, completed_at = NULL, locked_by = NULL, "
            "locked_at = NULL, lease_until = NULL WHERE id = %s AND status = 'failed'",
            (_ts(_now()), task_id),
        )
        if not cursor.rowcount:
            return None
        row = await self._db.fetch_one(
            f"SELECT {_COLUMNS} FROM {TASKS_TABLE} WHERE id = %s", (task_id,)
        )
        return self._record(row) if row is not None else None

    # -- inspection ---------------------------------------------------------

    async def list(
        self,
        *,
        status: TaskStatus | str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[TaskRecord]:
        clauses, params = [], []
        if status is not None:
            clauses.append("status = %s")
            params.append(TaskStatus(status).value)
        if task_type is not None:
            clauses.append("type = %s")
            params.append(task_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = await self._db.fetch_all(
            f"SELECT {_COLUMNS} FROM {TASKS_TABLE} {where} ORDER BY id DESC LIMIT %s",
            params,
        )
        return [self._record(row) for row in rows]

    async def stats(self) -> QueueStats:
        rows = await self._db.fetch_all(
            f"SELECT status, COUNT(*) AS n FROM {TASKS_TABLE} GROUP BY status"
        )
        counts = {row["status"]: row["n"] for row in rows}
        return QueueStats(
            total=sum(counts.values()),
            pending=counts.get(TaskStatus.PENDING.value, 0),
            running=counts.get(TaskStatus.RUNNING.value, 0),
            retrying=counts.get(TaskStatus.RETRYING.value, 0),
            completed=counts.get(TaskStatus.COMPLETED.value, 0),
            failed=counts.get(TaskStatus.FAILED.value, 0),
        )

    def capabilities(self) -> QueueCapabilities:
        return QueueCapabilities(
            provider=self.provider,
            durable=True,
            delivery="at_least_once",
            ordering="best_effort",
            visibility_timeout=True,
            delayed_delivery=True,
            priority=True,
            transactions=True,
        )

    def _record(self, row: Any) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            type=row["type"],
            payload=json.loads(row["payload"]) if row["payload"] else None,
            status=_parse_status(row["status"]),
            priority=row["priority"],
            available_at=_parse_ts(row["available_at"]),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            locked_by=row["locked_by"],
            locked_at=_parse_ts(row["locked_at"]),
            lease_until=_parse_ts(row["lease_until"]),
            idempotency_key=row["idempotency_key"],
            trace_id=row["trace_id"],
            created_at=_parse_ts(row["created_at"]),
            completed_at=_parse_ts(row["completed_at"]),
            last_error=row["last_error"],
        )


if TYPE_CHECKING:
    from voodoo.storage.queue.interfaces import VoodooQueue

    _protocol_check: VoodooQueue = PostgresQueue(PostgresDatabase("check"))
