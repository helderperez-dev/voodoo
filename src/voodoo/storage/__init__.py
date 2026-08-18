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

from voodoo.storage.events import (
    EventBusCapabilities,
    LocalEventBus,
    SQLiteEventBus,
    VoodooEventBus,
)
from voodoo.storage.manager import StorageManager, storage

__all__ = [
    "StorageManager",
    "storage",
    "EventBusCapabilities",
    "VoodooEventBus",
    "LocalEventBus",
    "SQLiteEventBus",
]
