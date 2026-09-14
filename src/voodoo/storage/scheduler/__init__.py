"""Durable scheduler storage.

Voodoo Store is the canonical local-first scheduler provider. SQLite remains
available only as an explicit compatibility adapter; the Runtime never falls
back to it when Store capabilities are missing.
"""

from __future__ import annotations

from voodoo.storage.scheduler.sqlite import SQLiteScheduleStore
from voodoo.storage.scheduler.store import VoodooStoreScheduleStore


def create_schedule_store():
    """Resolve the canonical Store-backed scheduler.

    Missing temporal-work capabilities are an actionable configuration/runtime
    error. They must never silently change persistence semantics by falling
    back to SQLite.
    """
    return VoodooStoreScheduleStore()


__all__ = [
    "SQLiteScheduleStore",
    "VoodooStoreScheduleStore",
    "create_schedule_store",
]
