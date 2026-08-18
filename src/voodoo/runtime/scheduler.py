"""Durable scheduler service (Sprint 5).

The scheduler tick loop claims due schedules from the SQLite store and
enqueues durable tasks via the existing queue system. Schedules survive
restarts because they live in the database, not in process memory.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("voodoo.scheduler")


class ScheduleService:
    """Background service that polls the schedule store and fires tasks."""

    def __init__(self, store, tick_interval: float = 1.0):
        self.store = store
        self.tick_interval = tick_interval
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the scheduler tick loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        """Stop the scheduler tick loop."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _tick_loop(self) -> None:
        """Poll for due schedules and enqueue tasks."""
        while True:
            try:
                due = self.store.claim_due()
                for schedule in due:
                    await self._fire(schedule)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("scheduler tick error: %r", exc)
            await asyncio.sleep(self.tick_interval)

    async def _fire(self, schedule: dict) -> None:
        """Enqueue the scheduled task."""
        import json

        from voodoo.workers.queue import enqueue

        payload = json.loads(schedule["payload"]) if schedule["payload"] else {}
        await enqueue(schedule["task_type"], payload)
        logger.info("schedule %s fired task %s", schedule["id"], schedule["task_type"])
