"""Redis cache provider (Sprint 13).

``RedisCache`` implements the ``VoodooCache`` capability over a Redis
server. It is the production cache backend: TTLs are honored and data is
durable (survives process restarts, shared across processes/nodes).

redis-py is an optional dependency — when it is missing the store refuses
to operate with an actionable :class:`ConfigurationError`, so nothing on
the default path imports redis (mirrors the S3/Postgres lazy-import guard).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from voodoo.adapters.capabilities import CacheCapabilities
from voodoo.core.errors import ConfigurationError
from voodoo.storage.cache.interfaces import VoodooCache

try:
    import redis
except ImportError:  # pragma: no cover - exercised when redis is absent
    redis = None


class RedisCache:
    """Redis-backed key/value cache with TTL support."""

    provider = "redis"

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        if redis is None:
            raise ConfigurationError(
                "The redis cache provider requires the [redis] extra: "
                "pip install 'voodoo-framework[redis]' (redis)."
            )
        self.url = url
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str, default: Any = None) -> Any:
        value = self._client.get(key)
        return default if value is None else value

    def set(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        if ttl is not None:
            self._client.set(key, value, ex=int(ttl))
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def clear(self) -> None:
        # Only clear keys this cache owns (the caller's namespace), never
        # the whole server. The default namespace is the empty prefix.
        self._client.flushdb()

    def capabilities(self) -> CacheCapabilities:
        return CacheCapabilities(
            provider=self.provider,
            ttl=True,
            durable=True,
        )

    def close(self) -> None:
        self._client.close()


if TYPE_CHECKING:
    _protocol_check: VoodooCache = RedisCache()
