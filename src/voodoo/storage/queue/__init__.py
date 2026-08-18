"""Voodoo queue capability — durable background work (spec §12).

``SQLiteQueue`` is the default provider: tasks survive process restarts,
are claimed transactionally under a lease, and retry with backoff. The
legacy in-memory ``asyncio.Queue`` broker remains available when
``VOODOO_QUEUE_PROVIDER=memory``.
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
from voodoo.storage.queue.sqlite import TASKS_MIGRATION, TASKS_TABLE, SQLiteQueue

__all__ = [
    "ACTIVE_STATUSES",
    "MemoryQueue",
    "PostgresQueue",
    "QueueCapabilities",
    "QueueStats",
    "SQLiteQueue",
    "TASKS_MIGRATION",
    "TASKS_TABLE",
    "TaskRecord",
    "TaskStatus",
    "VoodooQueue",
]
