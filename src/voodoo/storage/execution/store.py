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
from voodoo.observability import store_span
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.runtime.store import get_active_runtime_store

__all__ = ["VoodooStoreExecutionStore"]

_EXECUTION_PREFIX = b"runtime:execution:data:"
_EVENT_PREFIX = b"runtime:execution:event:"
_EVENT_STREAM = b"runtime.execution.events"
_EVENT_SEQUENCE_KEY = b"runtime:execution:meta:event-sequence"
_ARTIFACT_PREFIX = b"runtime:execution:artifact:"
_APPROVAL_PREFIX = b"runtime:execution:approval:"
_EXECUTION_COLLECTION = b"runtime.executions"
_ARTIFACT_COLLECTION = b"runtime.execution_artifacts"
_APPROVAL_COLLECTION = b"runtime.execution_approvals"
_SCHEMA_KEY = "_schema_version"
_SCHEMA_VERSION = 1


def _encode(value: Any) -> bytes:
    return json.dumps(
        value, default=str, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _decode(value: bytes) -> Any:
    return json.loads(bytes(value).decode("utf-8"))


def _decode_versioned(value: bytes, *, kind: str) -> dict[str, Any]:
    payload = _decode(value)
    if not isinstance(payload, dict):
        raise ValueError(f"{kind} record must be a JSON object")
    version = payload.pop(_SCHEMA_KEY, 0)
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError(f"{kind} schema version must be an integer")
    if version > _SCHEMA_VERSION:
        raise ValueError(f"unsupported {kind} schema version: {version}")
    return payload


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

    @staticmethod
    def _native_streams(store: Any) -> bool:
        return all(
            hasattr(store, method)
            for method in ("read_stream", "append_stream", "transaction")
        )

    @staticmethod
    def _native_collections(store: Any) -> bool:
        return all(
            hasattr(store, method)
            for method in (
                "create_collection",
                "upsert_record",
                "get_record",
                "scan_collection",
            )
        )

    @classmethod
    def _ensure_collections(cls, store: Any) -> None:
        if not cls._native_collections(store):
            return
        for name in (
            _EXECUTION_COLLECTION,
            _ARTIFACT_COLLECTION,
            _APPROVAL_COLLECTION,
        ):
            store.create_collection(name, schema_version=1, codec=b"json")

    def save(self, execution: Execution) -> None:
        """Persist an execution and emit a bounded Store correlation span."""
        with store_span(
            "store.execution.save",
            attributes={"provider": self.provider},
        ):
            self._save(execution)

    def _save(self, execution: Execution) -> None:
        """Persist the materialized execution and append its status event atomically."""
        if self._native_collections(self._store):
            self._ensure_collections(self._store)
        data = execution.model_dump(mode="json")
        data[_SCHEMA_KEY] = _SCHEMA_VERSION
        event: dict[str, Any] = {
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
        if self._native_collections(self._store):
            tx.upsert_record(
                _EXECUTION_COLLECTION,
                execution.id.encode("utf-8"),
                _encode(data),
            )
            # The collection is canonical. Delete the legacy materialized
            # record in the same transaction, after the native write has been
            # staged successfully, while retaining legacy read-through for
            # older records that have not been touched yet.
            tx.delete(_execution_key(execution.id))
        else:
            tx.put(_execution_key(execution.id), _encode(data))
        if self._native_streams(self._store):
            tx.append_stream(_EVENT_STREAM, _encode(event))
        else:
            tx.put(_event_key(sequence), _encode(event))
        tx.put(_EVENT_SEQUENCE_KEY, str(sequence).encode("ascii"))
        if self._native_streams(self._store) and hasattr(tx, "commit_with_results"):
            tx.commit_with_results()
        else:
            tx.commit()

    def load_all(self) -> list[Execution]:
        """Load materialized executions and emit a bounded Store span."""
        with store_span(
            "store.execution.load",
            attributes={"provider": self.provider},
        ):
            return self._load_all()

    def _load_all(self) -> list[Execution]:
        values: dict[str, bytes] = {}
        if self._native_collections(self._store):
            self._ensure_collections(self._store)
            values.update(
                {
                    bytes(key).decode("utf-8"): value
                    for key, value, _indexes in self._store.scan_collection(
                        _EXECUTION_COLLECTION
                    )
                }
            )
        values.update(
            {
                bytes(key)[len(_EXECUTION_PREFIX) :].decode("utf-8"): value
                for key, value in self._store.scan_prefix(_EXECUTION_PREFIX)
                if bytes(key)[len(_EXECUTION_PREFIX) :].decode("utf-8")
                not in values
            }
        )
        executions: list[Execution] = []
        for value in values.values():
            try:
                executions.append(
                    Execution.model_validate(_decode_versioned(value, kind="execution"))
                )
            except ValueError as error:
                if str(error).startswith("unsupported ") and "schema version" in str(error):
                    raise
                continue
            except (TypeError, json.JSONDecodeError):
                continue
        executions.sort(key=lambda item: item.created_at)
        return executions

    def append_event(
        self, execution_id: str, event_type: str, payload: dict[str, object]
    ) -> None:
        with store_span(
            "store.execution.append_event",
            attributes={"provider": self.provider},
        ):
            self._append_event(execution_id, event_type, payload)

    def _append_event(
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
        if self._native_streams(self._store):
            tx.append_stream(_EVENT_STREAM, _encode(event))
        else:
            tx.put(_event_key(sequence), _encode(event))
        tx.put(_EVENT_SEQUENCE_KEY, str(sequence).encode("ascii"))
        if self._native_streams(self._store) and hasattr(tx, "commit_with_results"):
            tx.commit_with_results()
        else:
            tx.commit()

    def timeline(self, execution_id: str) -> list[dict[str, object]]:
        events = self._events()
        return [event for event in events if event["execution_id"] == execution_id]

    def list_events(self, limit: int = 100) -> list[dict[str, object]]:
        events = self._events()
        events.reverse()
        return events[:limit]

    def _events(self) -> list[dict[str, object]]:
        self._migrate_legacy_events()
        events = [
            _decode(value) for _key, value in self._store.scan_prefix(_EVENT_PREFIX)
        ]
        if self._native_streams(self._store):
            events.extend(
                _decode(value)
                for _offset, value in self._store.read_stream(
                    _EVENT_STREAM, 0, 100_000
                )
            )
        events.sort(key=lambda event: int(event["sequence"]))
        return events

    def _migrate_legacy_events(self) -> None:
        """Move legacy event-key records into the canonical native stream.

        The migration is idempotent: native stream events are keyed by the
        durable sequence embedded in each payload, so an already-migrated
        sequence is not appended again. Stream appends and legacy-key deletes
        share one Store transaction, preventing a crash from producing either
        duplicate history or a partially deleted event set.
        """
        if not self._native_streams(self._store):
            return
        legacy = [
            (bytes(key), _decode(value))
            for key, value in self._store.scan_prefix(_EVENT_PREFIX)
        ]
        if not legacy:
            return
        stream_events = {
            int(_decode(value)["sequence"]): _decode(value)
            for _offset, value in self._store.read_stream(_EVENT_STREAM, 0, 100_000)
        }
        to_append: dict[int, dict[str, object]] = {}
        for _key, event in legacy:
            sequence = event.get("sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int):
                raise ValueError("legacy execution event sequence must be an integer")
            existing = stream_events.get(sequence)
            if existing is not None:
                if existing != event:
                    raise ValueError(
                        f"conflicting execution event sequence during migration: {sequence}"
                    )
            elif sequence in to_append and to_append[sequence] != event:
                raise ValueError(
                    f"conflicting legacy execution event sequence: {sequence}"
                )
            else:
                to_append[sequence] = event
        tx = self._store.transaction()
        for sequence in sorted(to_append):
            tx.append_stream(_EVENT_STREAM, _encode(to_append[sequence]))
        for key, _event in legacy:
            tx.delete(key)
        tx.commit()

    def record_artifact(self, artifact: dict[str, Any]) -> None:
        with store_span(
            "store.execution.record_artifact",
            attributes={"provider": self.provider},
        ):
            self._record_artifact(artifact)

    def _record_artifact(self, artifact: dict[str, Any]) -> None:
        record = dict(artifact)
        record.setdefault("created_at", datetime.now(UTC).isoformat())
        record.setdefault(_SCHEMA_KEY, _SCHEMA_VERSION)
        encoded = _encode(record)
        if self._native_collections(self._store):
            self._ensure_collections(self._store)
            self._store.upsert_record(
                _ARTIFACT_COLLECTION,
                str(record["id"]).encode("utf-8"),
                encoded,
            )
            self._store.delete(_artifact_key(str(record["id"])))
        else:
            self._store.put(_artifact_key(str(record["id"])), encoded)

    def list_artifacts(
        self, execution_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        artifacts_by_id: dict[str, dict[str, Any]] = {}
        if self._native_collections(self._store):
            self._ensure_collections(self._store)
            artifacts_by_id.update(
                {
                    str(bytes(key).decode("utf-8")): _decode_versioned(
                        value, kind="artifact"
                    )
                    for key, value, _indexes in self._store.scan_collection(
                        _ARTIFACT_COLLECTION
                    )
                }
            )
        artifacts_by_id.update(
            {
                str(record.get("id")): record
                for _key, value in self._store.scan_prefix(_ARTIFACT_PREFIX)
                if (record := _decode_versioned(value, kind="artifact"))
                and str(record.get("id")) not in artifacts_by_id
            }
        )
        artifacts = list(artifacts_by_id.values())
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
        with store_span(
            "store.execution.save_approval",
            attributes={"provider": self.provider},
        ):
            self._save_approval(approval)

    def _save_approval(self, approval: Any) -> None:
        record = {
            _SCHEMA_KEY: _SCHEMA_VERSION,
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
        if self._native_collections(self._store):
            self._ensure_collections(self._store)
            self._store.upsert_record(
                _APPROVAL_COLLECTION,
                str(approval.id).encode("utf-8"),
                _encode(record),
            )
            self._store.delete(_approval_key(str(approval.id)))
        else:
            self._store.put(_approval_key(str(approval.id)), _encode(record))

    def load_approval(self, execution_id: str) -> dict[str, Any] | None:
        approvals = [
            approval
            for approval in self.load_approvals()
            if approval.get("execution_id") == execution_id
        ]
        return approvals[0] if approvals else None

    def load_approvals(self, pending_only: bool = False) -> list[dict[str, Any]]:
        approvals_by_id: dict[str, dict[str, Any]] = {}
        if self._native_collections(self._store):
            self._ensure_collections(self._store)
            approvals_by_id.update(
                {
                    str(bytes(key).decode("utf-8")): _decode_versioned(
                        value, kind="approval"
                    )
                    for key, value, _indexes in self._store.scan_collection(
                        _APPROVAL_COLLECTION
                    )
                }
            )
        for key, value in self._store.scan_prefix(_APPROVAL_PREFIX):
            try:
                record = _decode_versioned(value, kind="approval")
                approval_id = str(record.get("id", bytes(key).decode("utf-8")))
                approvals_by_id.setdefault(approval_id, record)
            except ValueError as error:
                if str(error).startswith("unsupported ") and "schema version" in str(error):
                    raise
                continue
            except (TypeError, json.JSONDecodeError):
                continue
        approvals = list(approvals_by_id.values())
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
