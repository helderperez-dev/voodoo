"""Compatibility facade for voodoo.runtime.agency.goal_store."""

from voodoo.runtime.agency.goal_store import (
    GoalStore,
    SQLiteGoalStore,
    VoodooStoreGoalStore,
)

__all__ = ["GoalStore", "SQLiteGoalStore", "VoodooStoreGoalStore"]
