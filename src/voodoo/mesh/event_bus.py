"""Mesh integration with the event bus (Sprint 7).

The mesh sits on top of the active :class:`~voodoo.storage.events.VoodooEventBus`
for durable event publication, while preserving the existing ``emit``/``on``
interface. Local handlers keep the mesh contract: they receive the *raw
payload*, not the event envelope (the envelope is the remote/durable boundary).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from voodoo.storage.events import LocalEventBus, VoodooEventBus


class EventBusAwareMesh:
    """A mesh whose durability comes from a :class:`VoodooEventBus`.

    Keeps the existing ``MeshNetwork`` surface (``emit``/``on``/``expose``)
    semantics: handlers registered via ``on()`` receive the raw payload.
    Durability and replay are delegated to the underlying bus.
    """

    def __init__(self, bus: VoodooEventBus | None = None) -> None:
        self.bus = bus or LocalEventBus()
        self._handlers: dict[str, list[Callable]] = {}

    @staticmethod
    def _wrap(handler: Callable) -> Callable:
        """Wrap a mesh handler so it receives the raw payload from an envelope."""

        def wrapper(event: dict[str, Any]) -> Any:
            return handler(event.get("payload"))

        return wrapper

    def on(self, event_type: str):
        """Decorator to register a handler for an event (receives raw payload)."""

        def decorator(func):
            wrapper = self._wrap(func)
            self.bus.subscribe(event_type, wrapper)
            self._handlers.setdefault(event_type, []).append(wrapper)
            return func

        return decorator

    async def emit(self, event_type: str, payload: Any, **envelope: Any) -> None:
        """Publish an event through the bus."""
        self.bus.publish(event_type, payload, **envelope)

    def replay(self, event_type: str) -> int:
        """Replay persisted events to registered handlers. Returns the count."""
        count = 0
        for wrapper in self._handlers.get(event_type, []):
            count = max(count, self.bus.replay(event_type, wrapper))
        return count

    def get_bus(self) -> VoodooEventBus:
        """Return the underlying event bus."""
        return self.bus
