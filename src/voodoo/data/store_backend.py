"""Voodoo Store-backed record persistence for the Model facade.

Voodoo Store 0.2+ provides the native Collections contract used here. This is a
Runtime-owned data adapter, not a SQL emulation layer, and there is no legacy
transactional-KV fallback in the default Store path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from voodoo.core.errors import ConfigurationError

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

_runtime_store: RuntimeStore | None = None

_REQUIRED_COLLECTION_API = (
    "create_collection",
    "upsert_record",
    "get_record",
    "delete_record",
    "scan_collection",
)


def bind_runtime_store(runtime_store: RuntimeStore | None) -> None:
    """Bind the application-owned RuntimeStore for Model persistence."""
    global _runtime_store
    from voodoo.runtime.store import bind_active_runtime_store

    _runtime_store = runtime_store
    bind_active_runtime_store(runtime_store)


def _get_runtime_store() -> RuntimeStore:
    if _runtime_store is not None:
        return _runtime_store
    from voodoo.runtime.store import acquire_runtime_store

    return acquire_runtime_store()


def close_owned_store() -> None:
    """Standalone Store lifetime is managed centrally by runtime.store."""


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
    missing = [name for name in _REQUIRED_COLLECTION_API if not hasattr(native, name)]
    if missing:
        raise ConfigurationError(
            "Voodoo Store 0.2+ is required for native Model persistence. "
            f"Missing Store capabilities: {', '.join(missing)}. "
            "Upgrade with `pip install -U 'voodoo-store>=0.2.2,<0.3'`."
        )
    return native


def _collection_key(collection: str) -> bytes:
    return collection.encode("utf-8")


def _primary_key(record_id: int) -> bytes:
    return f"{record_id:020d}".encode("ascii")


def _ensure_collection(store: Any, collection: str) -> None:
    store.create_collection(
        _collection_key(collection), schema_version=1, codec=b"json"
    )


def _sequence_key(collection: str) -> bytes:
    return f"data:{collection}:meta:next_id".encode()


def _encode(record: dict[str, Any]) -> bytes:
    return json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


def insert_record(collection: str, values: dict[str, Any]) -> int:
    """Atomically allocate an integer id and persist one native Store record."""
    store = _native()
    _ensure_collection(store, collection)
    tx = store.transaction()
    if not hasattr(tx, "upsert_record"):
        raise ConfigurationError(
            "Voodoo Store 0.2+ transactional Collections support is required. "
            "Upgrade with `pip install -U 'voodoo-store>=0.2.2,<0.3'`."
        )

    sequence_key = _sequence_key(collection)
    raw = tx.get(sequence_key)
    next_id = int(bytes(raw).decode()) if raw is not None else 1
    record = dict(values)
    record["id"] = next_id
    encoded = _encode(record)
    tx.put(sequence_key, str(next_id + 1).encode())
    tx.upsert_record(_collection_key(collection), _primary_key(next_id), encoded)
    tx.commit()
    return next_id


def get_record(collection: str, record_id: int) -> dict[str, Any] | None:
    store = _native()
    _ensure_collection(store, collection)
    native_record = store.get_record(
        _collection_key(collection), _primary_key(record_id)
    )
    if native_record is None:
        return None
    return _decode(bytes(native_record[1]))


def put_record(collection: str, record_id: int, values: dict[str, Any]) -> None:
    store = _native()
    _ensure_collection(store, collection)
    record = dict(values)
    record["id"] = record_id
    store.upsert_record(
        _collection_key(collection),
        _primary_key(record_id),
        _encode(record),
    )


def delete_record(collection: str, record_id: int) -> None:
    store = _native()
    _ensure_collection(store, collection)
    store.delete_record(_collection_key(collection), _primary_key(record_id))


def scan_records(collection: str) -> list[dict[str, Any]]:
    store = _native()
    _ensure_collection(store, collection)
    records: list[dict[str, Any]] = []
    for _key, value, _indexes in store.scan_collection(_collection_key(collection)):
        records.append(_decode(bytes(value)))
    records.sort(key=lambda record: int(record["id"]))
    return records


def store_path() -> Path:
    return _get_runtime_store().config.path
