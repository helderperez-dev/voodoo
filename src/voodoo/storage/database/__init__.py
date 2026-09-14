"""Optional SQL database adapters.

The core interfaces are import-safe without SQL dependencies. SQLite and
PostgreSQL implementations are loaded only when their adapter symbols are
requested explicitly.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from voodoo.storage.database.interfaces import (
    DatabaseCapabilities,
    Migration,
    VoodooDatabase,
)

__all__ = [
    "DatabaseCapabilities",
    "Migration",
    "VoodooDatabase",
    "FRAMEWORK_MIGRATIONS",
    "LEDGER_TABLE",
    "PostgresDatabase",
    "SQLiteDatabase",
    "register_framework_migration",
]

_LAZY_EXPORTS = {
    "PostgresDatabase": ("voodoo.storage.database.postgres", "PostgresDatabase"),
    "SQLiteDatabase": ("voodoo.storage.database.sqlite", "SQLiteDatabase"),
    "FRAMEWORK_MIGRATIONS": ("voodoo.storage.database.sqlite", "FRAMEWORK_MIGRATIONS"),
    "LEDGER_TABLE": ("voodoo.storage.database.sqlite", "LEDGER_TABLE"),
    "register_framework_migration": (
        "voodoo.storage.database.sqlite",
        "register_framework_migration",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'voodoo.storage.database' has no attribute {name!r}")
    module_name, symbol = target
    value = getattr(import_module(module_name), symbol)
    globals()[name] = value
    return value
