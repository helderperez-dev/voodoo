from __future__ import annotations

from types import SimpleNamespace

from voodoo.runtime.transaction import (
    OutboxDispatcher,
    OutboxMessage,
    RuntimeTransaction,
)


class _CollectionTransaction:
    def __init__(self, native: _CollectionNative) -> None:
        self.native = native
        self.operations: list[tuple[str, bytes, bytes, bytes | None]] = []

    def upsert_record(
        self, collection: bytes, key: bytes, value: bytes, *, indexes: list
    ) -> None:
        self.operations.append(("upsert", collection, key, value))

    def delete_record(self, collection: bytes, key: bytes) -> None:
        self.operations.append(("delete", collection, key, None))

    def commit(self) -> None:
        for operation, collection, key, value in self.operations:
            records = self.native.records.setdefault(collection, {})
            if operation == "upsert":
                assert value is not None
                records[key] = value
            else:
                records.pop(key, None)

    def rollback(self) -> None:
        self.operations.clear()


class _CollectionNative:
    def __init__(self) -> None:
        self.records: dict[bytes, dict[bytes, bytes]] = {}

    def create_collection(self, collection: bytes, *, schema_version: int, codec: bytes) -> None:
        self.records.setdefault(collection, {})

    def upsert_record(
        self,
        _collection: bytes,
        _key: bytes,
        _value: bytes,
        *,
        indexes: list | None = None,
    ) -> None:
        _ = indexes

    def transaction(self) -> _CollectionTransaction:
        return _CollectionTransaction(self)

    def scan_collection(self, collection: bytes):
        return [
            (key, value, []) for key, value in self.records.get(collection, {}).items()
        ]

    def scan_prefix(self, _prefix: bytes):
        return []


def test_outbox_collection_fallback_is_atomic_and_dispatchable() -> None:
    native = _CollectionNative()
    runtime = SimpleNamespace(
        provider=SimpleNamespace(name="voodoo", opened=True, native=native)
    )
    message = OutboxMessage(
        id="collection-event",
        topic="order.created",
        payload={"order_id": "42"},
    )

    with RuntimeTransaction(runtime) as tx:
        tx.stage_outbox(message)

    dispatcher = OutboxDispatcher(runtime)
    assert dispatcher.pending() == [message]
    published: list[tuple[str, dict, dict]] = []
    assert dispatcher.dispatch(
        lambda topic, payload, metadata: published.append((topic, payload, metadata))
    ) == 1
    assert published == [("order.created", {"order_id": "42"}, {})]
    assert dispatcher.pending() == []
    assert b"collection-event" in native.records[b"runtime.outbox_delivered"]
