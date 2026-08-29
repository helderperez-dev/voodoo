"""Agent registry — Protocol, in-memory, and SQLite implementations (Sprint 17).

The registry persists agent identity and links every run to its execution
history. The default backend is SQLite (WAL mode, busy_timeout=5000).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from voodoo.agents.models import AgentEntity, AgentRunRecord

__all__ = [
    "AgentRegistry",
    "InMemoryAgentRegistry",
    "SQLiteAgentRegistry",
]


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class AgentRegistry(Protocol):
    """Persistence contract for agent registries."""

    async def register(self, entity: AgentEntity) -> None:
        """Register or update an agent entity."""
        ...

    async def get(self, agent_id: str) -> AgentEntity | None:
        """Fetch an agent by ID. Returns ``None`` if not found."""
        ...

    async def list_agents(
        self,
        state: str | None = None,
        limit: int = 100,
    ) -> list[AgentEntity]:
        """List registered agents, optionally filtered by state."""
        ...

    async def update(self, entity: AgentEntity) -> None:
        """Update an existing agent entity."""
        ...

    async def delete(self, agent_id: str) -> bool:
        """Delete an agent. Returns ``True`` if deleted."""
        ...

    async def record_run(self, record: AgentRunRecord) -> None:
        """Persist a run record linked to this agent."""
        ...

    async def get_runs(
        self,
        agent_id: str,
        limit: int = 50,
    ) -> list[AgentRunRecord]:
        """List run history for an agent, newest first."""
        ...

    async def count_agents(self, state: str | None = None) -> int:
        """Count registered agents."""
        ...

    async def count_runs(self, agent_id: str) -> int:
        """Count runs for an agent."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------


class InMemoryAgentRegistry:
    """Non-durable registry for tests."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentEntity] = {}
        self._runs: dict[str, list[AgentRunRecord]] = {}

    async def register(self, entity: AgentEntity) -> None:
        self._agents[entity.agent_id] = entity

    async def get(self, agent_id: str) -> AgentEntity | None:
        return self._agents.get(agent_id)

    async def list_agents(
        self,
        state: str | None = None,
        limit: int = 100,
    ) -> list[AgentEntity]:
        agents = list(self._agents.values())
        if state:
            agents = [a for a in agents if a.state == state]
        return agents[:limit]

    async def update(self, entity: AgentEntity) -> None:
        if entity.agent_id not in self._agents:
            raise KeyError(f"Agent '{entity.agent_id}' not found")
        self._agents[entity.agent_id] = entity

    async def delete(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            self._runs.pop(agent_id, None)
            return True
        return False

    async def record_run(self, record: AgentRunRecord) -> None:
        self._runs.setdefault(record.agent_id, []).append(record)

    async def get_runs(
        self,
        agent_id: str,
        limit: int = 50,
    ) -> list[AgentRunRecord]:
        runs = self._runs.get(agent_id, [])
        return list(reversed(runs[-limit:]))

    async def count_agents(self, state: str | None = None) -> int:
        if state:
            return sum(1 for a in self._agents.values() if a.state == state)
        return len(self._agents)

    async def count_runs(self, agent_id: str) -> int:
        return len(self._runs.get(agent_id, []))


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id   TEXT PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    model      TEXT NOT NULL DEFAULT '',
    system_prompt TEXT,
    capabilities TEXT NOT NULL DEFAULT '[]',
    tools      TEXT NOT NULL DEFAULT '[]',
    permissions TEXT NOT NULL DEFAULT '[]',
    config     TEXT NOT NULL DEFAULT '{}',
    state      TEXT NOT NULL DEFAULT 'active',
    metadata   TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id       TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    execution_id TEXT,
    prompt       TEXT NOT NULL DEFAULT '',
    output       TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'completed',
    tokens_in    INTEGER NOT NULL DEFAULT 0,
    tokens_out   INTEGER NOT NULL DEFAULT 0,
    cost         REAL NOT NULL DEFAULT 0.0,
    tool_calls   TEXT NOT NULL DEFAULT '[]',
    started_at   REAL NOT NULL,
    completed_at REAL,
    trace_id     TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_id ON agent_runs(agent_id);
"""


class SQLiteAgentRegistry:
    """Durable SQLite-backed agent registry.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file. Created on first use.
    """

    def __init__(self, db_path: str = "data/agents.db") -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # -- agents ------------------------------------------------------------

    async def register(self, entity: AgentEntity) -> None:
        """Insert or replace an agent entity."""
        d = entity.to_dict()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO agents
                (agent_id, name, description, model, system_prompt,
                 capabilities, tools, permissions, config, state,
                 metadata, created_at, updated_at)
            VALUES
                (:agent_id, :name, :description, :model, :system_prompt,
                 :capabilities, :tools, :permissions, :config, :state,
                 :metadata, :created_at, :updated_at)
            """,
            {
                **d,
                "capabilities": json.dumps(d["capabilities"]),
                "tools": json.dumps(d["tools"]),
                "permissions": json.dumps(d["permissions"]),
                "config": json.dumps(d["config"]),
                "metadata": json.dumps(d["metadata"]),
            },
        )
        self._conn.commit()

    async def get(self, agent_id: str) -> AgentEntity | None:
        cur = self._conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return _row_to_entity(row, cur.description)

    async def list_agents(
        self,
        state: str | None = None,
        limit: int = 100,
    ) -> list[AgentEntity]:
        if state:
            cur = self._conn.execute(
                "SELECT * FROM agents WHERE state = ? ORDER BY created_at DESC LIMIT ?",
                (state, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM agents ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [_row_to_entity(r, cur.description) for r in cur.fetchall()]

    async def update(self, entity: AgentEntity) -> None:
        entity.updated_at = _iso_now()
        d = entity.to_dict()
        cur = self._conn.execute(
            "UPDATE agents SET name=:name, description=:description, "
            "model=:model, system_prompt=:system_prompt, "
            "capabilities=:capabilities, tools=:tools, permissions=:permissions, "
            "config=:config, state=:state, metadata=:metadata, "
            "updated_at=:updated_at WHERE agent_id=:agent_id",
            {
                **d,
                "capabilities": json.dumps(d["capabilities"]),
                "tools": json.dumps(d["tools"]),
                "permissions": json.dumps(d["permissions"]),
                "config": json.dumps(d["config"]),
                "metadata": json.dumps(d["metadata"]),
            },
        )
        if cur.rowcount == 0:
            raise KeyError(f"Agent '{entity.agent_id}' not found")
        self._conn.commit()

    async def delete(self, agent_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # -- runs --------------------------------------------------------------

    async def record_run(self, record: AgentRunRecord) -> None:
        d = record.to_dict()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO agent_runs
                (run_id, agent_id, execution_id, prompt, output, status,
                 tokens_in, tokens_out, cost, tool_calls,
                 started_at, completed_at, trace_id)
            VALUES
                (:run_id, :agent_id, :execution_id, :prompt, :output, :status,
                 :tokens_in, :tokens_out, :cost, :tool_calls,
                 :started_at, :completed_at, :trace_id)
            """,
            {**d, "tool_calls": json.dumps(d["tool_calls"])},
        )
        self._conn.commit()

    async def get_runs(
        self,
        agent_id: str,
        limit: int = 50,
    ) -> list[AgentRunRecord]:
        cur = self._conn.execute(
            "SELECT * FROM agent_runs WHERE agent_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (agent_id, limit),
        )
        return [_row_to_run(r, cur.description) for r in cur.fetchall()]

    async def count_agents(self, state: str | None = None) -> int:
        if state:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM agents WHERE state = ?", (state,)
            )
        else:
            cur = self._conn.execute("SELECT COUNT(*) FROM agents")
        return cur.fetchone()[0]

    async def count_runs(self, agent_id: str) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM agent_runs WHERE agent_id = ?", (agent_id,)
        )
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AGENT_COLUMNS = [
    "agent_id",
    "name",
    "description",
    "model",
    "system_prompt",
    "capabilities",
    "tools",
    "permissions",
    "config",
    "state",
    "metadata",
    "created_at",
    "updated_at",
]

_RUN_COLUMNS = [
    "run_id",
    "agent_id",
    "execution_id",
    "prompt",
    "output",
    "status",
    "tokens_in",
    "tokens_out",
    "cost",
    "tool_calls",
    "started_at",
    "completed_at",
    "trace_id",
]


def _row_to_entity(row: Any, description: Any) -> AgentEntity:
    """Convert a sqlite3 row to an AgentEntity."""
    cols = [d[0] for d in description]
    data = dict(zip(cols, row, strict=False))
    for key in ("capabilities", "tools", "permissions", "config", "metadata"):
        if isinstance(data.get(key), str):
            data[key] = json.loads(data[key])
    return AgentEntity.from_dict(data)


def _row_to_run(row: Any, description: Any) -> AgentRunRecord:
    """Convert a sqlite3 row to an AgentRunRecord."""
    cols = [d[0] for d in description]
    data = dict(zip(cols, row, strict=False))
    if isinstance(data.get("tool_calls"), str):
        data["tool_calls"] = json.loads(data["tool_calls"])
    return AgentRunRecord.from_dict(data)


def _iso_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")
