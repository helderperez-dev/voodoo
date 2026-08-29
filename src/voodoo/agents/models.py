"""Agent entity and run-record data models (Sprint 17).

``AgentEntity`` is the durable identity of an agent — name, model policy,
tools, capabilities, permissions, configuration, and current state.
``AgentRunRecord`` links a single agent run to its execution record.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

__all__ = ["AgentEntity", "AgentRunRecord"]


@dataclass
class AgentEntity:
    """Durable agent identity.

    Parameters
    ----------
    agent_id:
        Unique identifier. Auto-generated UUID if not provided.
    name:
        Human-readable display name.
    description:
        What this agent does.
    model:
        ``"provider:model"`` string (e.g. ``"openai:gpt-4o"``).
    system_prompt:
        Default system prompt for all runs.
    capabilities:
        Capability names granted to this agent.
    tools:
        Tool names available to this agent.
    permissions:
        Permission strings required for sensitive tools.
    config:
        Arbitrary configuration dict (temperature, max_tokens, etc.).
    state:
        Current lifecycle state (``"active"``, ``"paused"``, ``"archived"``).
    metadata:
        Arbitrary key-value metadata.
    created_at:
        ISO timestamp of creation.
    updated_at:
        ISO timestamp of last update.
    """

    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    model: str = ""
    system_prompt: str | None = None
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    state: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: _iso_now())
    updated_at: str = field(default_factory=lambda: _iso_now())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "permissions": self.permissions,
            "config": self.config,
            "state": self.state,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentEntity:
        """Deserialize from a plain dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentRunRecord:
    """Links an agent run to its execution.

    Parameters
    ----------
    run_id:
        Unique run identifier (matches ``AgentRun.run_id``).
    agent_id:
        The agent that performed the run.
    execution_id:
        The execution record ID (from the execution store).
    prompt:
        The input prompt.
    output:
        The final output.
    status:
        Run outcome (``"completed"``, ``"error"``, ``"failed"``).
    tokens_in:
        Input token count.
    tokens_out:
        Output token count.
    cost:
        Estimated cost in USD.
    tool_calls:
        Tool call history for this run.
    started_at:
        Unix timestamp when the run started.
    completed_at:
        Unix timestamp when the run completed.
    trace_id:
        Correlation ID from telemetry.
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    execution_id: str | None = None
    prompt: str = ""
    output: str = ""
    status: str = "completed"
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "execution_id": self.execution_id,
            "prompt": self.prompt[:500],
            "output": self.output[:500],
            "status": self.status,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost": self.cost,
            "tool_calls": self.tool_calls,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRunRecord:
        """Deserialize from a plain dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _iso_now() -> str:
    """Return an ISO-8601 timestamp (UTC, second precision)."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")
