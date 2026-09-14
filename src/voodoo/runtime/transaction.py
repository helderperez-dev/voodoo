"""Provider-neutral atomic boundary for Store-backed Runtime state.

Sprint 28.11 deliberately exposes only semantics that Voodoo Store 0.2.x can
actually commit atomically: KV mutations, Collection upserts, and durable
outbox records staged in the same native transaction. Jobs, external effects,
and work performed by another node are not claimed to be part of this atomic
boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from voodoo.runtime.store import RuntimeStore, StoreProviderError, get_active_runtime_store

__all__ = ["OutboxMessage", "RuntimeTransaction", "transaction"]

_OUTBOX_PREFIX = b"runtime:outbox:pending:"


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
                "id": self.id,
                "topic": self.topic,
                "payload": self.payload,
                "metadata": self.metadata,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


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
            raise StoreProviderError("RuntimeStore must be started before a transaction")
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
        self.put(_OUTBOX_PREFIX + message.id.encode(), message.encode())
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

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self._finished:
            return False
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def transaction(runtime_store: RuntimeStore | None = None) -> RuntimeTransaction:
    """Create an atomic transaction over the active Runtime Store."""
    return RuntimeTransaction(runtime_store)
