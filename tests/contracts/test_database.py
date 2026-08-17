"""Database adapter contract tests (spec §29).

``DatabaseContractTests`` is the portability suite every ``VoodooDatabase``
implementation must pass unchanged — SQLite today, PostgreSQL in a later
sprint. Provider-specific behavior (runner internals, constructor
validation, pragmas) gets its own tests on top.
"""

import pytest

from voodoo.storage.database import SQLiteDatabase
from voodoo.storage.database.interfaces import Migration

CONTRACT_MIGRATION = Migration(
    version=1,
    name="contract_items",
    statements=(
        "CREATE TABLE IF NOT EXISTS contract_items ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL)",
    ),
)


class DatabaseContractTests:
    """Mixin run against every database adapter."""

    def make_database(self, tmp_path):
        raise NotImplementedError

    @pytest.fixture(autouse=True)
    async def database(self, tmp_path):
        db = self.make_database(tmp_path)
        await db.connect()
        await db.migrate()
        yield db
        await db.close()

    async def test_declares_provider_and_capabilities(self, database):
        assert isinstance(database.provider, str) and database.provider
        caps = database.capabilities()
        assert caps.transactions is True
        assert caps.migrations is True

    async def test_migration_ledger_tracks_applied_versions(self, database):
        rows = await database.fetch_all("SELECT version FROM schema_migrations")
        versions = [row["version"] for row in rows]
        assert versions == sorted(versions)
        assert 1 in versions  # contract_items baseline
        assert database.current_version() >= 1

    async def test_migrations_are_idempotent(self, database):
        before = await database.fetch_all(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        await database.migrate()
        await database.migrate()
        after = await database.fetch_all(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        assert before == after

    async def test_write_read_roundtrip(self, database):
        await database.execute(
            "INSERT INTO contract_items (name) VALUES (?)", ("alpha",)
        )
        row = await database.fetch_one(
            "SELECT name FROM contract_items WHERE name = ?", ("alpha",)
        )
        assert row is not None and row["name"] == "alpha"
        rows = await database.fetch_all("SELECT name FROM contract_items")
        assert [r["name"] for r in rows] == ["alpha"]

    async def test_transaction_commits_on_success(self, database):
        async with database.transaction() as conn:
            await conn.execute("INSERT INTO contract_items (name) VALUES ('t1')")
            await conn.execute("INSERT INTO contract_items (name) VALUES ('t2')")
        count = await database.fetch_one("SELECT COUNT(*) AS n FROM contract_items")
        assert count["n"] == 2

    async def test_transaction_rolls_back_on_error(self, database):
        with pytest.raises(RuntimeError, match="boom"):
            async with database.transaction() as conn:
                await conn.execute("INSERT INTO contract_items (name) VALUES ('x')")
                raise RuntimeError("boom")
        count = await database.fetch_one("SELECT COUNT(*) AS n FROM contract_items")
        assert count["n"] == 0

    async def test_data_survives_reconnect(self, database, tmp_path):
        await database.execute("INSERT INTO contract_items (name) VALUES ('durable')")
        await database.close()
        reopened = self.make_database(tmp_path)
        await reopened.connect()
        await reopened.migrate()
        try:
            row = await reopened.fetch_one(
                "SELECT name FROM contract_items WHERE name = ?", ("durable",)
            )
            assert row is not None
        finally:
            await reopened.close()


class TestSQLiteDatabase(DatabaseContractTests):
    def make_database(self, tmp_path) -> SQLiteDatabase:
        return SQLiteDatabase(
            str(tmp_path / "contract.db"), migrations=(CONTRACT_MIGRATION,)
        )

    async def test_sqlite_capabilities(self, database):
        caps = database.capabilities()
        assert caps.provider == "sqlite"
        assert caps.native_json is False
        assert caps.concurrent_writers is False

    async def test_sqlite_wal_mode_on_file_backed_db(self, database):
        row = await database.fetch_one("PRAGMA journal_mode")
        assert row is not None and str(row[0]).lower() == "wal"

    async def test_connection_required_before_use(self, tmp_path):
        db = SQLiteDatabase(str(tmp_path / "closed.db"))
        with pytest.raises(RuntimeError, match="not connected"):
            _ = db.connection

    async def test_rerunnable_migration_fn_runs_every_migrate(self, tmp_path):
        calls: list[str] = []

        async def marker(db) -> None:
            calls.append(db.provider)

        db = SQLiteDatabase(
            str(tmp_path / "rerun.db"),
            migrations=(
                CONTRACT_MIGRATION,
                Migration(version=3, name="counter", fn=marker, rerun=True),
            ),
        )
        await db.connect()
        try:
            await db.migrate()  # first application
            await db.migrate()  # rerun branch
            assert calls == [db.provider, db.provider]
            rows = await db.fetch_all(
                "SELECT version FROM schema_migrations WHERE version = 3"
            )
            assert len(rows) == 1  # ledger row recorded once
        finally:
            await db.close()

    async def test_duplicate_migration_versions_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="duplicate migration version"):
            SQLiteDatabase(
                str(tmp_path / "dup.db"),
                migrations=(CONTRACT_MIGRATION, Migration(version=1, name="other")),
            )
