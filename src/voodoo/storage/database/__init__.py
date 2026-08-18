"""Voodoo database adapters (spec §11).

SQLite is the embedded default; PostgreSQL arrives behind the same
``VoodooDatabase`` protocol as an optional extra. Migrations form one global
version namespace: 1 = user-model baseline (registered by ``voodoo.data``),
2+ reserved by the framework, 100+ available to applications.
"""

from voodoo.storage.database.interfaces import (
    DatabaseCapabilities,
    Migration,
    VoodooDatabase,
)
from voodoo.storage.database.sqlite import (
    FRAMEWORK_MIGRATIONS,
    LEDGER_TABLE,
    SQLiteDatabase,
    register_framework_migration,
)

__all__ = [
    "DatabaseCapabilities",
    "FRAMEWORK_MIGRATIONS",
    "LEDGER_TABLE",
    "Migration",
    "SQLiteDatabase",
    "VoodooDatabase",
    "register_framework_migration",
]
