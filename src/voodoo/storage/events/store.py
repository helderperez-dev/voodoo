"""Voodoo Store-backed durable event bus.

Events are persisted inside the Runtime-owned ``application.vstore`` and
replayed from the same durable substrate used by the rest of the Runtime. The
adapter consumes the central Runtime Store boundary and never opens a competing
writer.

Store 0.2.x does not yet expose the richer messaging subsystem through the
Python binding, so this adapter uses the durable KV/transaction contract as the
compatibility boundary. The public event API remains unchanged and can later be
moved to native Store Streams/Topics without application changes.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.store import acquire_runtime_store
from voodoo.storage.events.interfaces import EventBusCapabilities

_SEQUENCE_PREFIX = b"runtime:events:sequence:"
_EVENT_PREFIX = b"runtime:events:event:"


class VoodooStoreEventBus:
    """Durable event bus backed by the process-shared Runtime Store."""

    provider = "voodoo"

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def capabilities(self) -> EventBusCapabilities:
        return EventBusCapabilities(
            provider=self.provider,
            durable=True,
            replay=True,
            ordering=True,
            delivery="at_least_once",
        )

    def _native(self) -> Any:
        runtime = acquire_runtime_store()
        provider = runtime.provider or runtime.start()
        if provider is None:
            raise ConfigurationError("Voodoo Store is disabled for event persistence")
        native = getattr(provider, "native", None)
        if native is None:
            raise ConfigurationError(
                "The active Voodoo Store provider does not expose durable KV storage"
            )
        return native

    @staticmethod
    def _event_type_key(event_type: str) -> bytes:
        return event_type.encode("utf-8").hex().encode("ascii")

    @classmethod
    def _sequence_key(cls, event_type: str) -> bytes:
        return _SEQUENCE_PREFIX + cls._event_type_key(event_type)

    @classmethod
    def _event_key(cls, event_type: str, sequence: int) -> bytes:
        return (
            _EVENT_PREFIX
            + cls._event_type_key(event_type)
            + b":"
            + f"{sequence:020d}".encode("ascii")
        )

    @classmethod
    def _event_scan_prefix(cls, event_type: str) -> bytes:
        return _EVENT_PREFIX + cls._event_type_key(event_type) + b":"

    def publish(self, event_type: str, payload: Any, **envelope: Any) -> dict[str, Any]:
        """Persist an event atomically, then notify in-process subscribers."""
        from voodoo.telemetry import trace_id_var

        store = self._native()
        sequence_key = self._sequence_key(event_type)
        raw_sequence = store.get(sequence_key)
        sequence = int(bytes(raw_sequence).decode("ascii")) + 1 if raw_sequence else 1

        ev = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": envelope.get("source", "voodoo"),
            "subject": envelope.get("subject"),
            "correlation_id": envelope.get("correlation_id", trace_id_var.get()),
            "causation_id": envelope.get("causation_id"),
            "payload": payload,
            "schema_version": envelope.get("schema_version", 1),
        }
        encoded = json.dumps(
            ev,
            default=str,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        tx = store.transaction()
        tx.put(sequence_key, str(sequence).encode("ascii"))
        tx.put(self._event_key(event_type, sequence), encoded)
        tx.commit()

        for handler in self._handlers.get(event_type, []):
            try:
                result = handler(ev)
                if result is not None and hasattr(result, "__await__"):
                    asyncio.create_task(result)
            except Exception:
                pass
        return ev

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def replay(self, event_type: str, handler: Callable) -> int:
        """Replay persisted events in deterministic publication order."""
        count = 0
        for _raw_key, raw_value in self._native().scan_prefix(
            self._event_scan_prefix(event_type)
        ):
            try:
                ev = json.loads(bytes(raw_value).decode("utf-8"))
                handler(ev)
                count += 1
            except Exception:
                pass
        return count

    def close(self) -> None:
        """Lifecycle is owned centrally by RuntimeStore."""
