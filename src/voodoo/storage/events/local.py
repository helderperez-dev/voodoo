"""In-process event bus (Sprint 7)."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from typing import Any

from voodoo.storage.events.interfaces import EventBusCapabilities


class LocalEventBus:
    """In-process event bus — mesh behavior without durability."""

    provider = "local"

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def capabilities(self) -> EventBusCapabilities:
        return EventBusCapabilities(
            provider=self.provider,
            durable=False,
            replay=False,
            ordering=True,
            delivery="at_most_once",
        )

    def publish(self, event_type: str, payload: Any, **envelope: Any) -> dict[str, Any]:
        """Publish an event to subscribers. Returns the envelope."""
        from voodoo.telemetry import trace_id_var

        ev = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": time.time(),
            "source": envelope.get("source", "voodoo"),
            "subject": envelope.get("subject"),
            "correlation_id": envelope.get("correlation_id", trace_id_var.get()),
            "causation_id": envelope.get("causation_id"),
            "payload": payload,
            "schema_version": envelope.get("schema_version", 1),
        }
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
        return 0
