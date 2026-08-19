"""Voodoo storage package.

Two concerns live here:

- ``voodoo.storage.manager`` — the legacy ``StorageManager`` facade over
  local-filesystem / S3-compatible uploads (import-compatible re-export of
  the former flat ``voodoo/storage.py`` module).
- ``voodoo.storage.database`` — the ``VoodooDatabase`` capability adapters
  (SQLite default, PostgreSQL later) that own all durable schema through
  the migration runner.
- ``voodoo.storage.events`` — event bus capability (Sprint 7).
"""

from voodoo.storage.cache import CacheCapabilities, MemoryCache, RedisCache, VoodooCache
from voodoo.storage.events import (
    EventBusCapabilities,
    LocalEventBus,
    PostgresEventStore,
    SQLiteEventBus,
    VoodooEventBus,
)
from voodoo.storage.execution import PostgresExecutionStore, SQLiteExecutionStore
from voodoo.storage.manager import StorageManager, storage
from voodoo.storage.queue import (
    PostgresQueue,
    RedisQueue,
    SQLiteQueue,
    VoodooQueue,
)

__all__ = [
    "StorageManager",
    "storage",
    "EventBusCapabilities",
    "VoodooEventBus",
    "LocalEventBus",
    "SQLiteEventBus",
    "PostgresEventStore",
    "SQLiteExecutionStore",
    "PostgresExecutionStore",
    "VoodooQueue",
    "SQLiteQueue",
    "PostgresQueue",
    "RedisQueue",
    "CacheCapabilities",
    "VoodooCache",
    "MemoryCache",
    "RedisCache",
]
