"""PostgreSQL adapter contract tests (spec §29, Sprint 10).

The same ``DatabaseContractTests`` suite used for SQLite runs against a
real PostgreSQL server when ``VOODOO_TEST_DATABASE_URL`` is set — CI
provides one via a service container (``.github/workflows/ci.yml``).
Locally the module is skipped when no server is available, so the
default ``pytest`` run stays green without PostgreSQL installed.

The contract baseline uses ``BIGSERIAL`` so the id column is server-side
generated — no ``RETURNING``-specific assertions appear in the shared
mixin; provider-specific ones live on the subclass below.
"""

import os

import pytest

from tests.contracts.test_database import DatabaseContractTests
from voodoo.storage.database import PostgresDatabase
from voodoo.storage.database.interfaces import Migration

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_DATABASE_URL"),
    reason="VOODOO_TEST_DATABASE_URL not set (no PostgreSQL server available)",
)

# PostgreSQL has no AUTOINCREMENT: identity columns are the native idiom.
CONTRACT_MIGRATION_PG = Migration(
    version=1,
    name="contract_items",
    statements=(
        "CREATE TABLE IF NOT EXISTS contract_items ("
        "id BIGSERIAL PRIMARY KEY, "
        "name TEXT NOT NULL)",
    ),
)


class TestPostgresDatabase(DatabaseContractTests):
    def make_database(self, tmp_path) -> PostgresDatabase:
        return PostgresDatabase(
            os.environ["VOODOO_TEST_DATABASE_URL"],
            migrations=(CONTRACT_MIGRATION_PG,),
        )

    @pytest.fixture(autouse=True)
    async def database(self, tmp_path):
        # The base mixin gets a fresh SQLite file per test; the PG suite
        # shares one database URL, so drop the tables up front to give
        # each test the same clean slate (ledger + contract table).
        db = self.make_database(tmp_path)
        await db.connect()
        await db.execute("DROP TABLE IF EXISTS contract_items")
        await db.execute("DROP TABLE IF EXISTS schema_migrations")
        await db.migrate()
        yield db
        await db.close()

    async def test_postgres_capabilities(self, database):
        caps = database.capabilities()
        assert caps.provider == "postgres"
        assert caps.native_json is True
        assert caps.concurrent_writers is True

    async def test_transaction_is_atomic_across_statements(self, database):
        # psycopg's transaction() issues explicit BEGIN/COMMIT/ROLLBACK
        # even while the connection is in autocommit mode for plain
        # execute() calls — both must coexist on the same connection.
        async with database.transaction() as conn:
            await conn.execute("INSERT INTO contract_items (name) VALUES ('a')")
            await conn.execute("INSERT INTO contract_items (name) VALUES ('b')")
        count = await database.fetch_one("SELECT COUNT(*) AS n FROM contract_items")
        assert count["n"] == 2

        with pytest.raises(RuntimeError):
            async with database.transaction() as conn:
                await conn.execute("INSERT INTO contract_items (name) VALUES ('c')")
                raise RuntimeError("boom")
        count = await database.fetch_one("SELECT COUNT(*) AS n FROM contract_items")
        assert count["n"] == 2

    async def test_identity_column_generates_ids(self, database):
        await database.execute("INSERT INTO contract_items (name) VALUES ('first')")
        await database.execute("INSERT INTO contract_items (name) VALUES ('second')")
        rows = await database.fetch_all(
            "SELECT id, name FROM contract_items ORDER BY id"
        )
        ids = [row["id"] for row in rows]
        assert ids == [1, 2]
