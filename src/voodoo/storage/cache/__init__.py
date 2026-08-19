"""Voodoo cache capability — key/value caching (Sprint 13).

``MemoryCache`` is the default provider: process-local, no TTL, no
persistence. ``RedisCache`` (``[redis]`` extra) is the production backend
with TTL support and durability.
"""

from voodoo.storage.cache.interfaces import CacheCapabilities, VoodooCache
from voodoo.storage.cache.memory import MemoryCache
from voodoo.storage.cache.redis import RedisCache

__all__ = ["CacheCapabilities", "MemoryCache", "RedisCache", "VoodooCache"]
