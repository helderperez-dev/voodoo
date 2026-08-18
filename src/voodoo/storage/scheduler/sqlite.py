"""SQLite-backed durable schedule store (Sprint 5).

Schedules are rows in the ``schedules`` table; claiming due schedules is
atomic via a transactional ``UPDATE ... WHERE next_run_at <= now`` pattern
so concurrent scheduler instances never double-fire.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voodoo.storage.database.interfaces import Migration
from voodoo.storage.database.sqlite import register_framework_migration

__all__ = ["SQLiteScheduleStore", "SCHEDULES_MIGRATION"]

SCHEDULES_MIGRATION_VERSION = 4

SCHEDULES_MIGRATION = Migration(
    version=SCHEDULES_MIGRATION_VERSION,
    name="schedules",
    statements=(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            spec TEXT NOT NULL,
            next_run_at TEXT NOT NULL,
            last_run_at TEXT,
            task_type TEXT NOT NULL,
            payload TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules (active, next_run_at)",
    ),
)

register_framework_migration(SCHEDULES_MIGRATION)


class SQLiteScheduleStore:
    """Durable schedule store backed by SQLite."""

    provider = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                spec TEXT NOT NULL,
                next_run_at TEXT NOT NULL,
                last_run_at TEXT,
                task_type TEXT NOT NULL,
                payload TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules (active, next_run_at)"
        )
        self._conn.commit()

    def create(
        self,
        schedule_id: str,
        name: str,
        kind: str,
        spec: str,
        next_run_at: datetime,
        task_type: str,
        payload: Any = None,
    ) -> None:
        """Insert a new schedule."""
        self._conn.execute(
            """
            INSERT INTO schedules (id, name, kind, spec, next_run_at, task_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                name,
                kind,
                spec,
                next_run_at.isoformat(),
                task_type,
                json.dumps(payload) if payload is not None else None,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def claim_due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """Atomically claim all due active schedules.

        Returns the claimed schedules with their next_run_at advanced
        (for interval/cron) or marked inactive (for one-shot at/after).
        """
        now = now or datetime.now(UTC)
        now_iso = now.isoformat()

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            due = self._conn.execute(
                """
                SELECT * FROM schedules
                WHERE active = 1 AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (now_iso,),
            ).fetchall()

            claimed: list[dict[str, Any]] = []
            for row in due:
                schedule = dict(row)
                if schedule["kind"] in ("at", "after"):
                    # One-shot: mark inactive after claim
                    self._conn.execute(
                        "UPDATE schedules SET active = 0, last_run_at = ? WHERE id = ?",
                        (now_iso, schedule["id"]),
                    )
                elif schedule["kind"] == "interval":
                    # Periodic: advance next_run_at
                    interval = float(schedule["spec"])
                    next_run = now + __import__("datetime").timedelta(seconds=interval)
                    self._conn.execute(
                        "UPDATE schedules SET next_run_at = ?, last_run_at = ? WHERE id = ?",
                        (next_run.isoformat(), now_iso, schedule["id"]),
                    )
                elif schedule["kind"] == "cron":
                    # Cron: compute next run
                    next_run = _cron_next(schedule["spec"], now)
                    if next_run is not None:
                        self._conn.execute(
                            "UPDATE schedules SET next_run_at = ?, last_run_at = ? WHERE id = ?",
                            (next_run.isoformat(), now_iso, schedule["id"]),
                        )
                    else:
                        self._conn.execute(
                            "UPDATE schedules SET active = 0, last_run_at = ? WHERE id = ?",
                            (now_iso, schedule["id"]),
                        )
                claimed.append(schedule)
            self._conn.execute("COMMIT")
            return claimed
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def list_all(self) -> list[dict[str, Any]]:
        """Return all schedules (active and inactive)."""
        rows = self._conn.execute(
            "SELECT * FROM schedules ORDER BY created_at"
        ).fetchall()
        return [dict(row) for row in rows]

    def get(self, schedule_id: str) -> dict[str, Any] | None:
        """Return one schedule or None."""
        row = self._conn.execute(
            "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        return dict(row) if row else None

    def pause(self, schedule_id: str) -> bool:
        """Pause a schedule (set active=0). Returns True if found."""
        cursor = self._conn.execute(
            "UPDATE schedules SET active = 0 WHERE id = ? AND active = 1",
            (schedule_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def resume(self, schedule_id: str, next_run_at: datetime | None = None) -> bool:
        """Resume a schedule (set active=1). Returns True if found."""
        if next_run_at is not None:
            cursor = self._conn.execute(
                "UPDATE schedules SET active = 1, next_run_at = ? WHERE id = ? AND active = 0",
                (next_run_at.isoformat(), schedule_id),
            )
        else:
            cursor = self._conn.execute(
                "UPDATE schedules SET active = 1 WHERE id = ? AND active = 0",
                (schedule_id,),
            )
        self._conn.commit()
        return cursor.rowcount > 0

    def schedule_from_timespec(
        self,
        schedule_id: str,
        time_spec: Any,
        task_type: str,
        payload: Any = None,
    ) -> bool:
        """Create a schedule from a TimeSpec (Sprint 5).

        Returns True if the TimeSpec had a schedule/interval and was stored.
        Returns False if the TimeSpec had no schedule/interval.
        """
        record = time_spec.to_schedule_record(schedule_id, task_type)
        if record is None:
            return False

        self.create(
            schedule_id=schedule_id,
            name=record["name"],
            kind=record["kind"],
            spec=record["spec"],
            next_run_at=record["next_run_at"],
            task_type=task_type,
            payload=payload,
        )
        return True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _cron_next(spec: str, now: datetime) -> datetime | None:
    """Minimal 5-field cron: minute hour day month weekday.

    Returns the next run time after ``now``. Returns None if the spec
    cannot be parsed (schedule is disabled).
    """
    import datetime as dt

    parts = spec.split()
    if len(parts) != 5:
        return None
    minute, hour, day, month, weekday = parts

    # Very minimal: only support '*' and exact numbers.
    def _matches(value: str, actual: int) -> bool:
        if value == "*":
            return True
        try:
            return int(value) == actual
        except ValueError:
            return False

    # Try each minute in the next 24 hours
    for offset in range(1, 24 * 60 + 1):
        candidate = now + dt.timedelta(minutes=offset)
        if (
            _matches(minute, candidate.minute)
            and _matches(hour, candidate.hour)
            and _matches(day, candidate.day)
            and _matches(month, candidate.month)
            and _matches(weekday, candidate.weekday())
        ):
            return candidate
    return None
