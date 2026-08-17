"""Execution — the first-class execution representation.

Every meaningful operation (HTTP request, Agent run, Task, Workflow task,
Tool invocation, MCP call, Worker job, Human approval, Event handler) is
eventually represented as an :class:`Execution`.

An Execution carries the lifecycle:

    created → planned → authorized → running → waiting
                                    ↕            ↓
                                    ↑        completed
                                  (resume)     failed
                                               cancelled
                                               timed_out

It integrates with the existing telemetry store (``record_agent_run`` /
``record_tool_call`` / ``record_trace``) rather than duplicating tracing.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from voodoo.primitives.compute import ComputeSpec
from voodoo.primitives.effect import Effect
from voodoo.primitives.intent import Intent
from voodoo.primitives.resource import Resource
from voodoo.primitives.state import State

__all__ = ["ExecutionStatus", "Execution"]


class ExecutionStatus(StrEnum):
    CREATED = "created"
    PLANNED = "planned"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def terminal(self) -> bool:
        return self in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
        )

    @property
    def active(self) -> bool:
        return self in (
            ExecutionStatus.CREATED,
            ExecutionStatus.PLANNED,
            ExecutionStatus.AUTHORIZED,
            ExecutionStatus.RUNNING,
            ExecutionStatus.WAITING,
        )


class Execution(BaseModel):
    """A single runtime execution.

    This is the canonical record produced and consumed by the
    :class:`~voodoo.runtime.engine.ExecutionEngine`. It is serializable
    (Pydantic) so it can be checkpointed, inspected, and emitted as telemetry.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    parent_execution_id: str | None = None
    status: ExecutionStatus = ExecutionStatus.CREATED

    intent: Intent | None = None
    actor: str = "system"
    compute: ComputeSpec | None = None
    capabilities: list[str] = Field(default_factory=list)
    resources: Resource = Field(default_factory=Resource)

    effects: list[Effect] = Field(default_factory=list)
    state_changes: list[State] = Field(default_factory=list)

    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # internal wall-clock timing (seconds since epoch) for accounting
    _started_ts: float | None = None
    _completed_ts: float | None = None

    model_config = {"arbitrary_types_allowed": True}

    # -- lifecycle ---------------------------------------------------------

    def mark_planned(self) -> None:
        self._transition(ExecutionStatus.PLANNED)

    def mark_authorized(self) -> None:
        self._transition(ExecutionStatus.AUTHORIZED)

    def start(self) -> None:
        self.started_at = datetime.now(UTC)
        self._started_ts = time.time()
        self._transition(ExecutionStatus.RUNNING)

    def wait(self) -> None:
        self._transition(ExecutionStatus.WAITING)

    def resume(self) -> None:
        self._transition(ExecutionStatus.RUNNING)

    def complete(self, result: Any | None = None) -> None:
        if result is not None:
            self.result = result
        self.completed_at = datetime.now(UTC)
        self._completed_ts = time.time()
        self._transition(ExecutionStatus.COMPLETED)

    def fail(self, error: str) -> None:
        self.error = error
        self.completed_at = datetime.now(UTC)
        self._completed_ts = time.time()
        self._transition(ExecutionStatus.FAILED)

    def cancel(self) -> None:
        self.completed_at = datetime.now(UTC)
        self._completed_ts = time.time()
        self._transition(ExecutionStatus.CANCELLED)

    def time_out(self) -> None:
        self.completed_at = datetime.now(UTC)
        self._completed_ts = time.time()
        self._transition(ExecutionStatus.TIMED_OUT)

    def _transition(self, new_status: ExecutionStatus) -> None:
        self.status = new_status

    # -- recording ---------------------------------------------------------

    def add_effect(self, effect: Effect) -> None:
        self.effects.append(effect)
        if self.intent is not None:
            self.intent.add_effect(effect.id)

    def record_state_change(self, state: State) -> None:
        self.state_changes.append(state)

    def add_resources(self, resource: Resource) -> None:
        self.resources = self.resources.add(resource)

    # -- queries -----------------------------------------------------------

    @property
    def duration_seconds(self) -> float | None:
        if self._started_ts is None or self._completed_ts is None:
            return None
        return self._completed_ts - self._started_ts

    @property
    def cost(self) -> float:
        return self.resources.cost

    @property
    def succeeded(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    @property
    def failed(self) -> bool:
        return self.status in (ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT)

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "parent_execution_id": self.parent_execution_id,
            "status": self.status.value,
            "intent": self.intent.name if self.intent else None,
            "actor": self.actor,
            "compute": self.compute.describe() if self.compute else None,
            "capabilities": self.capabilities,
            "resources": self.resources.describe(),
            "effects": [e.name for e in self.effects],
            "state_changes": len(self.state_changes),
            "duration_seconds": self.duration_seconds,
            "cost": self.cost,
            "succeeded": self.succeeded,
            "error": self.error,
        }
