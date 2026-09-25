"""Voodoo Store-backed record persistence for the public Model facade.

Voodoo Store 0.3+ provides the native Collections/index query contract used
here. The public data path has no SQL fallback and therefore no optional SQL
dependency in its import graph.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from uuid import UUID
from typing import TYPE_CHECKING, Any

from voodoo.core.errors import ConfigurationError

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

_runtime_store: RuntimeStore | None = None
_collection_indexes: dict[str, dict[str, bool]] = {}

_REQUIRED_COLLECTION_API = (
    "create_collection",
    "define_index",
    "upsert_record",
    "get_record",
    "delete_record",
    "scan_collection",
    "query_index_exact",
    "query_index_range",
)


def bind_runtime_store(runtime_store: RuntimeStore | None) -> None:
    """Bind the application-owned RuntimeStore for Model persistence."""
    global _runtime_store
    from voodoo.runtime.store import bind_active_runtime_store

    _runtime_store = runtime_store
    bind_active_runtime_store(runtime_store)


def register_indexes(collection: str, indexes: dict[str, bool]) -> None:
    """Register model-declared native indexes for one collection."""
    _collection_indexes[collection] = {
        str(name): bool(unique)
        for name, unique in indexes.items()
        if str(name)
    }


def _get_runtime_store() -> RuntimeStore:
    if _runtime_store is not None:
        return _runtime_store
    from voodoo.runtime.store import acquire_runtime_store

    return acquire_runtime_store()


def close_owned_store() -> None:
    """Standalone Store lifetime is managed centrally by runtime.store."""


def should_use_store() -> bool:
    """Return True for the public Model API.

    Kept temporarily for compatibility with internal callers while the 2.x SQL
    compatibility modules are retired. Public Model persistence is Store-only.
    """
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
            "Voodoo Store 0.3+ is required for native Model persistence. "
            f"Missing Store capabilities: {', '.join(missing)}."
        )
    return native


def _collection_key(collection: str) -> bytes:
    return collection.encode("utf-8")


def _primary_key(record_id: UUID | str) -> bytes:
    value = record_id if isinstance(record_id, UUID) else UUID(str(record_id))
    return value.bytes


def uuid7() -> UUID:
    """Generate an RFC 9562 UUIDv7 without requiring Python 3.14+."""
    unix_ms = time.time_ns() // 1_000_000
    if unix_ms >= (1 << 48):
        raise OverflowError("UUIDv7 timestamp exceeds 48 bits")
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (
        (unix_ms << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return UUID(int=value)


def _ensure_collection(store: Any, collection: str) -> None:
    collection_key = _collection_key(collection)
    store.create_collection(collection_key, schema_version=1, codec=b"json")
    created_index = False
    for index, unique in _collection_indexes.get(collection, {}).items():
        created_index = (
            store.define_index(
                collection_key,
                index.encode("utf-8"),
                unique=unique,
            )
            or created_index
        )

    if created_index:
        # Store intentionally keeps schema/index evolution explicit. When a
        # model adds an index after records already exist, rebuild those
        # records once so the new native index is complete immediately.
        existing = list(store.scan_collection(collection_key))
        for primary_key, value, _indexes in existing:
            record = _decode(bytes(value))
            store.upsert_record(
                collection_key,
                bytes(primary_key),
                bytes(value),
                indexes=_record_indexes(collection, record),
            )


def _json_default(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _encode(record: dict[str, Any]) -> bytes:
    return json.dumps(
        record,
        separators=(",", ":"),
        sort_keys=True,
        default=_json_default,
    ).encode("utf-8")


def _decode(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


def _encode_index_value(value: Any) -> bytes:
    if isinstance(value, bool):
        return b"b:" + (b"1" if value else b"0")
    if isinstance(value, int):
        if value < -(1 << 63) or value >= (1 << 63):
            raise ValueError("indexed integers must fit in signed 64-bit range")
        sortable = value + (1 << 63)
        return b"i:" + sortable.to_bytes(8, "big", signed=False)
    if isinstance(value, str):
        return b"s:" + value.encode("utf-8")
    raise TypeError("Store indexes currently support str, int, and bool values")


def _record_indexes(
    collection: str, record: dict[str, Any]
) -> list[tuple[bytes, bytes]]:
    indexes: list[tuple[bytes, bytes]] = []
    for field in _collection_indexes.get(collection, {}):
        if field in record:
            indexes.append((field.encode("utf-8"), _encode_index_value(record[field])))
    return indexes


def insert_record(
    collection: str,
    values: dict[str, Any],
    *,
    record_id: UUID | None = None,
) -> UUID:
    """Persist one native Store record with a Runtime-generated UUIDv7 identity."""
    store = _native()
    _ensure_collection(store, collection)
    tx = store.transaction()
    if not hasattr(tx, "upsert_record"):
        raise ConfigurationError(
            "Voodoo Store 0.3+ transactional Collections support is required."
        )

    identity = record_id or uuid7()
    record = dict(values)
    record["id"] = identity
    tx.upsert_record(
        _collection_key(collection),
        _primary_key(identity),
        _encode(record),
        indexes=_record_indexes(collection, record),
    )
    tx.commit()
    return identity


def get_record(
    collection: str, record_id: UUID | str
) -> dict[str, Any] | None:
    store = _native()
    _ensure_collection(store, collection)
    native_record = store.get_record(
        _collection_key(collection), _primary_key(record_id)
    )
    if native_record is None:
        return None
    return _decode(bytes(native_record[1]))


def put_record(
    collection: str,
    record_id: UUID | str,
    values: dict[str, Any],
) -> None:
    store = _native()
    _ensure_collection(store, collection)
    identity = record_id if isinstance(record_id, UUID) else UUID(str(record_id))
    record = dict(values)
    record["id"] = identity
    store.upsert_record(
        _collection_key(collection),
        _primary_key(identity),
        _encode(record),
        indexes=_record_indexes(collection, record),
    )


def delete_record(collection: str, record_id: UUID | str) -> None:
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


def query_records(
    collection: str,
    *,
    filters: dict[str, Any],
    order_by: list[str],
    limit: int | None,
    offset: int | None,
) -> list[dict[str, Any]]:
    """Use native Store indexes when declared; preserve scan fallback semantics."""
    store = _native()
    _ensure_collection(store, collection)
    declared = set(_collection_indexes.get(collection, {}))
    rows: list[dict[str, Any]]
    native_order_field: str | None = None

    indexed_filter = next((field for field in filters if field in declared), None)
    if indexed_filter is not None:
        native = store.query_index_exact(
            _collection_key(collection),
            indexed_filter.encode("utf-8"),
            _encode_index_value(filters[indexed_filter]),
        )
        rows = [_decode(bytes(record[1])) for record in native]
    elif len(order_by) == 1:
        first = order_by[0]
        field = first[1:] if first.startswith("-") else first
        if field in declared:
            native = store.query_index_range(
                _collection_key(collection),
                field.encode("utf-8"),
                descending=first.startswith("-"),
            )
            rows = [_decode(bytes(indexed_record[1][1])) for indexed_record in native]
            native_order_field = field
        else:
            rows = scan_records(collection)
    else:
        rows = scan_records(collection)

    for key, expected in filters.items():
        rows = [row for row in rows if row.get(key) == expected]

    for column in reversed(order_by):
        descending = column.startswith("-")
        name = column[1:] if descending else column
        if name == native_order_field and column == order_by[0]:
            continue
        rows.sort(key=lambda row: row.get(name), reverse=descending)

    if offset is not None:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]
    return rows


def store_path() -> Path:
    return _get_runtime_store().config.path
