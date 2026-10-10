"""Provider-neutral atomic boundary for Store-backed Runtime state.

Sprint 28.11 deliberately exposes only semantics that Voodoo Store 0.2.x can
actually commit atomically: KV mutations, Collection upserts, and durable
outbox records staged in the same native transaction. Jobs, external effects,
and work performed by another node are not claimed to be part of this atomic
boundary.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from voodoo.runtime.store import (
    RuntimeStore,
    StoreProviderError,
    get_active_runtime_store,
)

__all__ = [
    "OutboxDispatcher",
    "OutboxMessage",
    "RuntimeTransaction",
    "dispatch_events",
    "dispatch_outbox",
    "transaction",
]

_OUTBOX_PENDING_PREFIX = b"runtime:outbox:pending:"
_OUTBOX_DELIVERED_PREFIX = b"runtime:outbox:delivered:"
_OUTBOX_PENDING_COLLECTION = b"runtime.outbox_pending"
_OUTBOX_DELIVERED_COLLECTION = b"runtime.outbox_delivered"
_SCHEMA_KEY = "_schema_version"
_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    """Durable intent to publish work after the local transaction commits."""

    topic: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: uuid4().hex)
    metadata: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> bytes:
        return json.dumps(
            {
                _SCHEMA_KEY: _SCHEMA_VERSION,
                "id": self.id,
                "topic": self.topic,
                "payload": self.payload,
                "metadata": self.metadata,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @classmethod
    def decode(cls, raw: bytes, *, expected_id: str | None = None) -> OutboxMessage:
        envelope = json.loads(raw.decode("utf-8"))
        if not isinstance(envelope, dict):
            raise ValueError("outbox record must be a JSON object")
        version = envelope.pop(_SCHEMA_KEY, 0)
        if isinstance(version, bool) or not isinstance(version, int):
            raise ValueError("outbox schema version must be an integer")
        if version > _SCHEMA_VERSION:
            raise ValueError(f"unsupported outbox schema version: {version}")
        message = cls(
            id=envelope["id"],
            topic=envelope["topic"],
            payload=envelope["payload"],
            metadata=envelope.get("metadata", {}),
        )
        if expected_id is not None and message.id != expected_id:
            raise ValueError("outbox key does not match record id")
        return message


class RuntimeTransaction:
    """One atomic transaction over the active Runtime-owned Voodoo Store.

    The wrapper prevents higher Runtime layers from depending on the native
    ``voodoo_store.Transaction`` type while making the supported atomicity
    boundary explicit.
    """

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self.runtime_store = runtime_store or get_active_runtime_store()
        if self.runtime_store is None:
            raise StoreProviderError("No active RuntimeStore for transaction")
        provider = self.runtime_store.provider
        if provider is None or not provider.opened:
            raise StoreProviderError(
                "RuntimeStore must be started before a transaction"
            )
        if provider.name != "voodoo":
            raise StoreProviderError(
                "RuntimeTransaction currently requires the Voodoo Store provider"
            )
        native = getattr(provider, "native", None)
        if native is None or not hasattr(native, "transaction"):
            raise StoreProviderError(
                "Active Voodoo Store does not expose transactional capability"
            )
        self._tx = native.transaction()
        self._native_collections = all(
            hasattr(native, method)
            for method in ("create_collection", "upsert_record")
        ) and hasattr(self._tx, "delete_record")
        if self._native_collections:
            native.create_collection(
                _OUTBOX_PENDING_COLLECTION, schema_version=1, codec=b"json"
            )
            native.create_collection(
                _OUTBOX_DELIVERED_COLLECTION, schema_version=1, codec=b"json"
            )
        self._native_outbox = all(
            hasattr(native, method)
            for method in ("emit_outbox_event", "outbox_events_after", "ack_outbox_event")
        )
        self._finished = False

    def get(self, key: bytes) -> bytes | None:
        """Read a KV value including mutations staged by this transaction."""
        value = self._tx.get(key)
        return None if value is None else bytes(value)

    def put(self, key: bytes, value: bytes) -> None:
        """Stage a KV write."""
        self._tx.put(key, value)

    def delete(self, key: bytes) -> None:
        """Stage a KV delete."""
        self._tx.delete(key)

    def upsert_record(
        self,
        collection: bytes,
        primary_key: bytes,
        value: bytes,
        *,
        indexes: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        """Stage a native Collection upsert in the same transaction."""
        self._tx.upsert_record(
            collection,
            primary_key,
            value,
            indexes=list(indexes or []),
        )

    def stage_outbox(self, message: OutboxMessage) -> str:
        """Atomically stage a durable message beside state mutations."""
        if self._native_outbox and hasattr(self._tx, "emit_event"):
            self._tx.emit_event(
                message.topic.encode("utf-8"),
                message.encode(),
                int(datetime.now(UTC).timestamp() * 1000),
            )
            return message.id
        if self._native_collections:
            self._tx.upsert_record(
                _OUTBOX_PENDING_COLLECTION,
                message.id.encode("utf-8"),
                message.encode(),
                indexes=[],
            )
            return message.id
        self.put(_OUTBOX_PENDING_PREFIX + message.id.encode(), message.encode())
        return message.id

    def commit(self) -> None:
        if self._finished:
            raise StoreProviderError("Runtime transaction is already finished")
        self._tx.commit()
        self._finished = True

    def rollback(self) -> None:
        if self._finished:
            raise StoreProviderError("Runtime transaction is already finished")
        self._tx.rollback()
        self._finished = True

    def __enter__(self) -> RuntimeTransaction:
        return self

    def __exit__(
        self, exc_type: Any, exc: Any, traceback: Any
    ) -> Literal[False]:
        if self._finished:
            return False
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


class OutboxDispatcher:
    """Dispatch durable local outbox records with at-least-once semantics.

    The local state mutation and outbox insertion are atomic. Delivery itself is
    intentionally outside that transaction. If a process fails after publish but
    before acknowledgement, the message can be published again after restart.
    Consumers that need duplicate suppression should use ``message.id`` as their
    idempotency key.
    """

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self.runtime_store = runtime_store or get_active_runtime_store()
        if self.runtime_store is None:
            raise StoreProviderError("No active RuntimeStore for outbox dispatch")
        provider = self.runtime_store.provider
        if provider is None or not provider.opened:
            raise StoreProviderError("RuntimeStore must be started for outbox dispatch")
        if provider.name != "voodoo":
            raise StoreProviderError(
                "OutboxDispatcher currently requires the Voodoo Store provider"
            )
        self._native: Any = getattr(provider, "native", None)
        if self._native is None:
            raise StoreProviderError("Active Voodoo Store has no native handle")
        self._native_outbox = all(
            hasattr(self._native, method)
            for method in ("outbox_events_after", "ack_outbox_event")
        )
        self._native_collections = all(
            hasattr(self._native, method)
            for method in ("create_collection", "scan_collection", "upsert_record")
        )
        if self._native_collections:
            self._native.create_collection(
                _OUTBOX_PENDING_COLLECTION, schema_version=1, codec=b"json"
            )
            self._native.create_collection(
                _OUTBOX_DELIVERED_COLLECTION, schema_version=1, codec=b"json"
            )
        self._native_receipts: dict[str, tuple[int, bytes]] = {}

    def pending(self) -> list[OutboxMessage]:
        """Return durable pending messages in Store key order."""
        pending: list[OutboxMessage] = []
        self._native_receipts.clear()
        if self._native_outbox:
            for event in self._native.outbox_events_after(None, 10_000):
                try:
                    message = OutboxMessage.decode(bytes(event["payload"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                self._native_receipts[message.id] = (
                    int(event["tx_id"]),
                    bytes(event["nonce"]),
                )
                pending.append(message)
        pending.extend(self._collection_pending())
        pending.extend(self._legacy_pending())
        return pending

    def _collection_pending(self) -> list[OutboxMessage]:
        if not self._native_collections:
            return []
        pending: list[OutboxMessage] = []
        for key, raw_value, _indexes in self._native.scan_collection(
            _OUTBOX_PENDING_COLLECTION
        ):
            expected_id = bytes(key).decode("utf-8")
            try:
                message = OutboxMessage.decode(bytes(raw_value), expected_id=expected_id)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if message.id not in self._native_receipts:
                pending.append(message)
        return pending

    def _legacy_pending(self) -> list[OutboxMessage]:
        pending: list[OutboxMessage] = []
        for key, raw_value in self._native.scan_prefix(_OUTBOX_PENDING_PREFIX):
            expected_id = bytes(key)[len(_OUTBOX_PENDING_PREFIX) :].decode("utf-8")
            try:
                message = OutboxMessage.decode(bytes(raw_value), expected_id=expected_id)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if message.id not in self._native_receipts:
                pending.append(message)
        return pending

    def dispatch(
        self,
        publish: Callable[[str, dict[str, Any], dict[str, Any]], Any],
        *,
        limit: int | None = None,
    ) -> int:
        """Publish pending messages and acknowledge successful deliveries.

        A failed publish leaves the message pending. A successful publish moves
        its durable record from ``pending`` to ``delivered`` in one local Store
        transaction.
        """
        delivered = 0
        for message in self.pending():
            if limit is not None and delivered >= limit:
                break
            publish(message.topic, message.payload, message.metadata)
            receipt = self._native_receipts.get(message.id)
            if receipt is not None:
                self._native.ack_outbox_event(*receipt)
            elif self._native_collections:
                tx = self._native.transaction()
                if not hasattr(tx, "delete_record"):
                    raise StoreProviderError(
                        "Store transaction lacks native collection deletion"
                    )
                tx.delete_record(
                    _OUTBOX_PENDING_COLLECTION, message.id.encode("utf-8")
                )
                tx.upsert_record(
                    _OUTBOX_DELIVERED_COLLECTION,
                    message.id.encode("utf-8"),
                    message.encode(),
                    indexes=[],
                )
                tx.commit()
            else:
                tx = self._native.transaction()
                tx.delete(_OUTBOX_PENDING_PREFIX + message.id.encode())
                tx.put(_OUTBOX_DELIVERED_PREFIX + message.id.encode(), message.encode())
                tx.commit()
            delivered += 1
        return delivered

    def dispatch_events(
        self, event_bus: Any | None = None, *, limit: int | None = None
    ) -> int:
        """Dispatch pending messages through the configured Runtime EventBus."""
        if event_bus is None:
            from voodoo.adapters.registry import registry

            event_bus = registry.get_events()

        def publish(
            topic: str, payload: dict[str, Any], metadata: dict[str, Any]
        ) -> Any:
            return event_bus.publish(topic, payload, **metadata)

        return self.dispatch(publish, limit=limit)


def transaction(runtime_store: RuntimeStore | None = None) -> RuntimeTransaction:
    """Create an atomic transaction over the active Runtime Store."""
    return RuntimeTransaction(runtime_store)


def dispatch_outbox(
    publish: Callable[[str, dict[str, Any], dict[str, Any]], Any],
    *,
    runtime_store: RuntimeStore | None = None,
    limit: int | None = None,
) -> int:
    """Dispatch pending Runtime outbox records using a caller-owned publisher."""
    return OutboxDispatcher(runtime_store).dispatch(publish, limit=limit)


def dispatch_events(
    *,
    event_bus: Any | None = None,
    runtime_store: RuntimeStore | None = None,
    limit: int | None = None,
) -> int:
    """Dispatch pending Runtime outbox records through the configured EventBus."""
    return OutboxDispatcher(runtime_store).dispatch_events(event_bus, limit=limit)
