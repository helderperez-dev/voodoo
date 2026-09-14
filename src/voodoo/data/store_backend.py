"""Voodoo Store-backed record persistence for the Model facade.

This is a Runtime-owned data adapter, not a SQL emulation layer. Newer Store
bindings use native Collections; the 0.1.1 transactional-KV layout remains a
read/write compatibility path so applications can upgrade without losing
records. The public ``Model`` API never sees either representation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

_runtime_store: RuntimeStore | None = None
_owned_runtime_store: RuntimeStore | None = None


def bind_runtime_store(runtime_store: RuntimeStore | None) -> None:
    """Bind the application-owned RuntimeStore for Model persistence."""
    global _runtime_store
    _runtime_store = runtime_store


def _get_runtime_store() -> RuntimeStore:
    global _owned_runtime_store
    if _runtime_store is not None:
        return _runtime_store
    if _owned_runtime_store is None:
        from voodoo.runtime.store import RuntimeStore, StoreConfig

        _owned_runtime_store = RuntimeStore(StoreConfig.from_mapping())
        _owned_runtime_store.start()
    return _owned_runtime_store


def close_owned_store() -> None:
    global _owned_runtime_store
    if _owned_runtime_store is not None:
        _owned_runtime_store.stop()
        _owned_runtime_store = None


def should_use_store() -> bool:
    """Use Store by default; an initialized SQL adapter is an explicit override."""
    from voodoo.data.base import _active_adapter

    if _active_adapter() is not None:
        return False
    if _runtime_store is not None:
        return True

    from voodoo.config import _load_raw_file_data

    raw = _load_raw_file_data(None)
    database = raw.get("database") if isinstance(raw, dict) else None
    if isinstance(database, str):
        return database.lower() == "voodoo"
    if isinstance(database, dict) and database.get("provider"):
        return str(database["provider"]).lower() == "voodoo"
    return True


def _native() -> Any:
    runtime_store = _get_runtime_store()
    provider = runtime_store.provider or runtime_store.start()
    if provider is None:
        raise RuntimeError("Voodoo Store is disabled")
    native = getattr(provider, "native", None)
    if native is None:
        raise RuntimeError("Active Store provider does not expose record storage")
    return native


def _supports_native_collections(store: Any) -> bool:
    required = (
        "create_collection",
        "upsert_record",
        "get_record",
        "delete_record",
        "scan_collection",
    )
    return all(hasattr(store, name) for name in required)


def _supports_transactional_collection_upsert(transaction: Any) -> bool:
    return hasattr(transaction, "upsert_record")


def _collection_key(collection: str) -> bytes:
    return collection.encode("utf-8")


def _primary_key(record_id: int) -> bytes:
    return f"{record_id:020d}".encode("ascii")


def _ensure_collection(store: Any, collection: str) -> None:
    if _supports_native_collections(store):
        store.create_collection(
            _collection_key(collection), schema_version=1, codec=b"json"
        )


def _record_prefix(collection: str) -> bytes:
    return f"data:{collection}:record:".encode()


def _record_key(collection: str, record_id: int) -> bytes:
    return _record_prefix(collection) + _primary_key(record_id)


def _sequence_key(collection: str) -> bytes:
    return f"data:{collection}:meta:next_id".encode()


def _encode(record: dict[str, Any]) -> bytes:
    return json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


def insert_record(collection: str, values: dict[str, Any]) -> int:
    """Atomically allocate an integer id and persist one record.

    With the native Collections binding, the sequence KV update and native
    record upsert are staged in one Store transaction. Published 0.1.1 falls
    back to the original transactional-KV representation.
    """
    store = _native()
    _ensure_collection(store, collection)
    tx = store.transaction()
    sequence_key = _sequence_key(collection)
    raw = tx.get(sequence_key)
    next_id = int(bytes(raw).decode()) if raw is not None else 1
    record = dict(values)
    record["id"] = next_id
    encoded = _encode(record)
    tx.put(sequence_key, str(next_id + 1).encode())
    if _supports_native_collections(
        store
    ) and _supports_transactional_collection_upsert(tx):
        tx.upsert_record(
            _collection_key(collection),
            _primary_key(next_id),
            encoded,
        )
    else:
        tx.put(_record_key(collection, next_id), encoded)
    tx.commit()
    return next_id


def get_record(collection: str, record_id: int) -> dict[str, Any] | None:
    store = _native()
    if _supports_native_collections(store):
        _ensure_collection(store, collection)
        native_record = store.get_record(
            _collection_key(collection), _primary_key(record_id)
        )
        if native_record is not None:
            return _decode(bytes(native_record[1]))

    raw = store.get(_record_key(collection, record_id))
    return None if raw is None else _decode(bytes(raw))


def put_record(collection: str, record_id: int, values: dict[str, Any]) -> None:
    store = _native()
    record = dict(values)
    record["id"] = record_id
    encoded = _encode(record)

    if _supports_native_collections(store):
        _ensure_collection(store, collection)
        store.upsert_record(
            _collection_key(collection),
            _primary_key(record_id),
            encoded,
        )
        # An upgraded store may still contain the 0.1.1 representation. Once
        # rewritten natively, remove the stale legacy copy.
        store.delete(_record_key(collection, record_id))
        return

    store.put(_record_key(collection, record_id), encoded)


def delete_record(collection: str, record_id: int) -> None:
    store = _native()
    if _supports_native_collections(store):
        _ensure_collection(store, collection)
        store.delete_record(_collection_key(collection), _primary_key(record_id))
    # Always clear the legacy representation as well; delete is idempotent.
    store.delete(_record_key(collection, record_id))


def scan_records(collection: str) -> list[dict[str, Any]]:
    store = _native()
    records_by_id: dict[int, dict[str, Any]] = {}

    # Read legacy records first. Native rows overwrite the same ids so a
    # progressively migrated record always exposes its newest representation.
    for _key, value in store.scan_prefix(_record_prefix(collection)):
        record = _decode(bytes(value))
        records_by_id[int(record["id"])] = record

    if _supports_native_collections(store):
        _ensure_collection(store, collection)
        for _key, value, _indexes in store.scan_collection(_collection_key(collection)):
            record = _decode(bytes(value))
            records_by_id[int(record["id"])] = record

    return [records_by_id[key] for key in sorted(records_by_id)]


def store_path() -> Path:
    return _get_runtime_store().config.path
