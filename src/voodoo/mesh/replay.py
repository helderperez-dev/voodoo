"""Replay/idempotency storage for governed remote Mesh execution.

The replay store is deliberately not a second execution lifecycle. It only maps
one stable remote ``request_id`` plus a semantic request fingerprint to the
canonical :class:`RemoteExecutionOutcome` projected from Execution truth.

An in-memory implementation keeps tests and local experiments zero-infra. The
SQLite implementation provides durable duplicate suppression across process
restarts without requiring an external service.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from voodoo.mesh.remote import RemoteExecutionOutcome, RemoteExecutionRequest


@dataclass(frozen=True)
class ReplayRecord:
    request_id: str
    fingerprint: str
    outcome: RemoteExecutionOutcome


class RemoteReplayStore(Protocol):
    def get(self, request_id: str) -> ReplayRecord | None: ...

    def save(
        self,
        request: RemoteExecutionRequest,
        outcome: RemoteExecutionOutcome,
    ) -> ReplayRecord: ...

    def close(self) -> None: ...


def request_fingerprint(request: RemoteExecutionRequest) -> str:
    """Return a stable semantic fingerprint for replay/conflict detection."""
    payload: dict[str, Any] = {
        "schema_version": request.schema_version,
        "operation": request.operation,
        "arguments": request.arguments,
        "actor": request.actor,
        "correlation_id": request.correlation_id,
        "parent_execution_id": request.parent_execution_id,
        "target_entity_id": request.target_entity_id,
        "metadata": request.metadata,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class InMemoryRemoteReplayStore:
    """Process-local replay store used by default."""

    def __init__(self) -> None:
        self._records: dict[str, ReplayRecord] = {}

    def get(self, request_id: str) -> ReplayRecord | None:
        return self._records.get(request_id)

    def save(
        self,
        request: RemoteExecutionRequest,
        outcome: RemoteExecutionOutcome,
    ) -> ReplayRecord:
        fingerprint = request_fingerprint(request)
        existing = self._records.get(request.request_id)
        if existing is not None and existing.fingerprint != fingerprint:
            raise ValueError("remote request_id replay conflict")
        record = ReplayRecord(
            request_id=request.request_id,
            fingerprint=fingerprint,
            outcome=outcome.model_copy(deep=True),
        )
        # The request identity is immutable, but its projected Execution outcome
        # may move from WAITING to COMPLETED/FAILED after durable resume.
        self._records[request.request_id] = record
        return record

    def close(self) -> None:
        return None


class SQLiteRemoteReplayStore:
    """Durable local-first replay store for distributed request outcomes."""

    def __init__(self, path: str | Path = "data/mesh_replay.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mesh_remote_replay (
                request_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                outcome_json TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def get(self, request_id: str) -> ReplayRecord | None:
        row = self._connection.execute(
            "SELECT request_id, fingerprint, outcome_json "
            "FROM mesh_remote_replay WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return ReplayRecord(
            request_id=row["request_id"],
            fingerprint=row["fingerprint"],
            outcome=RemoteExecutionOutcome.model_validate_json(row["outcome_json"]),
        )

    def save(
        self,
        request: RemoteExecutionRequest,
        outcome: RemoteExecutionOutcome,
    ) -> ReplayRecord:
        fingerprint = request_fingerprint(request)
        existing = self.get(request.request_id)
        if existing is not None and existing.fingerprint != fingerprint:
            raise ValueError("remote request_id replay conflict")

        self._connection.execute(
            """
            INSERT INTO mesh_remote_replay(request_id, fingerprint, outcome_json)
            VALUES (?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                outcome_json = excluded.outcome_json
            """,
            (
                request.request_id,
                fingerprint,
                outcome.model_dump_json(),
            ),
        )
        self._connection.commit()
        return ReplayRecord(
            request_id=request.request_id,
            fingerprint=fingerprint,
            outcome=outcome.model_copy(deep=True),
        )

    def close(self) -> None:
        self._connection.close()


__all__ = [
    "ReplayRecord",
    "RemoteReplayStore",
    "InMemoryRemoteReplayStore",
    "SQLiteRemoteReplayStore",
    "request_fingerprint",
]
