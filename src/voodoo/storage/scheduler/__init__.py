"""Durable scheduler storage.

Voodoo Store is the canonical local-first scheduler provider. SQLite remains
available only as an explicit compatibility adapter and is imported lazily.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from voodoo.storage.scheduler.store import VoodooStoreScheduleStore

__all__ = [
    "SQLiteScheduleStore",
    "VoodooStoreScheduleStore",
    "create_schedule_store",
]

_LAZY_EXPORTS = {
    "SQLiteScheduleStore": (
        "voodoo.storage.scheduler.sqlite",
        "SQLiteScheduleStore",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(
            f"module 'voodoo.storage.scheduler' has no attribute {name!r}"
        )
    module_name, symbol = target
    value = getattr(import_module(module_name), symbol)
    globals()[name] = value
    return value


def create_schedule_store(_legacy_path: str | Path | None = None):
    """Resolve the canonical Store-backed scheduler.

    ``_legacy_path`` is accepted temporarily so the current App lifecycle can
    retain its call shape. It is deliberately ignored: missing Store
    temporal-work capabilities are an actionable error and never trigger a
    SQLite fallback.
    """
    return VoodooStoreScheduleStore()
