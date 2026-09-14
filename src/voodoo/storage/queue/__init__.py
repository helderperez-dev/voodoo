"""Voodoo queue capability — durable background work (spec §12).

Voodoo Store is the target local-first durable provider. SQLite, Postgres,
Redis, and memory remain available as explicit adapters while Sprint 28
converges defaults onto the shared application Store.
"""

from voodoo.storage.queue.interfaces import (
    ACTIVE_STATUSES,
    QueueCapabilities,
    QueueStats,
    TaskRecord,
    TaskStatus,
    VoodooQueue,
)
from voodoo.storage.queue.memory import MemoryQueue
from voodoo.storage.queue.postgres import PostgresQueue
from voodoo.storage.queue.redis import RedisQueue
from voodoo.storage.queue.sqlite import TASKS_MIGRATION, TASKS_TABLE, SQLiteQueue
from voodoo.storage.queue.store import VoodooStoreQueue

__all__ = [
    "ACTIVE_STATUSES",
    "MemoryQueue",
    "PostgresQueue",
    "QueueCapabilities",
    "QueueStats",
    "RedisQueue",
    "SQLiteQueue",
    "TASKS_MIGRATION",
    "TASKS_TABLE",
    "TaskRecord",
    "TaskStatus",
    "VoodooQueue",
    "VoodooStoreQueue",
]
