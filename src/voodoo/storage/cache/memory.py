"""In-memory cache provider — the default, zero-infra cache.

Selected via ``VOODOO_CACHE_PROVIDER=memory`` (the default). Ephemeral:
data lives only for the process lifetime. TTLs are not supported — a
``set(ttl=...)`` call is rejected loudly with a :class:`CapabilityError`
(spec §10) rather than silently dropping the expiry, mirroring how the
memory queue rejects ``delay``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from voodoo.adapters.capabilities import CacheCapabilities, require
from voodoo.storage.cache.interfaces import VoodooCache


class MemoryCache:
    """Process-local dict-backed cache (no TTL, no persistence)."""

    provider = "memory"

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        if ttl is not None:
            require(
                self.capabilities(),
                "ttl",
                hint="use a durable cache provider (redis) for TTLs",
            )
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def capabilities(self) -> CacheCapabilities:
        return CacheCapabilities(
            provider=self.provider,
            ttl=False,
            durable=False,
        )


if TYPE_CHECKING:
    _protocol_check: VoodooCache = MemoryCache()
