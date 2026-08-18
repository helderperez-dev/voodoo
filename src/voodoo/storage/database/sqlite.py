"""SQLite implementation of the Voodoo database capability.

The local source of truth (spec §11): WAL journaling for file-backed
databases, ordered idempotent migrations tracked in ``schema_migrations``,
and commit/rollback transaction semantics. Every SQLite-backed runtime
subsystem persists through this adapter — never through aiosqlite directly.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import aiosqlite

from voodoo.storage.database.interfaces import (
    DatabaseCapabilities,
    Migration,
    VoodooDatabase,
)

LEDGER_TABLE = "schema_migrations"

# Framework-owned schema changes, dynamically registered by subsystems
# (tasks, executions, schedules, …). Version 1 is the user-model baseline
# registered by ``voodoo.data``; the framework reserves 2+. Migrations are
# re-merged on every ``migrate()`` call so late-imported subsystems still
# get their tables.
_FRAMEWORK_MIGRATIONS: list[Migration] = []
FRAMEWORK_MIGRATIONS = _FRAMEWORK_MIGRATIONS


def register_framework_migration(migration: Migration) -> None:
    """Register a framework-owned migration (called at import time).

    Idempotent: re-registering the same version/name is a no-op so that
    repeated imports (or test re-imports) don't blow up.
    """
    for existing in _FRAMEWORK_MIGRATIONS:
        if existing.version == migration.version:
            if existing.name == migration.name:
                return
            raise ValueError(
                f"duplicate migration version {migration.version} "
                f"({existing.name!r} vs {migration.name!r})"
            )
    _FRAMEWORK_MIGRATIONS.append(migration)


class SQLiteDatabase:
    """Embedded SQLite backend — the default Voodoo database."""

    provider = "sqlite"

    def __init__(self, path: str, migrations: Sequence[Migration] = ()) -> None:
        self.path = path
        self._extra_migrations = tuple(migrations)
        self._conn: aiosqlite.Connection | None = None
        self._version = 0
        # Early validation: duplicates among explicitly-provided migrations
        # are caught at construction. Framework migrations registered later
        # are re-validated on each migrate() call.
        self._merge_migrations()

    def _merge_migrations(self) -> tuple[Migration, ...]:
        by_version: dict[int, Migration] = {}
        for migration in (*_FRAMEWORK_MIGRATIONS, *self._extra_migrations):
            if migration.version in by_version:
                raise ValueError(
                    f"duplicate migration version {migration.version} "
                    f"({by_version[migration.version].name!r} vs {migration.name!r})"
                )
            by_version[migration.version] = migration
        return tuple(by_version[v] for v in sorted(by_version))

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError(
                f"sqlite database at {self.path!r} is not connected; "
                "call connect() first"
            )
        return self._conn

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        if self._conn is not None:
            return
        db_dir = os.path.dirname(self.path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        # Durability/concurrency pragmas. WAL is a no-op on :memory:.
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.commit()

    async def close(self) -> None:
        """Close the connection if open. No-op otherwise (keeps startup lazy).

        aiosqlite runs each connection on a dedicated non-daemon thread; an
        unclosed connection would keep the interpreter alive at shutdown.
        """
        if self._conn is not None:
            try:
                await self._conn.close()
            finally:
                self._conn = None

    # -- migrations ----------------------------------------------------------

    async def migrate(self) -> None:
        conn = self.connection
        await conn.execute(
            f"CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} ("
            "version INTEGER PRIMARY KEY,"
            "name TEXT NOT NULL,"
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        await conn.commit()

        applied = {
            row["version"]
            for row in await self.fetch_all(f"SELECT version FROM {LEDGER_TABLE}")
        }
        # Re-merge each time so late-imported subsystem migrations are picked up.
        for migration in self._merge_migrations():
            if migration.version not in applied:
                async with self.transaction():
                    for statement in migration.statements:
                        await conn.execute(statement)
                    if migration.fn is not None:
                        await migration.fn(self)
                    await conn.execute(
                        f"INSERT INTO {LEDGER_TABLE} (version, name) VALUES (?, ?)",
                        (migration.version, migration.name),
                    )
                self._version = migration.version
            elif migration.rerun and migration.fn is not None:
                # Idempotent re-runnable step: keep late-registered items
                # (e.g. models imported after the baseline) working.
                await migration.fn(self)

    def current_version(self) -> int:
        return self._version

    # -- queries -------------------------------------------------------------

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Run a block atomically: commit on success, rollback on error.

        Yields the raw connection so callers compose arbitrary statements;
        aiosqlite opens the implicit transaction on first DML.
        """
        conn = self.connection
        try:
            yield conn
        except BaseException:
            await conn.rollback()
            raise
        await conn.commit()

    async def execute(self, query: str, params: Sequence[Any] = ()) -> aiosqlite.Cursor:
        cursor = await self.connection.execute(query, params)
        await self.connection.commit()
        return cursor

    async def fetch_all(
        self, query: str, params: Sequence[Any] = ()
    ) -> list[aiosqlite.Row]:
        async with self.connection.execute(query, params) as cursor:
            return list(await cursor.fetchall())

    async def fetch_one(
        self, query: str, params: Sequence[Any] = ()
    ) -> aiosqlite.Row | None:
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchone()

    def capabilities(self) -> DatabaseCapabilities:
        return DatabaseCapabilities(
            provider=self.provider,
            transactions=True,
            migrations=True,
            native_json=False,  # JSON persisted as TEXT
            concurrent_writers=False,  # single writer at a time (WAL readers ok)
        )


if TYPE_CHECKING:
    # Structural conformance assertion — mypy errors here if the adapter
    # drifts from the VoodooDatabase protocol.
    _protocol_check: VoodooDatabase = SQLiteDatabase("check")
