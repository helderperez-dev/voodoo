"""PostgreSQL implementation of the durable execution store (Sprint 11).

Mirrors :class:`~voodoo.storage.execution.sqlite.SQLiteExecutionStore` —
materialized ``executions`` table plus an append-only ``execution_events``
journal, artifacts (Sprint 6) and approvals (Sprint 4). The store keeps a
single synchronous psycopg connection (the ``ExecutionStore`` protocol is
sync like the SQLite one) and translates SQLite ``?`` placeholders to
psycopg ``%s`` via the shared ``_translate``.

The DDL is the *same* as SQLite — the migrations (versions 3/7/8,
``EXECUTION_MIGRATION`` / ``EXECUTION_ARTIFACTS_MIGRATION`` /
``EXECUTION_APPROVALS_MIGRATION``) are executed through the shared
``_translate`` so PostgreSQL uses TEXT columns just like SQLite (JSONB /
TIMESTAMPTZ remain a future sprint).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.storage.database.postgres import _translate
from voodoo.storage.execution.migrations import (
    EXECUTION_APPROVALS_MIGRATION,
    EXECUTION_ARTIFACTS_MIGRATION,
)
from voodoo.storage.execution.sqlite import (
    EXECUTION_MIGRATION,
    _execution_payload,
    _status_event_type,
)

__all__ = ["PostgresExecutionStore"]


class PostgresExecutionStore:
    """Durable execution store backed by PostgreSQL (shared tables)."""

    provider = "postgres"

    def __init__(self, url: str) -> None:
        self.url = url
        self._lock = Lock()
        self._conn: Any | None = None
        self._connect()
        self._migrate()

    def _connect(self) -> None:
        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(self.url, autocommit=False)
        self._conn.row_factory = dict_row

    def _migrate(self) -> None:
        """Create shared tables (own connection, sync — as SQLite does).

        The DDL is translatable by ``PostgresDatabase._translate``; running
        it here on the sync connection gives the execution store the same
        schema the async migration runner would create for the app database.
        """
        with self._lock:
            for migration in (
                EXECUTION_MIGRATION,
                EXECUTION_ARTIFACTS_MIGRATION,
                EXECUTION_APPROVALS_MIGRATION,
            ):
                with self._conn.cursor() as cur:
                    for statement in migration.statements:
                        cur.execute(_translate(statement))
            # post-Sprint-4 checkpoint column, like the SQLite store.
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'executions' AND column_name = 'checkpoint'"
                )
                if cur.fetchone() is None:
                    cur.execute(
                        _translate("ALTER TABLE executions ADD COLUMN checkpoint TEXT")
                    )
            self._conn.commit()

    # -- ExecutionStore protocol (sync) ------------------------------------

    def save(self, execution: Execution) -> None:
        payload = _execution_payload(execution)
        # Postgres enforces the execution_events → executions FK (SQLite does
        # not), so the parent materialized row must exist before the journal
        # insert. Order is not externally observable.
        self._upsert_materialized(execution)
        self.append_event(execution.id, _status_event_type(execution.status), payload)

    def load_all(self) -> list[Execution]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM executions ORDER BY created_at")
            rows = cur.fetchall()
        return [_row_to_execution(row) for row in rows]

    # -- journal -----------------------------------------------------------

    def append_event(
        self, execution_id: str, event_type: str, payload: dict[str, object]
    ) -> None:

        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                _translate(
                    "INSERT INTO execution_events "
                    "(execution_id, event_type, payload, timestamp) "
                    "VALUES (%s, %s, %s, %s)"
                ),
                (
                    execution_id,
                    event_type,
                    json.dumps(payload, default=str, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )
        self._conn.commit()

    def timeline(self, execution_id: str) -> list[dict[str, object]]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                _translate(
                    "SELECT sequence, event_type, payload, timestamp "
                    "FROM execution_events "
                    "WHERE execution_id = %s ORDER BY sequence ASC"
                ),
                (execution_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]) if row["payload"] else None,
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def list_events(self, limit: int = 100) -> list[dict[str, object]]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                _translate(
                    "SELECT sequence, execution_id, event_type, payload, timestamp "
                    "FROM execution_events ORDER BY sequence DESC LIMIT %s"
                ),
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "sequence": row["sequence"],
                "execution_id": row["execution_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]) if row["payload"] else None,
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    # -- artifacts (Sprint 6, spec §46) ------------------------------------

    def record_artifact(self, artifact: dict[str, Any]) -> None:

        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                _translate(
                    "INSERT INTO artifacts ("
                    "id, execution_id, parent_artifact_id, created_by, tool, model, "
                    "checksum, metadata, created_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    artifact["id"],
                    artifact["execution_id"],
                    artifact.get("parent_artifact_id"),
                    artifact.get("created_by"),
                    artifact.get("tool"),
                    artifact.get("model"),
                    artifact.get("checksum"),
                    json.dumps(artifact.get("metadata") or {}, default=str),
                    artifact.get("created_at") or datetime.now(UTC).isoformat(),
                ),
            )
        self._conn.commit()

    def list_artifacts(
        self, execution_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if execution_id is not None:
            sql = _translate(
                "SELECT * FROM artifacts WHERE execution_id = %s "
                "ORDER BY created_at DESC LIMIT %s"
            )
            params = (execution_id, limit)
        else:
            sql = _translate(
                "SELECT * FROM artifacts ORDER BY created_at DESC LIMIT %s"
            )
            params = (limit,)
        with self._lock, self._conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [
            {
                "id": row["id"],
                "execution_id": row["execution_id"],
                "parent_artifact_id": row["parent_artifact_id"],
                "created_by": row["created_by"],
                "tool": row["tool"],
                "model": row["model"],
                "checksum": row["checksum"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # -- approvals (Sprint 4) ----------------------------------------------

    def save_approval(self, approval: Any) -> None:

        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                _translate(
                    "INSERT INTO approvals ("
                    "id, execution_id, trace_id, capability, question, requested_by, "
                    "status, decided_by, decided_at, reason, created_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "status = excluded.status, "
                    "decided_by = excluded.decided_by, "
                    "decided_at = excluded.decided_at, "
                    "reason = excluded.reason"
                ),
                (
                    approval.id,
                    approval.execution_id,
                    approval.trace_id,
                    approval.capability,
                    approval.question,
                    approval.requested_by,
                    approval.status.value,
                    approval.decided_by,
                    approval.decided_at.isoformat() if approval.decided_at else None,
                    approval.reason,
                    approval.created_at.isoformat()
                    if approval.created_at
                    else datetime.now(UTC).isoformat(),
                ),
            )
        self._conn.commit()

    def load_approval(self, execution_id: str) -> dict[str, Any] | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                _translate(
                    "SELECT * FROM approvals WHERE execution_id = %s "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                (execution_id,),
            )
            row = cur.fetchone()
        return dict(row) if row is not None else None

    # -- internals ---------------------------------------------------------

    def _upsert_materialized(self, execution: Execution) -> None:

        data = execution.model_dump(mode="json")
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                _translate(
                    """
                    INSERT INTO executions (
                        id, trace_id, parent_execution_id, status, actor, intent,
                        capabilities, resources, effects, state_changes, result, error,
                        metadata, checkpoint, created_at, started_at, completed_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        trace_id = excluded.trace_id,
                        parent_execution_id = excluded.parent_execution_id,
                        status = excluded.status,
                        actor = excluded.actor,
                        intent = excluded.intent,
                        capabilities = excluded.capabilities,
                        resources = excluded.resources,
                        effects = excluded.effects,
                        state_changes = excluded.state_changes,
                        result = excluded.result,
                        error = excluded.error,
                        metadata = excluded.metadata,
                        checkpoint = excluded.checkpoint,
                        started_at = excluded.started_at,
                        completed_at = excluded.completed_at,
                        updated_at = excluded.updated_at
                    """
                ),
                (
                    data["id"],
                    data["trace_id"],
                    data.get("parent_execution_id"),
                    data["status"],
                    data["actor"],
                    json.dumps(data["intent"], default=str, ensure_ascii=False)
                    if data.get("intent")
                    else None,
                    json.dumps(data["capabilities"], default=str, ensure_ascii=False),
                    json.dumps(data["resources"], default=str, ensure_ascii=False),
                    json.dumps(data["effects"], default=str, ensure_ascii=False),
                    json.dumps(data["state_changes"], default=str, ensure_ascii=False),
                    json.dumps(data["result"], default=str, ensure_ascii=False)
                    if data.get("result") is not None
                    else None,
                    data.get("error"),
                    json.dumps(data["metadata"], default=str, ensure_ascii=False),
                    json.dumps(data["checkpoint"], default=str, ensure_ascii=False)
                    if data.get("checkpoint")
                    else None,
                    data.get("created_at") or datetime.now(UTC).isoformat(),
                    data.get("started_at"),
                    data.get("completed_at"),
                    datetime.now(UTC).isoformat(),
                ),
            )
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _row_to_execution(row: Any) -> Execution:
    """Reconstruct an Execution from a psycopg row (Row mapping)."""
    return Execution(
        id=row["id"],
        trace_id=row["trace_id"],
        parent_execution_id=row["parent_execution_id"],
        status=ExecutionStatus(row["status"]),
        actor=row["actor"],
        intent=json.loads(row["intent"]) if row["intent"] else None,
        capabilities=json.loads(row["capabilities"]) if row["capabilities"] else [],
        resources=json.loads(row["resources"]) if row["resources"] else {},
        effects=json.loads(row["effects"]) if row["effects"] else [],
        state_changes=json.loads(row["state_changes"]) if row["state_changes"] else [],
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        checkpoint=json.loads(row["checkpoint"]) if row["checkpoint"] else None,
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )
