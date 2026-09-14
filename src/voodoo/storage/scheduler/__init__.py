"""Durable scheduler storage.

Voodoo Store is the target local-first scheduler provider. SQLite remains the
compatibility adapter while installations are still using a published Store
binding that predates Sprint 28.5 temporal-work APIs.
"""

from __future__ import annotations

from pathlib import Path

from voodoo.core.errors import ConfigurationError
from voodoo.storage.scheduler.sqlite import SQLiteScheduleStore
from voodoo.storage.scheduler.store import VoodooStoreScheduleStore


def create_schedule_store(fallback_path: str | Path):
    """Resolve Store-first scheduling with a compatibility fallback.

    The Framework currently supports the published Store 0.1.1 line, which
    does not expose schedule/cron bindings. Once a compatible Store release is
    installed this resolver automatically converges the application lifecycle
    onto the shared RuntimeStore. Explicit Store disablement likewise keeps the
    existing SQLite compatibility path available.
    """
    try:
        return VoodooStoreScheduleStore()
    except ConfigurationError:
        return SQLiteScheduleStore(fallback_path)


__all__ = [
    "SQLiteScheduleStore",
    "VoodooStoreScheduleStore",
    "create_schedule_store",
]
