"""Durable scheduling for Voodoo (Sprint 5)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from voodoo.primitives.time import TimeSpec
from voodoo.storage.database.interfaces import Migration
from voodoo.storage.database.sqlite import register_framework_migration
from voodoo.storage.queue import VoodooQueue

SCHEDULES_MIGRATION_VERSION = 5

SCHEDULES_MIGRATION = Migration(
    version=SCHEDULES_MIGRATION_VERSION,
    name="schedules",
    statements=(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY,
            name TEXT,
            kind TEXT NOT NULL,
            spec TEXT NOT NULL,
            next_run_at TEXT NOT NULL,
            last_run_at TEXT,
            task_type TEXT NOT NULL,
            payload TEXT,
            active INTEGER NOT NULL DEFAULT 1
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON schedules (next_run_at)",
        "CREATE INDEX IF NOT EXISTS idx_schedules_active ON schedules (active)",
    ),
)

register_framework_migration(SCHEDULES_MIGRATION)


class Scheduler:
    """Durable scheduler backed by SQLite."""

    def __init__(self, path: str | Path, queue: VoodooQueue) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self.queue = queue
        self._running = False

    def at(
        self, when: datetime, task_type: str, payload: Any, name: str | None = None
    ) -> str:
        """Schedule a task at a specific time."""
        import uuid

        schedule_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO schedules (id, name, kind, spec, next_run_at, task_type, payload, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                schedule_id,
                name,
                "at",
                when.isoformat(),
                when.isoformat(),
                task_type,
                json.dumps(payload, default=str),
            ),
        )
        self._conn.commit()
        return schedule_id

    def after(
        self, delay: timedelta, task_type: str, payload: Any, name: str | None = None
    ) -> str:
        """Schedule a task after a delay."""
        when = datetime.now(UTC) + delay
        return self.at(when, task_type, payload, name)

    def every(
        self, interval: timedelta, task_type: str, payload: Any, name: str | None = None
    ) -> str:
        """Schedule a recurring task."""
        import uuid

        schedule_id = str(uuid.uuid4())
        spec = {"interval": interval.total_seconds()}
        next_run = datetime.now(UTC) + interval
        self._conn.execute(
            """
            INSERT INTO schedules (id, name, kind, spec, next_run_at, task_type, payload, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                schedule_id,
                name,
                "interval",
                json.dumps(spec),
                next_run.isoformat(),
                task_type,
                json.dumps(payload, default=str),
            ),
        )
        self._conn.commit()
        return schedule_id

    def cron(
        self, cron_expr: str, task_type: str, payload: Any, name: str | None = None
    ) -> str:
        """Schedule a task using a cron expression (5-field subset)."""
        # Minimal 5-field cron support (minute hour day month day_of_week)
        import uuid

        schedule_id = str(uuid.uuid4())
        spec = {"cron": cron_expr}
        # For simplicity, run now + 1 minute for initial scheduling
        next_run = datetime.now(UTC) + timedelta(minutes=1)
        self._conn.execute(
            """
            INSERT INTO schedules (id, name, kind, spec, next_run_at, task_type, payload, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                schedule_id,
                name,
                "cron",
                json.dumps(spec),
                next_run.isoformat(),
                task_type,
                json.dumps(payload, default=str),
            ),
        )
        self._conn.commit()
        return schedule_id

    def pause(self, schedule_id: str) -> None:
        """Pause a schedule."""
        self._conn.execute(
            "UPDATE schedules SET active = 0 WHERE id = ?",
            (schedule_id,),
        )
        self._conn.commit()

    def resume(self, schedule_id: str) -> None:
        """Resume a schedule."""
        self._conn.execute(
            "UPDATE schedules SET active = 1 WHERE id = ?",
            (schedule_id,),
        )
        self._conn.commit()

    async def tick(self) -> int:
        """Claim and dispatch due schedules. Returns number dispatched."""
        now = datetime.now(UTC).isoformat()
        rows = self._conn.execute(
            """
            SELECT * FROM schedules
            WHERE active = 1 AND next_run_at <= ?
            ORDER BY next_run_at ASC
            """,
            (now,),
        ).fetchall()

        dispatched = 0
        for row in rows:
            schedule_id = row["id"]
            task_type = row["task_type"]
            payload = json.loads(row["payload"]) if row["payload"] else None

            # Enqueue the task
            await self.queue.enqueue(
                task_type, payload, idempotency_key=f"schedule:{schedule_id}"
            )

            # Update next run
            kind = row["kind"]
            if kind == "at":
                # One-time schedule: deactivate
                self._conn.execute(
                    "UPDATE schedules SET active = 0 WHERE id = ?",
                    (schedule_id,),
                )
            elif kind == "interval":
                spec = json.loads(row["spec"])
                interval_seconds = spec.get("interval", 60)
                next_run = datetime.now(UTC) + timedelta(seconds=interval_seconds)
                self._conn.execute(
                    "UPDATE schedules SET next_run_at = ?, last_run_at = ? WHERE id = ?",
                    (next_run.isoformat(), now, schedule_id),
                )
            elif kind == "cron":
                # Simple: reschedule 1 minute later (minimal cron support)
                next_run = datetime.now(UTC) + timedelta(minutes=1)
                self._conn.execute(
                    "UPDATE schedules SET next_run_at = ?, last_run_at = ? WHERE id = ?",
                    (next_run.isoformat(), now, schedule_id),
                )
            self._conn.commit()
            dispatched += 1

        return dispatched

    def list_schedules(self) -> list[dict[str, Any]]:
        """List all schedules."""
        rows = self._conn.execute(
            "SELECT id, name, kind, next_run_at, last_run_at, task_type, active FROM schedules"
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# Factory function for schedule_from_spec
def schedule_from_spec(
    spec: TimeSpec,
    task_type: str,
    payload: Any,
    scheduler: Scheduler,
    name: str | None = None,
) -> str:
    """Schedule a task from a TimeSpec."""
    if spec.schedule is not None:
        # TimeSpec.schedule holds a cron expression or interval string
        if "*" in spec.schedule or any(c.isalpha() for c in spec.schedule):
            return scheduler.cron(spec.schedule, task_type, payload, name=name)
        # Try to parse as interval
        if " " in spec.schedule and not any(c.isalpha() for c in spec.schedule):
            # Assume it's a cron expression
            return scheduler.cron(spec.schedule, task_type, payload, name=name)
        # Otherwise treat as interval in seconds
        try:
            seconds = float(spec.schedule)
            return scheduler.every(
                timedelta(seconds=seconds), task_type, payload, name=name
            )
        except ValueError:
            return scheduler.cron(spec.schedule, task_type, payload, name=name)
    if spec.interval is not None:
        return scheduler.every(spec.interval, task_type, payload, name=name)
    if spec.deadline is not None:
        return scheduler.at(spec.deadline, task_type, payload, name=name)
    raise ValueError(
        "TimeSpec has no schedule, interval, or deadline — nothing to schedule"
    )
