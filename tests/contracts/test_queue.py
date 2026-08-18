"""Queue adapter contract tests (spec §12, §29).

``QueueContractTests`` is the portability suite every ``VoodooQueue``
implementation must pass unchanged — SQLite (default), Memory (ephemeral),
PostgreSQL (future). Provider-specific behavior (SQL dialect, concurrency)
gets its own tests on top.
"""

import asyncio

import pytest

from voodoo.storage.queue import TaskStatus


class QueueContractTests:
    """Mixin run against every queue adapter."""

    def make_queue(self):
        raise NotImplementedError

    @pytest.fixture(autouse=True)
    async def queue(self):
        q = self.make_queue()
        await q.setup()
        yield q

    async def test_enqueue_and_stats(self, queue):
        stats = await queue.stats()
        assert stats.total == 0
        task = await queue.enqueue("email", {"to": "a@b.com"})
        assert task.type == "email"
        assert task.payload == {"to": "a@b.com"}
        assert task.status == TaskStatus.PENDING
        assert task.id > 0
        stats = await queue.stats()
        assert stats.pending == 1

    async def test_claim_returns_none_when_empty(self, queue):
        task = await queue.claim("w1")
        assert task is None

    async def test_claim_and_complete(self, queue):
        await queue.enqueue("email", {"x": 1})
        task = await queue.claim("w1")
        assert task is not None
        assert task.status == TaskStatus.RUNNING
        assert task.locked_by == "w1"
        ok = await queue.complete(task.id, "w1")
        assert ok is True
        stats = await queue.stats()
        assert stats.completed == 1
        assert stats.pending == 0

    async def test_claim_fails_from_wrong_worker(self, queue):
        await queue.enqueue("t", {})
        task = await queue.claim("w1")
        assert task is not None
        # Worker w2 cannot complete w1's task
        ok = await queue.complete(task.id, "w2")
        assert ok is False

    async def test_fail_retries_until_max_attempts(self, queue):
        await queue.enqueue("flaky", {}, max_attempts=3)
        for attempt in range(3):
            task = await queue.claim("w1")
            assert task is not None, f"expected claim on attempt {attempt}"
            assert task.attempts == attempt + 1
            result = await queue.fail(task.id, "w1", f"boom-{attempt}", backoff_base=0)
            assert result is not None

        stats = await queue.stats()
        assert stats.failed == 1

    async def test_fail_with_remaining_attempts_requeues(self, queue):
        await queue.enqueue("retry_me", {}, max_attempts=2)
        task = await queue.claim("w1")
        result = await queue.fail(task.id, "w1", "transient", backoff_base=0)
        assert result is not None
        assert result.status == TaskStatus.RETRYING
        task2 = await queue.claim("w2", lease_seconds=0.1)
        assert task2 is not None
        assert task2.attempts == 2

    async def test_release_returns_to_pending(self, queue):
        await queue.enqueue("rel", {})
        task = await queue.claim("w1")
        ok = await queue.release(task.id, "w1")
        assert ok is True
        stats = await queue.stats()
        assert stats.pending == 1
        assert stats.running == 0

    async def test_release_wrong_worker_fails(self, queue):
        await queue.enqueue("rel", {})
        task = await queue.claim("w1")
        ok = await queue.release(task.id, "w2")
        assert ok is False

    async def test_idempotency_key_dedupes_in_flight(self, queue):
        t1 = await queue.enqueue("dedup", {"a": 1}, idempotency_key="k1")
        t2 = await queue.enqueue("dedup", {"a": 2}, idempotency_key="k1")
        assert t1.id == t2.id
        stats = await queue.stats()
        assert stats.pending == 1

    async def test_idempotency_key_reusable_after_complete(self, queue):
        t1 = await queue.enqueue("dedup", {}, idempotency_key="k1")
        task = await queue.claim("w1")
        await queue.complete(task.id, "w1")
        # After completion, same key can be reused
        t2 = await queue.enqueue("dedup", {}, idempotency_key="k1")
        assert t2.id != t1.id

    async def test_priority_ordering(self, queue):
        await queue.enqueue("p", {}, priority=1)
        await queue.enqueue("p", {}, priority=5)
        await queue.enqueue("p", {}, priority=3)
        task = await queue.claim("w1")
        assert task.priority == 5
        await queue.complete(task.id, "w1")
        task = await queue.claim("w1")
        assert task.priority == 3
        await queue.complete(task.id, "w1")
        task = await queue.claim("w1")
        assert task.priority == 1

    async def test_delayed_delivery(self, queue):
        caps = queue.capabilities()
        if caps.delayed_delivery is False:
            # Providers without delayed delivery must reject loudly (spec §10).
            from voodoo.adapters.capabilities import CapabilityError

            with pytest.raises(CapabilityError) as exc:
                await queue.enqueue("late", {}, delay=0.15)
            assert exc.value.feature == "delayed_delivery"
            return
        await queue.enqueue("late", {}, delay=0.15)
        # Not available yet
        task = await queue.claim("w1")
        assert task is None
        await asyncio.sleep(0.2)
        task = await queue.claim("w1")
        assert task is not None

    async def test_heartbeat_extends_lease(self, queue):
        await queue.enqueue("hb", {})
        await queue.claim("w1", lease_seconds=0.05)
        await asyncio.sleep(0.06)
        # Without heartbeat, lease should be expired
        reclaimed = await queue.release_expired()
        assert reclaimed >= 1

    async def test_heartbeat_prevents_expiry(self, queue):
        await queue.enqueue("hb2", {})
        task = await queue.claim("w1", lease_seconds=0.1)
        await asyncio.sleep(0.05)
        ok = await queue.heartbeat(task.id, "w1", lease_seconds=0.1)
        assert ok is True
        await asyncio.sleep(0.06)
        # Lease was extended, should still be running
        reclaimed = await queue.release_expired()
        assert reclaimed == 0

    async def test_release_expired_reclaims_dead_workers(self, queue):
        await queue.enqueue("dead", {}, max_attempts=1)
        await queue.claim("dead_worker", lease_seconds=0.05)
        await asyncio.sleep(0.06)
        reclaimed = await queue.release_expired()
        assert reclaimed == 1
        stats = await queue.stats()
        assert stats.failed == 1

    async def test_retry_resets_failed_task(self, queue):
        await queue.enqueue("retry", {}, max_attempts=1)
        task = await queue.claim("w1")
        await queue.fail(task.id, "w1", "bad")
        stats = await queue.stats()
        assert stats.failed == 1
        result = await queue.retry(task.id)
        assert result is not None
        assert result.status == TaskStatus.PENDING
        stats = await queue.stats()
        assert stats.pending == 1
        assert stats.failed == 0

    async def test_list_filters_by_status(self, queue):
        await queue.enqueue("a", {})
        await queue.enqueue("b", {})
        await queue.claim("w1")
        all_tasks = await queue.list()
        assert len(all_tasks) == 2
        pending = await queue.list(status=TaskStatus.PENDING)
        assert len(pending) == 1
        running = await queue.list(status=TaskStatus.RUNNING)
        assert len(running) == 1

    async def test_list_filters_by_type(self, queue):
        await queue.enqueue("type_a", {})
        await queue.enqueue("type_b", {})
        tasks = await queue.list(task_type="type_a")
        assert len(tasks) == 1
        assert tasks[0].type == "type_a"

    async def test_capabilities_declared(self, queue):
        caps = queue.capabilities()
        assert isinstance(caps.provider, str) and caps.provider
        assert caps.delivery == "at_least_once"
        assert caps.visibility_timeout is True

    async def test_concurrent_claims_never_duplicate(self, queue):
        """Two workers claiming simultaneously never get the same task."""
        await queue.enqueue("race", {})
        await queue.enqueue("race", {})
        results = await asyncio.gather(queue.claim("w1"), queue.claim("w2"))
        ids = [r.id for r in results if r is not None]
        assert len(ids) == 2
        assert ids[0] != ids[1]


class TestMemoryQueueContract(QueueContractTests):
    def make_queue(self):
        from voodoo.storage.queue import MemoryQueue

        return MemoryQueue()


class TestSQLiteQueueContract(QueueContractTests):
    def make_queue(self):
        import os
        import tempfile

        from voodoo.storage.database import SQLiteDatabase
        from voodoo.storage.queue import SQLiteQueue

        db = SQLiteDatabase(os.path.join(tempfile.mkdtemp(), "q.db"))
        self._db = db
        return SQLiteQueue(db)

    @pytest.fixture(autouse=True)
    async def queue(self):
        q = self.make_queue()
        await self._db.connect()
        await q.setup()
        yield q
        await self._db.close()

    async def test_setup_creates_tasks_table(self, queue):
        """SQLite-specific: the tasks table exists after setup."""
        rows = await self._db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        )
        assert len(rows) == 1

    async def test_sqlite_capabilities_durable(self, queue):
        caps = queue.capabilities()
        assert caps.durable is True
        assert caps.provider == "sqlite"

    async def test_data_survives_reconnect(self, queue):
        """SQLite-specific: tasks survive process restart."""
        await queue.enqueue("survive", {"x": 1})
        await self._db.close()
        await self._db.connect()
        await queue.setup()
        tasks = await queue.list(task_type="survive")
        assert len(tasks) == 1
        assert tasks[0].payload == {"x": 1}
