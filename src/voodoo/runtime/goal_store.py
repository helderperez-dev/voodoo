"""Durable storage for GoalRuntime checkpoints.

Goal persistence is deliberately separate from Execution persistence: a Goal is
an objective spanning one or more canonical Executions. Stores serialize
planning/checkpoint state only; they never execute work.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

__all__ = ["GoalStore", "SQLiteGoalStore", "VoodooStoreGoalStore"]

_GOAL_PREFIX = b"runtime:goals:checkpoint:"
_TERMINAL = {"completed", "failed", "cancelled"}


class GoalStore(Protocol):
    def save(self, goal_id: str, payload: dict[str, Any]) -> None: ...

    def load(self, goal_id: str) -> dict[str, Any] | None: ...

    def load_unfinished(self) -> list[dict[str, Any]]: ...


class VoodooStoreGoalStore:
    """Goal checkpoints backed by the Runtime-owned Voodoo Store.

    The adapter resolves the process-shared RuntimeStore lazily so GoalRuntime
    can be used before an ASGI ``App`` lifespan without opening a competing
    writer. When an App is active, the same application Store is reused.
    """

    provider = "voodoo"

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self._runtime_store = runtime_store

    @staticmethod
    def _key(goal_id: str) -> bytes:
        return _GOAL_PREFIX + goal_id.encode("utf-8")

    def _runtime(self) -> RuntimeStore:
        if self._runtime_store is not None:
            return self._runtime_store
        from voodoo.runtime.store import acquire_runtime_store

        return acquire_runtime_store()

    def _store(self) -> Any:
        runtime = self._runtime()
        provider = runtime.provider or runtime.start()
        if provider is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "Voodoo Store is disabled; durable Goal checkpoints require an "
                "explicit GoalStore adapter or an enabled Runtime Store."
            )
        native = getattr(provider, "native", None)
        if native is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "The active Voodoo Store provider does not expose durable KV storage."
            )
        return native

    def save(self, goal_id: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        self._store().put(self._key(goal_id), encoded)

    def load(self, goal_id: str) -> dict[str, Any] | None:
        raw = self._store().get(self._key(goal_id))
        if raw is None:
            return None
        return json.loads(bytes(raw).decode("utf-8"))

    def load_unfinished(self) -> list[dict[str, Any]]:
        checkpoints: list[dict[str, Any]] = []
        for _key, raw in self._store().scan_prefix(_GOAL_PREFIX):
            payload = json.loads(bytes(raw).decode("utf-8"))
            goal = payload.get("goal", {})
            if str(goal.get("status", "")) not in _TERMINAL:
                checkpoints.append(payload)
        checkpoints.sort(
            key=lambda payload: (
                str(payload.get("goal", {}).get("updated_at", "")),
                str(payload.get("goal", {}).get("id", "")),
            )
        )
        return checkpoints

    def close(self) -> None:
        """No-op: RuntimeStore owns the native Store lifecycle."""


class SQLiteGoalStore:
    """Explicit SQLite compatibility adapter for Goal checkpoints."""

    provider = "sqlite"

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
