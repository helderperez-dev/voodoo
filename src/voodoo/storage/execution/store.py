"""Voodoo Store-backed durable execution persistence.

The Runtime owns execution semantics; Voodoo Store owns durable mechanics. This
adapter keeps the existing synchronous ExecutionStore surface while persisting
materialized executions, journals, artifacts and approvals in the one active
application Store. It never opens a second ``.vstore``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.runtime.store import get_active_runtime_store

__all__ = ["VoodooStoreExecutionStore"]

_EXECUTION_PREFIX = b"runtime:execution:data:"
_EVENT_PREFIX = b"runtime:execution:event:"
_EVENT_SEQUENCE_KEY = b"runtime:execution:meta:event-sequence"
_ARTIFACT_PREFIX = b"runtime:execution:artifact:"
_APPROVAL_PREFIX = b"runtime:execution:approval:"


def _encode(value: Any) -> bytes:
    return json.dumps(
        value, default=str, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _decode(value: bytes) -> Any:
    return json.loads(bytes(value).decode("utf-8"))


def _execution_key(execution_id: str) -> bytes:
    return _EXECUTION_PREFIX + execution_id.encode("utf-8")


def _event_key(sequence: int) -> bytes:
    return _EVENT_PREFIX + f"{sequence:020d}".encode("ascii")


def _artifact_key(artifact_id: str) -> bytes:
    return _ARTIFACT_PREFIX + artifact_id.encode("utf-8")


def _approval_key(approval_id: str) -> bytes:
    return _APPROVAL_PREFIX + approval_id.encode("utf-8")


def _status_event_type(status: ExecutionStatus) -> str:
    mapping = {
        ExecutionStatus.CREATED: "execution.created",
        ExecutionStatus.PLANNED: "execution.started",
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


class VoodooStoreExecutionStore:
    """Execution persistence backed by the active Runtime Store."""

    provider = "voodoo"

    def __init__(self) -> None:
        runtime_store = get_active_runtime_store()
        if runtime_store is None:
            raise ConfigurationError(
                "Execution Store requires the active application RuntimeStore."
            )
        provider = runtime_store.provider or runtime_store.start()
        if provider is None:
            raise ConfigurationError("Voodoo Store is disabled for this Runtime.")
        native = getattr(provider, "native", None)
        if native is None:
            raise ConfigurationError(
                "The active Voodoo Store provider does not expose durable storage."
            )
        self._store = native
        self.path = runtime_store.config.path

    def save(self, execution: Execution) -> None:
        """Persist the materialized execution and append its status event atomically."""
        data = execution.model_dump(mode="json")
        event = {
            "execution_id": execution.id,
            "event_type": _status_event_type(execution.status),
            "payload": _execution_payload(execution),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        tx = self._store.transaction()
        raw_sequence = tx.get(_EVENT_SEQUENCE_KEY)
        sequence = int(bytes(raw_sequence).decode("ascii")) if raw_sequence else 0
        sequence += 1
        event["sequence"] = sequence
        tx.put(_execution_key(execution.id), _encode(data))
        tx.put(_event_key(sequence), _encode(event))
        tx.put(_EVENT_SEQUENCE_KEY, str(sequence).encode("ascii"))
        tx.commit()

    def load_all(self) -> list[Execution]:
        executions = [
            Execution.model_validate(_decode(value))
            for _key, value in self._store.scan_prefix(_EXECUTION_PREFIX)
        ]
        executions.sort(key=lambda item: item.created_at)
        return executions

    def append_event(
        self, execution_id: str, event_type: str, payload: dict[str, object]
    ) -> None:
        tx = self._store.transaction()
        raw_sequence = tx.get(_EVENT_SEQUENCE_KEY)
        sequence = int(bytes(raw_sequence).decode("ascii")) if raw_sequence else 0
        sequence += 1
        event = {
            "sequence": sequence,
            "execution_id": execution_id,
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        tx.put(_event_key(sequence), _encode(event))
        tx.put(_EVENT_SEQUENCE_KEY, str(sequence).encode("ascii"))
        tx.commit()

    def timeline(self, execution_id: str) -> list[dict[str, object]]:
        events = self._events()
        return [event for event in events if event["execution_id"] == execution_id]

    def list_events(self, limit: int = 100) -> list[dict[str, object]]:
        events = self._events()
        events.reverse()
        return events[:limit]

    def _events(self) -> list[dict[str, object]]:
        events = [
            _decode(value) for _key, value in self._store.scan_prefix(_EVENT_PREFIX)
        ]
        events.sort(key=lambda event: int(event["sequence"]))
        return events

    def record_artifact(self, artifact: dict[str, Any]) -> None:
        record = dict(artifact)
        record.setdefault("created_at", datetime.now(UTC).isoformat())
        self._store.put(_artifact_key(str(record["id"])), _encode(record))

    def list_artifacts(
        self, execution_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        artifacts = [
            _decode(value) for _key, value in self._store.scan_prefix(_ARTIFACT_PREFIX)
        ]
        if execution_id is not None:
            artifacts = [
                artifact
                for artifact in artifacts
                if artifact.get("execution_id") == execution_id
            ]
        artifacts.sort(
            key=lambda artifact: str(artifact.get("created_at", "")), reverse=True
        )
        return artifacts[:limit]

    def save_approval(self, approval: Any) -> None:
        record = {
            "id": approval.id,
            "execution_id": approval.execution_id,
            "trace_id": approval.trace_id,
            "capability": approval.capability,
            "question": approval.question,
            "requested_by": approval.requested_by,
            "status": approval.status.value,
            "decided_by": approval.decided_by,
            "decided_at": approval.decided_at.isoformat()
            if approval.decided_at
            else None,
            "reason": approval.reason,
            "created_at": approval.created_at.isoformat()
            if approval.created_at
            else datetime.now(UTC).isoformat(),
            "participant": getattr(approval, "participant", None),
        }
        self._store.put(_approval_key(str(approval.id)), _encode(record))

    def load_approval(self, execution_id: str) -> dict[str, Any] | None:
        approvals = [
            approval
            for approval in self.load_approvals()
            if approval.get("execution_id") == execution_id
        ]
        return approvals[0] if approvals else None

    def load_approvals(self, pending_only: bool = False) -> list[dict[str, Any]]:
        approvals = [
            _decode(value) for _key, value in self._store.scan_prefix(_APPROVAL_PREFIX)
        ]
        if pending_only:
            approvals = [
                approval
                for approval in approvals
                if approval.get("status") == "pending"
            ]
        approvals.sort(
            key=lambda approval: str(approval.get("created_at", "")), reverse=True
        )
        return approvals

    def close(self) -> None:
        """No-op: the Runtime owns the shared Store lifecycle."""
        return None
