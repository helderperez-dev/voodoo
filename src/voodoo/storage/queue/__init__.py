"""Voodoo queue capability with Voodoo Store as the default backend."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from voodoo.storage.queue.interfaces import (
    ACTIVE_STATUSES,
    QueueCapabilities,
    QueueStats,
    TaskRecord,
    TaskStatus,
    VoodooQueue,
)
from voodoo.storage.queue.memory import MemoryQueue
from voodoo.storage.queue.store import VoodooStoreQueue

__all__ = [
    "ACTIVE_STATUSES",
    "MemoryQueue",
    "PostgresQueue",
    "QueueCapabilities",
    "QueueStats",
    "RedisQueue",
    "SQLiteQueue",
    "TASKS_MIGRATION",
    "TASKS_TABLE",
    "TaskRecord",
    "TaskStatus",
    "VoodooQueue",
    "VoodooStoreQueue",
]

_LAZY_EXPORTS = {
    "PostgresQueue": ("voodoo.storage.queue.postgres", "PostgresQueue"),
    "RedisQueue": ("voodoo.storage.queue.redis", "RedisQueue"),
    "SQLiteQueue": ("voodoo.storage.queue.sqlite", "SQLiteQueue"),
    "TASKS_MIGRATION": ("voodoo.storage.queue.sqlite", "TASKS_MIGRATION"),
    "TASKS_TABLE": ("voodoo.storage.queue.sqlite", "TASKS_TABLE"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'voodoo.storage.queue' has no attribute {name!r}")
    module_name, symbol = target
    value = getattr(import_module(module_name), symbol)
    globals()[name] = value
    return value
