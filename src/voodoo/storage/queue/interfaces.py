"""Voodoo queue capability interface (spec §12).

Background work is a *durable* runtime concept: tasks are records that
survive process restarts, are claimed transactionally under a lease, and
retry with backoff until they succeed or exhaust their attempt budget.
The in-memory ``asyncio.Queue`` broker remains available as an explicit
``VOODOO_QUEUE_PROVIDER=memory`` choice for ephemeral, non-critical work.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from voodoo.adapters.capabilities import QueueCapabilities

__all__ = [
    "ACTIVE_STATUSES",
    "QueueCapabilities",
    "QueueStats",
    "TaskRecord",
    "TaskStatus",
    "VoodooQueue",
]


class TaskStatus(enum.StrEnum):
    """Durable task lifecycle.

    ``pending``/``retrying`` rows are claimable once ``available_at``
    passes; ``running`` rows hold a lease owned by ``locked_by``. A claim
    atomically moves a row to ``running`` (the spec's CLAIMED→RUNNING
    transition collapses into the single transactional claim statement).
    """

    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED)


ACTIVE_STATUSES = (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.RETRYING)


@dataclass(frozen=True)
class TaskRecord:
    """A durable queued task — JSON-compatible at every field (spec §48)."""

    id: int
    type: str
    payload: Any
    status: TaskStatus
    priority: int = 0
    available_at: datetime | None = None
    attempts: int = 0
    max_attempts: int = 1
    locked_by: str | None = None
    locked_at: datetime | None = None
    lease_until: datetime | None = None
    idempotency_key: str | None = None
    trace_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status.terminal

    def describe(self) -> dict[str, Any]:
        """JSON-ready view for CLI/API output."""
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "status": self.status.value,
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "available_at": self.available_at.isoformat()
            if self.available_at
            else None,
            "locked_by": self.locked_by,
            "lease_until": self.lease_until.isoformat() if self.lease_until else None,
            "idempotency_key": self.idempotency_key,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "last_error": self.last_error,
        }


@dataclass(frozen=True)
class QueueStats:
    total: int = 0
    pending: int = 0
    running: int = 0
    retrying: int = 0
    completed: int = 0
    failed: int = 0

    def describe(self) -> dict[str, int]:
        return {
            "total": self.total,
            "pending": self.pending,
            "running": self.running,
            "retrying": self.retrying,
            "completed": self.completed,
            "failed": self.failed,
        }


class VoodooQueue(Protocol):
    """Backend-neutral durable task queue."""

    provider: str

    async def setup(self) -> None:
        """Ensure schema exists (idempotent)."""
        ...

    async def enqueue(
        self,
        task_type: str,
        payload: Any,
        *,
        priority: int = 0,
        delay: float = 0.0,
        max_attempts: int = 1,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
    ) -> TaskRecord:
        """Persist a task. With an ``idempotency_key`` that is already
        active (pending/running/retrying), returns the existing record
        instead of inserting a duplicate (at-least-once, deduped in flight).
        """
        ...

    async def claim(
        self,
        worker: str,
        *,
        types: Sequence[str] | None = None,
        lease_seconds: float = 60.0,
    ) -> TaskRecord | None:
        """Atomically claim the highest-priority ready task for ``worker``.

        Sets status to ``running`` with a lease; ``None`` when nothing is
        claimable. Concurrent claims never return the same task.
        """
        ...

    async def heartbeat(
        self, task_id: int, worker: str, *, lease_seconds: float = 60.0
    ) -> bool:
        """Extend the lease of a task this worker owns. False if lost."""
        ...

    async def complete(self, task_id: int, worker: str) -> bool:
        """Mark a task completed. False if not owned / not running."""
        ...

    async def fail(
        self,
        task_id: int,
        worker: str,
        error: str,
        *,
        backoff_base: float = 1.0,
    ) -> TaskRecord | None:
        """Record failure; requeue with exponential backoff when attempts
        remain, else mark failed. Returns the updated record.
        """
        ...

    async def release(self, task_id: int, worker: str) -> bool:
        """Give a claimed task back to the pending pool immediately
        (graceful shutdown). Attempts already spent are kept."""
        ...

    async def release_expired(self) -> int:
        """Reclaim tasks whose lease expired (dead workers).

        Requeues when attempts remain, marks failed otherwise.
        Returns the number of reclaimed tasks.
        """
        ...

    async def retry(self, task_id: int) -> TaskRecord | None:
        """Manually requeue a failed task with a fresh attempt budget."""
        ...

    async def list(
        self,
        *,
        status: TaskStatus | str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[TaskRecord]:
        """Recent tasks, newest first (inspection/CLI)."""
        ...

    async def stats(self) -> QueueStats:
        """Counts by status."""
        ...

    def capabilities(self) -> QueueCapabilities: ...


# Re-exported for ergonomic queue field defaults.
__all__ = [
    "ACTIVE_STATUSES",
    "QueueCapabilities",
    "QueueStats",
    "TaskRecord",
    "TaskStatus",
    "VoodooQueue",
]
