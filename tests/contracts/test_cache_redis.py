"""Redis cache adapter contract tests (spec §9–§10, Sprint 13).

The same ``CacheContractTests`` suite used for ``MemoryCache`` runs against
a real Redis server when ``VOODOO_TEST_REDIS_URL`` is set — CI provides one
via a service container. Locally this module is skipped when no server is
available, so the default ``pytest`` run stays green without redis-py or a
running server.
"""

import os
import time

import pytest

from tests.contracts.test_cache import CacheContractTests

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


class TestRedisCacheContract(CacheContractTests):
    def make_cache(self):
        from voodoo.storage.cache import RedisCache

        return RedisCache(URL)

    def test_redis_capabilities(self, cache):
        caps = cache.capabilities()
        assert caps.provider == "redis"
        assert caps.ttl is True
        assert caps.durable is True

    def test_ttl_expires(self, cache):
        cache.set("k", "v", ttl=1)
        assert cache.get("k") == "v"
        time.sleep(1.2)
        assert cache.get("k") is None
