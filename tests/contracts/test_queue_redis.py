"""Redis queue adapter contract tests (spec §12, §29, Sprint 13).

The same ``QueueContractTests`` suite used for SQLite/Memory/Postgres runs
against a real Redis server when ``VOODOO_TEST_REDIS_URL`` is set — CI
provides one via a service container. Locally this module is skipped when
no server is available, so the default ``pytest`` run stays green.

Provider-specific extras: the claim is an atomic Lua script so the
concurrency tests exercise real cross-connection atomicity, and (unlike
SQLite/WAL) the uniqueness of a claim is guaranteed by Redis, not a
process-local connection.
"""

import os

import pytest

from tests.contracts.test_queue import QueueContractTests
from voodoo.storage.queue.redis import RedisQueue

redis = pytest.importorskip("redis")

pytestmark = pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_REDIS_URL"),
    reason="VOODOO_TEST_REDIS_URL not set (no Redis server available)",
)

URL = os.environ.get("VOODOO_TEST_REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(autouse=True)
def _flush():
    """Flush the test database before each test for isolation."""
    client = redis.Redis.from_url(URL, decode_responses=True)
    client.flushdb()
    client.close()
    yield


class TestRedisQueueContract(QueueContractTests):
    @pytest.fixture(autouse=True)
    async def queue(self):
        q = RedisQueue(URL)
        await q.setup()
        yield q
        await q.close()

    def make_queue(self):
        return RedisQueue(URL)

    async def test_redis_capabilities_durable(self, queue):
        caps = queue.capabilities()
        assert caps.durable is True
        assert caps.provider == "redis"
        assert caps.delayed_delivery is True
        assert caps.priority is True

    async def test_data_survives_reconnect(self):
        """Redis-specific: tasks survive a client reconnect."""
        q1 = RedisQueue(URL)
        await q1.setup()
        await q1.enqueue("survive", {"x": 1})
        await q1.close()

        q2 = RedisQueue(URL)
        await q2.setup()
        tasks = await q2.list(task_type="survive")
        assert len(tasks) == 1
        assert tasks[0].payload == {"x": 1}
        await q2.close()
