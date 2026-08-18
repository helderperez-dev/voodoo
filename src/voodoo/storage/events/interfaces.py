"""Event bus capability interface (Sprint 7)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from voodoo.adapters.capabilities import EventBusCapabilities

__all__ = ["EventBusCapabilities", "VoodooEventBus"]


class VoodooEventBus(Protocol):
    provider: str

    def capabilities(self) -> EventBusCapabilities: ...

    def publish(
        self, event_type: str, payload: Any, **envelope: Any
    ) -> dict[str, Any]: ...

    def subscribe(self, event_type: str, handler: Callable) -> None: ...

    def replay(self, event_type: str, handler: Callable) -> int: ...
