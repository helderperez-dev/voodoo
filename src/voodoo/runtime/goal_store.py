"""Durable storage for GoalRuntime checkpoints.

Goal persistence is deliberately separate from Execution persistence: a Goal is
an objective spanning one or more canonical Executions. The store serializes
planning/checkpoint state only; it never executes work.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

__all__ = ["GoalStore", "SQLiteGoalStore"]


class GoalStore(Protocol):
    def save(self, goal_id: str, payload: dict[str, Any]) -> None: ...

    def load(self, goal_id: str) -> dict[str, Any] | None: ...

    def load_unfinished(self) -> list[dict[str, Any]]: ...


class SQLiteGoalStore:
    """Local-first durable Goal checkpoint store."""

    def __init__(self, path: str | Path = "data/goals.db") -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_runs (
                goal_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_goal_runs_status ON goal_runs(status)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save(self, goal_id: str, payload: dict[str, Any]) -> None:
        goal = payload["goal"]
        self._conn.execute(
            """
            INSERT INTO goal_runs(goal_id, status, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(goal_id) DO UPDATE SET
                status=excluded.status,
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (
                goal_id,
                goal["status"],
                json.dumps(payload, separators=(",", ":"), default=str),
                goal["updated_at"],
            ),
        )
        self._conn.commit()

    def load(self, goal_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload FROM goal_runs WHERE goal_id = ?", (goal_id,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def load_unfinished(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT payload FROM goal_runs
            WHERE status NOT IN ('completed', 'failed', 'cancelled')
            ORDER BY updated_at, goal_id
            """
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]
