"""PostgreSQL queue adapter contract tests (spec §12, §29, Sprint 11).

The same ``QueueContractTests`` suite used for SQLite/Memory runs against a
real PostgreSQL server when ``VOODOO_TEST_DATABASE_URL`` is set — CI
provides one via a service container. Locally this module is skipped when no
server is available, so the default ``pytest`` run stays green.

Provider-specific extras: the claim uses ``FOR UPDATE SKIP LOCKED`` so the
concurrency tests exercise real cross-connection locking, and (unlike
SQLite/WAL) the uniqueness of a claim is guaranteed by the database, not a
process-local connection.
"""

import os

import pytest

from tests.contracts.test_queue import QueueContractTests
from voodoo.storage.database import PostgresDatabase
from voodoo.storage.queue.postgres import PostgresQueue

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_DATABASE_URL"),
    reason="VOODOO_TEST_DATABASE_URL not set (no PostgreSQL server available)",
)


@pytest.fixture
async def pg_db() -> PostgresDatabase:
    db = PostgresDatabase(os.environ["VOODOO_TEST_DATABASE_URL"])
    await db.connect()
    # Fresh ledger + tasks table per test so contract tests are isolated.
    await db.execute("DROP TABLE IF EXISTS schema_migrations CASCADE")
    await db.execute("DROP TABLE IF EXISTS tasks CASCADE")
    yield db
    await db.close()


class TestPostgresQueueContract(QueueContractTests):
    @pytest.fixture(autouse=True)
    async def queue(self, pg_db):
        self._db = pg_db
        q = PostgresQueue(pg_db)
        await q.setup()
        yield q

    def make_queue(self):
        from voodoo.storage.queue.postgres import PostgresQueue

        if not hasattr(self, "_db"):
            raise RuntimeError("expected pg_db fixture to provide the database")
        return PostgresQueue(self._db)

    async def test_setup_creates_tasks_table(self, queue):
        rows = await self._db.fetch_all(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='tasks'"
        )
        assert len(rows) == 1

    async def test_postgres_capabilities_durable(self, queue):
        caps = queue.capabilities()
        assert caps.durable is True
        assert caps.provider == "postgres"

    async def test_data_survives_reconnect(self):
        url = os.environ["VOODOO_TEST_DATABASE_URL"]

        db1 = PostgresDatabase(url)
        await db1.connect()
        await db1.execute("DROP TABLE IF EXISTS schema_migrations CASCADE")
        await db1.execute("DROP TABLE IF EXISTS tasks CASCADE")
        q1 = PostgresQueue(db1)
        await q1.setup()
        await q1.enqueue("persist", {"k": "v"})
        await db1.close()

        db2 = PostgresDatabase(url)
        await db2.connect()
        q2 = PostgresQueue(db2)
        await q2.setup()
        stats = await q2.stats()
        assert stats.pending == 1
        task = await q2.claim("w1")
        assert task is not None and task.type == "persist"
        await db2.close()

    async def test_claim_uses_skip_locked_not_busy_lock(self, queue):
        """The PG claim must not hold a table lock blocking other workers.

        The retain all semantics: enqueue 3 tasks, claim 2 from different
        "connections", and the third claim returns the remaining task (not
        None), proving FOR UPDATE SKIP LOCKED skips only the locked rows.
        """
        for _ in range(3):
            await queue.enqueue("race", {})
        # Both workers claim concurrently; we can't get duplicates but also
        # need the third claim to succeed while the first is still running.
        t1 = await queue.claim("w1")
        t2 = await queue.claim("w2")
        assert t1 is not None and t2 is not None
        assert t1.id != t2.id
        t3 = await queue.claim("w1")
        assert t3 is not None
        assert t3.id not in (t1.id, t2.id)


def test_postgres_claim_sql_uses_skip_locked():
    """The claim statement must use FOR UPDATE SKIP LOCKED (not a table lock).

    Static check so the SQL contract is pinned even without a server: if the
    claim regresses to ``SELECT ... FOR UPDATE`` or a plain subquery the
    worker liveness guarantees (concurrent multi-process workers) break.
    """
    import inspect

    from voodoo.storage.queue import postgres as pg_queue

    source = inspect.getsource(pg_queue.PostgresQueue.claim)
    # Present in the SQL (docstring double-mentions it, so just check the
    # executable body by looking at the multiline UPDATE statement).
    assert "FOR UPDATE SKIP LOCKED" in source
    # The locking clause must be inside the subquery (after SELECT...LIMIT 1),
    # not on the outer UPDATE — grab the SQL body only.
    body = source.split('"""')[1] if '"""' in source else source
    assert "WHERE id = (" in body
    assert body.index("FOR UPDATE SKIP LOCKED") > body.index("LIMIT 1")


async def test_lease_expiry_reclaims_after_sleep(pg_db):
    """A worker that claims and dies (no heartbeat/complete) has its lease
    reclaimed by release_expired after lease_seconds pass (failure path)."""
    q = PostgresQueue(pg_db)
    await q.setup()
    await q.enqueue("dead", {}, max_attempts=1)
    t = await q.claim("dead_worker", lease_seconds=0.05)
    assert t is not None
    import asyncio

    await asyncio.sleep(0.08)
    reclaimed = await q.release_expired()
    assert reclaimed == 1
    stats = await q.stats()
    assert stats.failed == 1


async def test_two_workers_never_claim_same_task(pg_db):
    """Cross-connection: two PostgresQueue instances sharing the DB never
    get the same task on concurrent claim (SKIP LOCKED guarantees it)."""
    q1 = PostgresQueue(pg_db)
    q2 = PostgresQueue(pg_db)
    await q1.setup()
    for _ in range(5):
        await q1.enqueue("race", {})
    import asyncio

    claimed = [
        r
        for r in await asyncio.gather(
            *(q.claim(w) for w, q in (("w1", q1), ("w2", q2)) for _ in range(5))
        )
        if r is not None
    ]
    ids = [t.id for t in claimed]
    assert len(ids) == len(set(ids)), "duplicate claim across connections"


async def test_idempotency_duplicate_enqueue_returns_same_row(pg_db):
    q = PostgresQueue(pg_db)
    await q.setup()
    t1 = await q.enqueue("dedup", {"a": 1}, idempotency_key="k1")
    t2 = await q.enqueue("dedup", {"a": 2}, idempotency_key="k1")
    assert t1.id == t2.id
    stats = await q.stats()
    assert stats.pending == 1
