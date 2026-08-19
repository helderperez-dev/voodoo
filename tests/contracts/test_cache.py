"""Cache adapter contract tests (spec §9–§10, Sprint 13).

``CacheContractTests`` is the portability suite every ``VoodooCache``
implementation must pass unchanged — Memory (default, no TTL) and Redis
(production, TTL + durability). Provider-specific behavior (TTL expiry,
durability) gets its own tests on top.
"""

import pytest

from voodoo.adapters.capabilities import CapabilityError


class CacheContractTests:
    """Mixin run against every cache adapter."""

    def make_cache(self):
        raise NotImplementedError

    @pytest.fixture(autouse=True)
    def cache(self):
        c = self.make_cache()
        yield c
        c.clear()

    def test_get_missing_returns_default(self, cache):
        assert cache.get("nope") is None
        assert cache.get("nope", "fallback") == "fallback"

    def test_set_get_roundtrip(self, cache):
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_set_overwrites(self, cache):
        cache.set("k", "one")
        cache.set("k", "two")
        assert cache.get("k") == "two"

    def test_delete(self, cache):
        cache.set("k", "v")
        cache.delete("k")
        assert cache.get("k") is None

    def test_clear(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_ttl_gated_on_capability(self, cache):
        caps = cache.capabilities()
        if caps.ttl is False:
            # Providers without TTL must reject loudly (spec §10).
            with pytest.raises(CapabilityError) as exc:
                cache.set("k", "v", ttl=10)
            assert exc.value.feature == "ttl"
            return
        cache.set("k", "v", ttl=10)
        assert cache.get("k") == "v"

    def test_capabilities_declared(self, cache):
        caps = cache.capabilities()
        assert isinstance(caps.provider, str) and caps.provider
        assert isinstance(caps.ttl, bool)
        assert isinstance(caps.durable, bool)


class TestMemoryCacheContract(CacheContractTests):
    def make_cache(self):
        from voodoo.storage.cache import MemoryCache

        return MemoryCache()

    def test_memory_capabilities(self, cache):
        caps = cache.capabilities()
        assert caps.provider == "memory"
        assert caps.ttl is False
        assert caps.durable is False
