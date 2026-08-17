"""Voodoo storage package.

Two concerns live here:

- ``voodoo.storage.manager`` — the legacy ``StorageManager`` facade over
  local-filesystem / S3-compatible uploads (import-compatible re-export of
  the former flat ``voodoo/storage.py`` module).
- ``voodoo.storage.database`` — the ``VoodooDatabase`` capability adapters
  (SQLite default, PostgreSQL later) that own all durable schema through
  the migration runner.
"""

from voodoo.storage.manager import StorageManager, storage

__all__ = ["StorageManager", "storage"]
