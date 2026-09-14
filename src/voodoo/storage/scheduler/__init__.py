"""Durable scheduler storage.

Voodoo Store is the canonical local-first scheduler provider. SQLite remains
available only as an explicit compatibility adapter; the Runtime never falls
back to it when Store capabilities are missing.
"""

from __future__ import annotations

from pathlib import Path

from voodoo.storage.scheduler.sqlite import SQLiteScheduleStore
from voodoo.storage.scheduler.store import VoodooStoreScheduleStore


def create_schedule_store(_legacy_path: str | Path | None = None):
    """Resolve the canonical Store-backed scheduler.

    ``_legacy_path`` is accepted temporarily so the current App lifecycle can
    retain its call shape while Sprint 28 removes legacy path plumbing. It is
    deliberately ignored: missing Store temporal-work capabilities are an
    actionable error and never trigger a SQLite fallback.
    """
    return VoodooStoreScheduleStore()


__all__ = [
    "SQLiteScheduleStore",
    "VoodooStoreScheduleStore",
    "create_schedule_store",
]
