"""SQLite-backed durable execution store (Sprint 3).

Executions are persisted in a materialized ``executions`` table plus an
append-only ``execution_events`` journal. The journal is the canonical
history; the materialized table is a queryable projection rebuilt on every
``save()`` (last write wins).

The store implements the sync ``ExecutionStore`` protocol from
``voodoo.runtime.persistence`` so the engine can swap between JSONL (legacy)
and SQLite without changing its recovery surface. Persistence failures are
never silently swallowed here — they raise, per spec §51.16.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.storage.database.interfaces import Migration
from voodoo.storage.database.sqlite import register_framework_migration
from voodoo.storage.execution.migrations import (
    EXECUTION_APPROVALS_MIGRATION,
    EXECUTION_ARTIFACTS_MIGRATION,
)

__all__ = ["SQLiteExecutionStore", "EXECUTION_MIGRATION"]

# Framework migration version for Sprint 3 — follows Sprint 1 (user baseline
# version 1) and Sprint 2 (tasks version 2). See storage/database/sqlite.py.
EXECUTION_MIGRATION_VERSION = 3

EXECUTION_MIGRATION = Migration(
    version=EXECUTION_MIGRATION_VERSION,
    name="executions",
    statements=(
        # Materialized execution state — queryable projection of the journal.
        """
        CREATE TABLE IF NOT EXISTS executions (
            id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            parent_execution_id TEXT,
            status TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'system',
            intent TEXT,
            capabilities TEXT NOT NULL DEFAULT '[]',
            resources TEXT NOT NULL DEFAULT '{}',
            effects TEXT NOT NULL DEFAULT '[]',
            state_changes TEXT NOT NULL DEFAULT '[]',
            result TEXT,
            error TEXT,
            metadata TEXT NOT NULL DEFAULT '{}',
            checkpoint TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL
        )
        """,
        # Append-only event journal — canonical execution history.
        """
        CREATE TABLE IF NOT EXISTS execution_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (execution_id) REFERENCES executions (id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_executions_trace ON executions (trace_id)",
        "CREATE INDEX IF NOT EXISTS idx_executions_status ON executions (status)",
        "CREATE INDEX IF NOT EXISTS idx_exec_events_exec ON execution_events (execution_id)",
        "CREATE INDEX IF NOT EXISTS idx_exec_events_type ON execution_events (event_type)",
    ),
)

# Register at import time so ``migrate()`` picks it up when a SQLite database
# is opened. Idempotent — repeated imports are no-ops.
register_framework_migration(EXECUTION_MIGRATION)


class SQLiteExecutionStore:
    """Durable execution store backed by a SQLite database file.

    Implements ``ExecutionStore`` (sync surface) plus journal append and
    timeline queries used by ``voodoo execution <id>`` and ``voodoo events``.

    The store owns its own sqlite3 connection — execution persistence must
    not require the async VoodooDatabase lifecycle (engine checkpoints are
    sync). WAL mode keeps reads cheap under concurrent access.
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
        """Create tables idempotently (direct DDL, no async runner needed)."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                parent_execution_id TEXT,
                status TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'system',
                intent TEXT,
                capabilities TEXT NOT NULL DEFAULT '[]',
                resources TEXT NOT NULL DEFAULT '{}',
                effects TEXT NOT NULL DEFAULT '[]',
                state_changes TEXT NOT NULL DEFAULT '[]',
                result TEXT,
                error TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                checkpoint TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_executions_trace ON executions (trace_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_executions_status ON executions (status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_events_exec ON execution_events (execution_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exec_events_type ON execution_events (event_type)"
        )
        # Artifacts + approvals are shared framework migrations (versions 7-8)
        # so the server-backed stores create identical tables. Execute the
        # same statements here — single source of truth.
        for statement in EXECUTION_ARTIFACTS_MIGRATION.statements:
            self._conn.execute(statement)
        for statement in EXECUTION_APPROVALS_MIGRATION.statements:
            self._conn.execute(statement)
        # Migration for existing databases created before Sprint 4:
        # add the checkpoint column if absent.
        columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(executions)")
        }
        if "checkpoint" not in columns:
            self._conn.execute("ALTER TABLE executions ADD COLUMN checkpoint TEXT")
        # Sprint 18: durable participant column for approvals (idempotent —
        # fresh databases create it via the v9 migration; existing ones here).
        approval_columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(approvals)")
        }
        if "participant" not in approval_columns:
            self._conn.execute("ALTER TABLE approvals ADD COLUMN participant TEXT")
        self._conn.commit()

    # -- ExecutionStore protocol (sync, engine-compatible) -----------------

    def save(self, execution: Execution) -> None:
        """Upsert the materialized execution row and append a journal event.

        The journal event type derives from the execution status:
        ``execution.created`` for ``created``, ``execution.started`` for
        ``running``, ``execution.completed`` for ``completed``, etc. A
        ``state.changed`` event is appended after the status event when the
        execution already existed (subsequent write).
        """
        self.append_event(
            execution.id,
            _status_event_type(execution.status),
            _execution_payload(execution),
        )
        self._upsert_materialized(execution)

    def load_all(self) -> list[Execution]:
        """Return every execution (materialized projection, last write wins)."""
        rows = self._conn.execute(
            "SELECT * FROM executions ORDER BY created_at"
        ).fetchall()
        return [_row_to_execution(row) for row in rows]

    # -- journal (Sprint 3 addition) ---------------------------------------

    def append_event(
        self, execution_id: str, event_type: str, payload: dict[str, object]
    ) -> None:
        """Append one event to the execution journal."""
        from datetime import UTC, datetime

        self._conn.execute(
            """
            INSERT INTO execution_events (execution_id, event_type, payload, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (
                execution_id,
                event_type,
                json.dumps(payload, default=str, ensure_ascii=False),
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def timeline(self, execution_id: str) -> list[dict[str, object]]:
        """Return the chronological event timeline for one execution."""
        rows = self._conn.execute(
            """
            SELECT sequence, event_type, payload, timestamp
            FROM execution_events
            WHERE execution_id = ?
            ORDER BY sequence ASC
            """,
            (execution_id,),
        ).fetchall()
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
        """Return recent journal events across all executions."""
        rows = self._conn.execute(
            """
            SELECT sequence, execution_id, event_type, payload, timestamp
            FROM execution_events
            ORDER BY sequence DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
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
        """Persist an artifact record (produced by ``Execution.artifact()``)."""
        import json as _json
        from datetime import UTC, datetime

        self._conn.execute(
            """
            INSERT INTO artifacts (
                id, execution_id, parent_artifact_id, created_by, tool, model,
                checksum, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact["id"],
                artifact["execution_id"],
                artifact.get("parent_artifact_id"),
                artifact.get("created_by"),
                artifact.get("tool"),
                artifact.get("model"),
                artifact.get("checksum"),
                _json.dumps(artifact.get("metadata") or {}, default=str),
                artifact.get("created_at") or datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def list_artifacts(
        self, execution_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return artifact records, optionally filtered by execution."""
        if execution_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM artifacts WHERE execution_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (execution_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM artifacts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
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
        """Persist a pending/decided approval record."""
        from datetime import UTC, datetime

        self._conn.execute(
            """
            INSERT INTO approvals (
                id, execution_id, trace_id, capability, question, requested_by,
                status, decided_by, decided_at, reason, created_at, participant
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                status = excluded.status,
                decided_by = excluded.decided_by,
                decided_at = excluded.decided_at,
                reason = excluded.reason,
                participant = excluded.participant
            """,
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
                getattr(approval, "participant", None),
            ),
        )
        self._conn.commit()

    def load_approval(self, execution_id: str) -> dict[str, Any] | None:
        """Load a persisted approval record by execution id."""
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE execution_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (execution_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def load_approvals(self, pending_only: bool = False) -> list[dict[str, Any]]:
        """List approvals — newest first, optionally pending only (Sprint 18)."""
        if pending_only:
            rows = self._conn.execute(
                "SELECT * FROM approvals WHERE status = 'pending' "
                "ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM approvals ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    # -- internals ---------------------------------------------------------

    def _upsert_materialized(self, execution: Execution) -> None:
        from datetime import UTC, datetime

        data = execution.model_dump(mode="json")
        self._conn.execute(
            """
            INSERT INTO executions (
                id, trace_id, parent_execution_id, status, actor, intent,
                capabilities, resources, effects, state_changes, result, error,
                metadata, checkpoint, created_at, started_at, completed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            """,
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
        """Close the store's connection (used by tests and shutdown)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _status_event_type(status: ExecutionStatus) -> str:
    """Map an execution status to its journal event type."""
    mapping = {
        ExecutionStatus.CREATED: "execution.created",
        ExecutionStatus.PLANNED: "execution.started",  # planned → started
        ExecutionStatus.AUTHORIZED: "execution.started",
        ExecutionStatus.RUNNING: "execution.started",
        ExecutionStatus.WAITING: "execution.waiting",
        ExecutionStatus.COMPLETED: "execution.completed",
        ExecutionStatus.FAILED: "execution.failed",
        ExecutionStatus.CANCELLED: "execution.failed",
        ExecutionStatus.TIMED_OUT: "execution.failed",
    }
    return mapping.get(status, "execution.started")


def _execution_payload(execution: Execution) -> dict[str, object]:
    """Extract a JSON-safe payload for the journal event."""
    data = execution.model_dump(mode="json")
    return {
        "id": data["id"],
        "trace_id": data["trace_id"],
        "parent_execution_id": data.get("parent_execution_id"),
        "status": data["status"],
        "actor": data["actor"],
        "intent": data.get("intent"),
        "error": data.get("error"),
    }


def _row_to_execution(row: sqlite3.Row) -> Execution:
    """Reconstruct an Execution from a materialized row."""
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
