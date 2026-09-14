"""Event bus capability with Voodoo Store as the dependency-light default."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from voodoo.storage.events.interfaces import EventBusCapabilities, VoodooEventBus
from voodoo.storage.events.local import LocalEventBus
from voodoo.storage.events.store import VoodooStoreEventBus

__all__ = [
    "EventBusCapabilities",
    "VoodooEventBus",
    "VoodooStoreEventBus",
    "LocalEventBus",
    "PostgresEventStore",
    "SQLiteEventBus",
]

_LAZY_EXPORTS = {
    "PostgresEventStore": ("voodoo.storage.events.postgres", "PostgresEventStore"),
    "SQLiteEventBus": ("voodoo.storage.events.sqlite", "SQLiteEventBus"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'voodoo.storage.events' has no attribute {name!r}")
    module_name, symbol = target
    value = getattr(import_module(module_name), symbol)
    globals()[name] = value
    return value
