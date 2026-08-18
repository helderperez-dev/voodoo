"""Event bus capability interface (Sprint 7)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class EventBusCapabilities:
    provider: str
    durable: bool = False
    replay: bool = False
    ordering: bool = True
    delivery: str = "at_most_once"


class VoodooEventBus(Protocol):
    provider: str

    def capabilities(self) -> EventBusCapabilities: ...

    def publish(
        self, event_type: str, payload: Any, **envelope: Any
    ) -> dict[str, Any]: ...

    def subscribe(self, event_type: str, handler: Callable) -> None: ...

    def replay(self, event_type: str, handler: Callable) -> int: ...
