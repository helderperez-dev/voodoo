"""Voodoo Store-backed durable event bus.

Events are persisted as native Voodoo Store Topics inside the Runtime-owned
``application.vstore``. The adapter consumes the central Runtime Store boundary
and never opens a competing writer.
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

_TOPIC_PREFIX = b"runtime.events:"
_REPLAY_BATCH_SIZE = 1024


class VoodooStoreEventBus:
    """Durable event bus backed by native Voodoo Store Topics."""

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
        required = ("publish_topic", "read_topic")
        missing = [name for name in required if native is None or not hasattr(native, name)]
        if missing:
            raise ConfigurationError(
                "Voodoo Store 0.3+ native messaging is required for event persistence. "
                f"Missing Store capabilities: {', '.join(missing)}."
            )
        return native

    @staticmethod
    def _topic(event_type: str) -> bytes:
        encoded = event_type.encode("utf-8")
        return _TOPIC_PREFIX + encoded.hex().encode("ascii")

    def publish(self, event_type: str, payload: Any, **envelope: Any) -> dict[str, Any]:
        """Persist an event to a native Topic, then notify in-process subscribers."""
        from voodoo.observability import trace_id_var

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
        self._native().publish_topic(self._topic(event_type), encoded)

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
        """Replay persisted events in deterministic Topic-offset order."""
        store = self._native()
        topic = self._topic(event_type)
        offset = 0
        count = 0

        while True:
            entries = store.read_topic(topic, offset, _REPLAY_BATCH_SIZE)
            if not entries:
                break

            for entry_offset, raw_value in entries:
                try:
                    ev = json.loads(bytes(raw_value).decode("utf-8"))
                    handler(ev)
                    count += 1
                except Exception:
                    pass
                offset = int(entry_offset) + 1

            if len(entries) < _REPLAY_BATCH_SIZE:
                break

        return count

    def close(self) -> None:
        """Lifecycle is owned centrally by RuntimeStore."""
