"""Durable scheduler service.

Legacy scheduler stores return due records that the Runtime then enqueues. A
Store-native scheduler instead advances temporal state and creates durable Jobs
inside Store. ``ScheduleService`` supports both without allowing a native
occurrence to be enqueued twice.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("voodoo.scheduler")


class ScheduleService:
    """Background service that advances durable temporal work."""

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

    async def tick_once(self) -> int:
        """Advance one scheduler iteration and return occurrences fired."""
        if getattr(self.store, "creates_jobs_natively", False):
            fired = int(self.store.tick())
            if fired:
                logger.info("native scheduler fired %d durable job(s)", fired)
            return fired

        due = self.store.claim_due()
        for schedule in due:
            await self._fire(schedule)
        return len(due)

    async def _tick_loop(self) -> None:
        """Advance schedules using the active provider's ownership model."""
        while True:
            try:
                await self.tick_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("scheduler tick error: %r", exc)
            await asyncio.sleep(self.tick_interval)

    async def _fire(self, schedule: dict) -> None:
        """Enqueue one legacy-provider schedule occurrence."""
        import json

        from voodoo.runtime.scheduling.workers import enqueue

        payload = json.loads(schedule["payload"]) if schedule["payload"] else {}
        await enqueue(schedule["task_type"], payload)
        logger.info("schedule %s fired task %s", schedule["id"], schedule["task_type"])
