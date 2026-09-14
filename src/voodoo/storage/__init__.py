"""Voodoo storage namespace.

The default package import is dependency-light. Store-native runtime paths do
not import SQLite, PostgreSQL, Redis, or S3 adapters. Compatibility adapters are
resolved lazily only when their public symbols are requested explicitly.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from voodoo.storage.manager import StorageManager, storage

__all__ = [
    "StorageManager",
    "storage",
    "EventBusCapabilities",
    "VoodooEventBus",
    "VoodooStoreEventBus",
    "LocalEventBus",
    "SQLiteEventBus",
    "PostgresEventStore",
    "SQLiteExecutionStore",
    "PostgresExecutionStore",
    "VoodooStoreExecutionStore",
    "VoodooQueue",
    "VoodooStoreQueue",
    "MemoryQueue",
    "SQLiteQueue",
    "PostgresQueue",
    "RedisQueue",
    "CacheCapabilities",
    "VoodooCache",
    "MemoryCache",
    "RedisCache",
]

_LAZY_EXPORTS = {
    "EventBusCapabilities": (
        "voodoo.storage.events.interfaces",
        "EventBusCapabilities",
    ),
    "VoodooEventBus": ("voodoo.storage.events.interfaces", "VoodooEventBus"),
    "VoodooStoreEventBus": ("voodoo.storage.events.store", "VoodooStoreEventBus"),
    "LocalEventBus": ("voodoo.storage.events.local", "LocalEventBus"),
    "SQLiteEventBus": ("voodoo.storage.events.sqlite", "SQLiteEventBus"),
    "PostgresEventStore": ("voodoo.storage.events.postgres", "PostgresEventStore"),
    "SQLiteExecutionStore": (
        "voodoo.storage.execution.sqlite",
        "SQLiteExecutionStore",
    ),
    "PostgresExecutionStore": (
        "voodoo.storage.execution.postgres",
        "PostgresExecutionStore",
    ),
    "VoodooStoreExecutionStore": (
        "voodoo.storage.execution.store",
        "VoodooStoreExecutionStore",
    ),
    "VoodooQueue": ("voodoo.storage.queue.interfaces", "VoodooQueue"),
    "VoodooStoreQueue": ("voodoo.storage.queue.store", "VoodooStoreQueue"),
    "MemoryQueue": ("voodoo.storage.queue.memory", "MemoryQueue"),
    "SQLiteQueue": ("voodoo.storage.queue.sqlite", "SQLiteQueue"),
    "PostgresQueue": ("voodoo.storage.queue.postgres", "PostgresQueue"),
    "RedisQueue": ("voodoo.storage.queue.redis", "RedisQueue"),
    "CacheCapabilities": ("voodoo.storage.cache.interfaces", "CacheCapabilities"),
    "VoodooCache": ("voodoo.storage.cache.interfaces", "VoodooCache"),
    "MemoryCache": ("voodoo.storage.cache.memory", "MemoryCache"),
    "RedisCache": ("voodoo.storage.cache.redis", "RedisCache"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'voodoo.storage' has no attribute {name!r}")
    module_name, symbol = target
    value = getattr(import_module(module_name), symbol)
    globals()[name] = value
    return value
