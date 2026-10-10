"""Durable orchestration checkpoints for Voodoo Workflows.

Workflow persistence records orchestration progress only. Canonical Executions
remain owned by :class:`ExecutionEngine`; this module never executes work and
never creates a second execution lifecycle.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

__all__ = ["WorkflowStore", "VoodooStoreWorkflowStore"]

_PREFIX = b"runtime:workflows:checkpoint:"
_NATIVE_INDEX_PREFIX = b"runtime:workflows:native-id:"
_NATIVE_INDEX_COLLECTION = b"runtime.workflow_index"
_TERMINAL = {"completed", "failed", "cancelled"}
_CHECKPOINT_SCHEMA_VERSION = 1
_SCHEMA_KEY = "_schema_version"
_INDEX_SCHEMA_VERSION = 1


class WorkflowStore(Protocol):
    """Durable checkpoint boundary for Workflow orchestration state."""

    def save(self, workflow_id: str, payload: dict[str, Any]) -> None: ...

    def load(self, workflow_id: str) -> dict[str, Any] | None: ...

    def load_unfinished(self) -> list[dict[str, Any]]: ...


class VoodooStoreWorkflowStore:
    """Workflow checkpoints backed by the Runtime-owned Voodoo Store."""

    provider = "voodoo"

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self._runtime_store = runtime_store

    def _runtime(self) -> RuntimeStore:
        if self._runtime_store is not None:
            return self._runtime_store
        from voodoo.runtime.store import acquire_runtime_store

        return acquire_runtime_store()

    def _store(self) -> Any:
        runtime = self._runtime()
        provider = runtime.provider or runtime.start()
        if provider is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "Voodoo Store is disabled; durable Workflow checkpoints require "
                "an explicit WorkflowStore adapter or an enabled Runtime Store."
            )
        native = getattr(provider, "native", None)
        if native is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "The active Voodoo Store provider does not expose durable KV storage."
            )
        return native

    @property
    def path(self) -> Any:
        return self._runtime().config.path

    def save(self, workflow_id: str, payload: dict[str, Any]) -> None:
        body = dict(payload)
        body["workflow_id"] = workflow_id
        body[_SCHEMA_KEY] = _CHECKPOINT_SCHEMA_VERSION
        store = self._store()
        encoded = json.dumps(
            body, separators=(",", ":"), sort_keys=True, default=str
        ).encode("utf-8")
        if self._native_workflows(store):
            native_id = self._native_id(store, workflow_id)
            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            existing = None if native_id is None else store.get_workflow(native_id)
            if native_id is None or existing is None:
                native_id = bytes(
                    store.create_workflow(
                        b"voodoo.workflow", b"checkpoint", encoded, now_ms
                    )
                )
                existing = store.get_workflow(native_id)
            # Also migrates a legacy prefixed index the first time an existing
            # workflow is checkpointed after upgrading the Store binding.
            self._save_native_id(store, workflow_id, native_id)
            status = str(body.get("status", "running"))
            if existing is not None and existing.get("status") not in {
                "completed",
                "failed",
                "cancelled",
            }:
                store.set_workflow_step(native_id, b"checkpoint", encoded, now_ms)
                if status == "completed":
                    store.complete_workflow(native_id, encoded, now_ms)
                elif status == "failed":
                    store.fail_workflow(native_id, str(body.get("error") or "").encode(), now_ms)
                elif status == "cancelled":
                    store.cancel_workflow(native_id, str(body.get("error") or "").encode(), now_ms)
            return
        store.put(self._key(workflow_id), encoded)

    def load(self, workflow_id: str) -> dict[str, Any] | None:
        store = self._store()
        if self._native_workflows(store):
            native_id = self._native_id(store, workflow_id)
            if native_id is not None:
                instance = store.get_workflow(native_id)
                if instance is not None:
                    payload = self._decode_native_state(workflow_id, instance)
                    payload["status"] = str(instance["status"])
                    return payload
        raw = store.get(self._key(workflow_id))
        if raw is None:
            return None
        return self._decode(workflow_id, bytes(raw))

    def load_unfinished(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        store = self._store()
        seen: set[str] = set()
        if self._native_workflows(store):
            native_indexes: list[tuple[bytes, bytes]] = []
            if self._native_collections(store):
                self._ensure_native_index(store)
                for key, raw, _indexes in store.scan_collection(
                    _NATIVE_INDEX_COLLECTION
                ):
                    payload = json.loads(bytes(raw).decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("workflow native index must be a JSON object")
                    version = payload.get(_SCHEMA_KEY, 0)
                    if version > _INDEX_SCHEMA_VERSION:
                        raise ValueError(
                            "workflow native index schema is newer than supported"
                        )
                    encoded_id = payload.get("native_id")
                    if not isinstance(encoded_id, str):
                        raise ValueError(
                            "workflow native index native_id must be hexadecimal"
                        )
                    native_indexes.append((bytes(key), bytes.fromhex(encoded_id)))
            native_indexes.extend(
                (
                    bytes(key)[len(_NATIVE_INDEX_PREFIX) :],
                    bytes(raw_native_id),
                )
                for key, raw_native_id in store.scan_prefix(_NATIVE_INDEX_PREFIX)
            )
            for raw_workflow_id, native_id in native_indexes:
                workflow_id = raw_workflow_id.decode("utf-8")
                if workflow_id in seen:
                    continue
                instance = store.get_workflow(native_id)
                if instance is None:
                    continue
                payload = self._decode_native_state(workflow_id, instance)
                payload["status"] = str(instance["status"])
                seen.add(workflow_id)
                if payload.get("status") not in _TERMINAL:
                    records.append(payload)
        for key, raw in store.scan_prefix(_PREFIX):
            workflow_id = key[len(_PREFIX) :].decode("utf-8")
            if workflow_id in seen:
                continue
            payload = self._decode(workflow_id, bytes(raw))
            if payload.get("status") not in _TERMINAL:
                records.append(payload)
        records.sort(key=lambda item: (item.get("updated_at", ""), item["workflow_id"]))
        return records

    def close(self) -> None:
        """No-op: RuntimeStore owns the shared Store lifecycle."""

    @staticmethod
    def _key(workflow_id: str) -> bytes:
        return _PREFIX + workflow_id.encode("utf-8")

    @staticmethod
    def _native_index_key(workflow_id: str) -> bytes:
        return _NATIVE_INDEX_PREFIX + workflow_id.encode("utf-8")

    @classmethod
    def _native_collections(cls, store: Any) -> bool:
        """Return whether the Store supports the native workflow index."""
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
    def _ensure_native_index(cls, store: Any) -> None:
        if cls._native_collections(store):
            store.create_collection(
                _NATIVE_INDEX_COLLECTION,
                schema_version=_INDEX_SCHEMA_VERSION,
                codec=b"json",
            )

    @classmethod
    def _save_native_id(cls, store: Any, workflow_id: str, native_id: bytes) -> None:
        if cls._native_collections(store):
            cls._ensure_native_index(store)
            store.upsert_record(
                _NATIVE_INDEX_COLLECTION,
                workflow_id.encode("utf-8"),
                json.dumps(
                    {
                        "native_id": bytes(native_id).hex(),
                        _SCHEMA_KEY: _INDEX_SCHEMA_VERSION,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8"),
            )
            # Remove the pre-collection index after migration so new writes
            # have one canonical durable representation.
            if hasattr(store, "delete"):
                store.delete(cls._native_index_key(workflow_id))
            return
        store.put(cls._native_index_key(workflow_id), bytes(native_id))

    @staticmethod
    def _native_workflows(store: Any) -> bool:
        return all(
            hasattr(store, method)
            for method in (
                "create_workflow",
                "get_workflow",
                "set_workflow_step",
                "complete_workflow",
                "fail_workflow",
                "cancel_workflow",
            )
        )

    @classmethod
    def _native_id(cls, store: Any, workflow_id: str) -> bytes | None:
        if cls._native_collections(store):
            cls._ensure_native_index(store)
            record = store.get_record(
                _NATIVE_INDEX_COLLECTION, workflow_id.encode("utf-8")
            )
            if record is not None:
                raw = bytes(record[1])
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError("workflow native index is not valid JSON") from error
                if not isinstance(payload, dict):
                    raise ValueError("workflow native index must be a JSON object")
                version = payload.get(_SCHEMA_KEY, 0)
                if version > _INDEX_SCHEMA_VERSION:
                    raise ValueError("workflow native index schema is newer than supported")
                encoded_id = payload.get("native_id")
                if not isinstance(encoded_id, str):
                    raise ValueError("workflow native index native_id must be hexadecimal")
                try:
                    return bytes.fromhex(encoded_id)
                except ValueError as error:
                    raise ValueError("workflow native index native_id is invalid") from error
        raw = store.get(cls._native_index_key(workflow_id))
        return None if raw is None else bytes(raw)

    @classmethod
    def _decode_native_state(
        cls, workflow_id: str, instance: dict[str, Any]
    ) -> dict[str, Any]:
        raw = instance.get("state")
        if raw is None:
            raise ValueError("native workflow state is missing")
        return cls._decode(workflow_id, bytes(raw))

    @staticmethod
    def _decode(workflow_id: str, raw: bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("workflow checkpoint is not valid UTF-8 JSON") from error
        if not isinstance(decoded, dict):
            raise ValueError("workflow checkpoint must be a JSON object")
        version = decoded.pop(_SCHEMA_KEY, 0)
        if not isinstance(version, int) or isinstance(version, bool):
            raise ValueError("workflow checkpoint schema version must be an integer")
        if version > _CHECKPOINT_SCHEMA_VERSION:
            raise ValueError(
                f"workflow checkpoint schema {version} is newer than supported "
                f"schema {_CHECKPOINT_SCHEMA_VERSION}"
            )
        stored_id = decoded.get("workflow_id")
        if stored_id is not None and stored_id != workflow_id:
            raise ValueError("workflow checkpoint identity does not match its key")
        decoded["workflow_id"] = workflow_id
        return cast(dict[str, Any], decoded)
