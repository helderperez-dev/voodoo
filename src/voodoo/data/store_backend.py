"""Voodoo Store-backed record persistence for the Model facade.

This is a Runtime-owned data adapter, not a SQL emulation layer. Records are
stored as versioned JSON documents under deterministic collection prefixes.
The public ``Model`` API stays unchanged while SQLite/PostgreSQL remain
explicit compatibility adapters.
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

    # Outside an App lifespan, fresh Model usage is still Store-first. A
    # configured SQL provider remains an explicit compatibility override.
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


def _record_prefix(collection: str) -> bytes:
    return f"data:{collection}:record:".encode()


def _record_key(collection: str, record_id: int) -> bytes:
    return _record_prefix(collection) + f"{record_id:020d}".encode()


def _sequence_key(collection: str) -> bytes:
    return f"data:{collection}:meta:next_id".encode()


def _encode(record: dict[str, Any]) -> bytes:
    return json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


def insert_record(collection: str, values: dict[str, Any]) -> int:
    """Atomically allocate an integer id and persist one record."""
    store = _native()
    tx = store.transaction()
    sequence_key = _sequence_key(collection)
    raw = tx.get(sequence_key)
    next_id = int(bytes(raw).decode()) if raw is not None else 1
    record = dict(values)
    record["id"] = next_id
    tx.put(sequence_key, str(next_id + 1).encode())
    tx.put(_record_key(collection, next_id), _encode(record))
    tx.commit()
    return next_id


def get_record(collection: str, record_id: int) -> dict[str, Any] | None:
    raw = _native().get(_record_key(collection, record_id))
    return None if raw is None else _decode(bytes(raw))


def put_record(collection: str, record_id: int, values: dict[str, Any]) -> None:
    record = dict(values)
    record["id"] = record_id
    _native().put(_record_key(collection, record_id), _encode(record))


def delete_record(collection: str, record_id: int) -> None:
    _native().delete(_record_key(collection, record_id))


def scan_records(collection: str) -> list[dict[str, Any]]:
    rows = _native().scan_prefix(_record_prefix(collection))
    return [_decode(bytes(value)) for _key, value in rows]


def store_path() -> Path:
    return _get_runtime_store().config.path
