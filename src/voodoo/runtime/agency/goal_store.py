"""Durable storage for GoalRuntime checkpoints.

Goal persistence is deliberately separate from Execution persistence: a Goal is
an objective spanning one or more canonical Executions. Stores serialize
planning/checkpoint state only; they never execute work.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

__all__ = ["GoalStore", "SQLiteGoalStore", "VoodooStoreGoalStore"]

_GOAL_PREFIX = b"runtime:goals:checkpoint:"
_COLLECTION = b"runtime.goals"
_TERMINAL = {"completed", "failed", "cancelled"}
_SCHEMA_KEY = "_schema_version"
_SCHEMA_VERSION = 1


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

    @staticmethod
    def _native_collections(store: Any) -> bool:
        return all(
            hasattr(store, method)
            for method in ("create_collection", "upsert_record", "get_record", "scan_collection")
        )

    @classmethod
    def _ensure_collection(cls, store: Any) -> None:
        if cls._native_collections(store):
            store.create_collection(_COLLECTION, schema_version=_SCHEMA_VERSION, codec=b"json")

    def save(self, goal_id: str, payload: dict[str, Any]) -> None:
        body = dict(payload)
        body[_SCHEMA_KEY] = _SCHEMA_VERSION
        encoded = json.dumps(
            body,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        store = self._store()
        if self._native_collections(store):
            self._ensure_collection(store)
            store.upsert_record(_COLLECTION, goal_id.encode("utf-8"), encoded)
            # A checkpoint write is the migration point for legacy KV data.
            store.delete(self._key(goal_id))
            return
        store.put(self._key(goal_id), encoded)

    def load(self, goal_id: str) -> dict[str, Any] | None:
        store = self._store()
        raw = None
        if self._native_collections(store):
            self._ensure_collection(store)
            record = store.get_record(_COLLECTION, goal_id.encode("utf-8"))
            if record is not None:
                raw = record[1]
        if raw is None:
            raw = store.get(self._key(goal_id))
        if raw is None:
            return None
        return self._decode(goal_id, bytes(raw))

    def load_unfinished(self) -> list[dict[str, Any]]:
        checkpoints: list[dict[str, Any]] = []
        store = self._store()
        records: dict[str, dict[str, Any]] = {}
        if self._native_collections(store):
            self._ensure_collection(store)
            for key, raw, _indexes in store.scan_collection(_COLLECTION):
                goal_id = bytes(key).decode("utf-8")
                records[goal_id] = self._decode(goal_id, bytes(raw))
        for key, raw in store.scan_prefix(_GOAL_PREFIX):
            goal_id = key[len(_GOAL_PREFIX) :].decode("utf-8")
            records.setdefault(goal_id, self._decode(goal_id, bytes(raw)))
        for payload in records.values():
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

    @staticmethod
    def _decode(goal_id: str, raw: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("goal checkpoint is not valid UTF-8 JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("goal checkpoint must be a JSON object")
        version = payload.pop(_SCHEMA_KEY, 0)
        if not isinstance(version, int) or isinstance(version, bool):
            raise ValueError("goal checkpoint schema version must be an integer")
        if version > _SCHEMA_VERSION:
            raise ValueError(
                f"goal checkpoint schema {version} is newer than supported schema "
                f"{_SCHEMA_VERSION}"
            )
        goal = payload.get("goal")
        if isinstance(goal, dict) and goal.get("id") not in (None, goal_id):
            raise ValueError("goal checkpoint does not match its key")
        return cast(dict[str, Any], payload)


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
        return cast(dict[str, Any], json.loads(row["payload"]))

    def load_unfinished(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT payload FROM goal_runs
            WHERE status NOT IN ('completed', 'failed', 'cancelled')
            ORDER BY updated_at, goal_id
            """
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]
