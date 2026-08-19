"""Voodoo cache capability interface (Sprint 13).

Caching is a first-class runtime capability: providers declare what they
guarantee through :class:`CacheCapabilities` (TTL support, durability) and
code that *requires* a feature calls :func:`~voodoo.adapters.capabilities.require`
so an unsupported operation fails loudly instead of silently degrading.

The default provider is the in-process :class:`MemoryCache`; ``RedisCache``
(``[redis]`` extra) is the production backend with TTL + durability.
"""

from __future__ import annotations

from typing import Any, Protocol

from voodoo.adapters.capabilities import CacheCapabilities

__all__ = ["CacheCapabilities", "VoodooCache"]


class VoodooCache(Protocol):
    """Backend-neutral key/value cache capability.

    Every implementation provides get/set/delete/clear plus a capability
    declaration. ``set`` accepts an optional ``ttl`` (seconds); providers
    that cannot honor TTLs must reject it loudly via ``require`` rather
    than silently ignoring it (spec §10).
    """

    provider: str

    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any, *, ttl: float | None = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def clear(self) -> None: ...

    def capabilities(self) -> CacheCapabilities: ...
