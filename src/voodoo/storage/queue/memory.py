"""In-memory queue provider — the legacy ``asyncio.Queue`` broker.

Kept for ephemeral, non-critical work where durability is not required.
Selected via ``VOODOO_QUEUE_PROVIDER=memory``. Not the default.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from voodoo.adapters.capabilities import require
from voodoo.storage.queue.interfaces import (
    QueueCapabilities,
    QueueStats,
    TaskRecord,
    TaskStatus,
)

_next_id = 0


def _gen_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


class MemoryQueue:
    """Ephemeral in-process queue (no persistence, no leases)."""

    provider = "memory"

    def __init__(self) -> None:
        self._tasks: dict[int, TaskRecord] = {}
        self._order: list[int] = []
        self._lock = asyncio.Lock()

    async def setup(self) -> None:
        pass

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
        if delay > 0:
            require(
                self.capabilities(),
                "delayed_delivery",
                hint="use a durable queue provider (sqlite) for delayed tasks",
            )
        async with self._lock:
            if idempotency_key is not None:
                for rec in self._tasks.values():
                    if rec.idempotency_key == idempotency_key and rec.status.value in (
                        "pending",
                        "running",
                        "retrying",
                    ):
                        return rec
            now = datetime.now(UTC)
            tid = _gen_id()
            rec = TaskRecord(
                id=tid,
                type=task_type,
                payload=payload,
                status=TaskStatus.PENDING,
                priority=priority,
                available_at=now + timedelta(seconds=delay) if delay else now,
                attempts=0,
                max_attempts=max(1, int(max_attempts)),
                idempotency_key=idempotency_key,
                trace_id=trace_id,
                created_at=now,
            )
            self._tasks[tid] = rec
            self._order.append(tid)
            return rec

    async def claim(
        self,
        worker: str,
        *,
        types: Sequence[str] | None = None,
        lease_seconds: float = 60.0,
    ) -> TaskRecord | None:
        async with self._lock:
            now = datetime.now(UTC)
            candidates = [
                tid
                for tid in self._order
                if self._tasks[tid].status in (TaskStatus.PENDING, TaskStatus.RETRYING)
                and self._tasks[tid].available_at
                and self._tasks[tid].available_at <= now
                and (types is None or self._tasks[tid].type in types)
            ]
            if not candidates:
                return None
            candidates.sort(
                key=lambda t: (
                    -self._tasks[t].priority,
                    self._tasks[t].available_at,
                    t,
                )
            )
            tid = candidates[0]
            old = self._tasks[tid]
            rec = TaskRecord(
                id=old.id,
                type=old.type,
                payload=old.payload,
                status=TaskStatus.RUNNING,
                priority=old.priority,
                available_at=old.available_at,
                attempts=old.attempts + 1,
                max_attempts=old.max_attempts,
                locked_by=worker,
                locked_at=now,
                lease_until=now + timedelta(seconds=lease_seconds),
                idempotency_key=old.idempotency_key,
                trace_id=old.trace_id,
                created_at=old.created_at,
            )
            self._tasks[tid] = rec
            return rec

    async def heartbeat(
        self, task_id: int, worker: str, *, lease_seconds: float = 60.0
    ) -> bool:
        async with self._lock:
            rec = self._tasks.get(task_id)
            if (
                rec is None
                or rec.locked_by != worker
                or rec.status != TaskStatus.RUNNING
            ):
                return False
            now = datetime.now(UTC)
            self._tasks[task_id] = TaskRecord(
                **{
                    **rec.__dict__,
                    "locked_at": now,
                    "lease_until": now + timedelta(seconds=lease_seconds),
                }
            )
            return True

    async def complete(self, task_id: int, worker: str) -> bool:
        async with self._lock:
            rec = self._tasks.get(task_id)
            if (
                rec is None
                or rec.locked_by != worker
                or rec.status != TaskStatus.RUNNING
            ):
                return False
            now = datetime.now(UTC)
            self._tasks[task_id] = TaskRecord(
                **{
                    **rec.__dict__,
                    "status": TaskStatus.COMPLETED,
                    "completed_at": now,
                    "locked_by": None,
                    "locked_at": None,
                    "lease_until": None,
                }
            )
            return True

    async def fail(
        self,
        task_id: int,
        worker: str,
        error: str,
        *,
        backoff_base: float = 1.0,
    ) -> TaskRecord | None:
        async with self._lock:
            rec = self._tasks.get(task_id)
            if (
                rec is None
                or rec.locked_by != worker
                or rec.status != TaskStatus.RUNNING
            ):
                return None
            now = datetime.now(UTC)
            if rec.attempts < rec.max_attempts:
                delay = backoff_base * (2 ** max(0, rec.attempts - 1))
                status = TaskStatus.RETRYING
                available = now + timedelta(seconds=delay)
                completed = None
            else:
                status = TaskStatus.FAILED
                available = now
                completed = now
            updated = TaskRecord(
                **{
                    **rec.__dict__,
                    "status": status,
                    "available_at": available,
                    "completed_at": completed,
                    "locked_by": None,
                    "locked_at": None,
                    "lease_until": None,
                    "last_error": error,
                }
            )
            self._tasks[task_id] = updated
            return updated

    async def release(self, task_id: int, worker: str) -> bool:
        async with self._lock:
            rec = self._tasks.get(task_id)
            if (
                rec is None
                or rec.locked_by != worker
                or rec.status != TaskStatus.RUNNING
            ):
                return False
            self._tasks[task_id] = TaskRecord(
                **{
                    **rec.__dict__,
                    "status": TaskStatus.PENDING,
                    "locked_by": None,
                    "locked_at": None,
                    "lease_until": None,
                }
            )
            return True

    async def release_expired(self) -> int:
        async with self._lock:
            now = datetime.now(UTC)
            count = 0
            for tid, rec in self._tasks.items():
                if (
                    rec.status == TaskStatus.RUNNING
                    and rec.lease_until
                    and rec.lease_until < now
                ):
                    if rec.attempts >= rec.max_attempts:
                        status = TaskStatus.FAILED
                        completed = now
                    else:
                        status = TaskStatus.PENDING
                        completed = None
                    self._tasks[tid] = TaskRecord(
                        **{
                            **rec.__dict__,
                            "status": status,
                            "completed_at": completed,
                            "locked_by": None,
                            "locked_at": None,
                            "lease_until": None,
                            "last_error": rec.last_error or "lease expired",
                        }
                    )
                    count += 1
            return count

    async def retry(self, task_id: int) -> TaskRecord | None:
        async with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None or rec.status != TaskStatus.FAILED:
                return None
            now = datetime.now(UTC)
            updated = TaskRecord(
                **{
                    **rec.__dict__,
                    "status": TaskStatus.PENDING,
                    "attempts": 0,
                    "available_at": now,
                    "completed_at": None,
                    "locked_by": None,
                    "locked_at": None,
                    "lease_until": None,
                }
            )
            self._tasks[task_id] = updated
            return updated

    async def list(
        self,
        *,
        status: TaskStatus | str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[TaskRecord]:
        results = []
        for tid in reversed(self._order):
            rec = self._tasks[tid]
            if status is not None and rec.status != TaskStatus(str(status)):
                continue
            if task_type is not None and rec.type != task_type:
                continue
            results.append(rec)
            if len(results) >= limit:
                break
        return results

    async def stats(self) -> QueueStats:
        counts: dict[str, int] = {}
        for rec in self._tasks.values():
            counts[rec.status.value] = counts.get(rec.status.value, 0) + 1
        return QueueStats(
            total=len(self._tasks),
            pending=counts.get(TaskStatus.PENDING.value, 0),
            running=counts.get(TaskStatus.RUNNING.value, 0),
            retrying=counts.get(TaskStatus.RETRYING.value, 0),
            completed=counts.get(TaskStatus.COMPLETED.value, 0),
            failed=counts.get(TaskStatus.FAILED.value, 0),
        )

    def capabilities(self) -> QueueCapabilities:
        return QueueCapabilities(
            provider=self.provider,
            durable=False,
            delivery="at_least_once",
            ordering="best_effort",
            visibility_timeout=True,
            delayed_delivery=False,
            priority=True,
            transactions=False,
        )
