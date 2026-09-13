"""Operational Protocol schemas added by Sprint 27.

These models extend the language-neutral Voodoo semantic boundary with the
World, Goal and governed distributed-execution concepts that landed after the
original protocol sprint. They are intentionally JSON-friendly and do not
import runtime implementation classes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .schemas import SCHEMA_VERSION

__all__ = [
    "Entity",
    "Relationship",
    "Observation",
    "WorldSnapshot",
    "GoalStatus",
    "Goal",
    "GoalIntentRun",
    "GoalRun",
    "RemoteOutcomeStatus",
    "RemoteExecutionRequest",
    "RemoteExecutionOutcome",
    "OPERATIONAL_PROTOCOL_ENTITIES",
]


def _now() -> datetime:
    return datetime.now(UTC)


class Entity(BaseModel):
    """Stable World identity plus current projected properties."""

    schema_version: int = SCHEMA_VERSION
    id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Relationship(BaseModel):
    """Typed directed edge between World entities."""

    schema_version: int = SCHEMA_VERSION
    id: str
    source_id: str
    predicate: str
    target_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class Observation(BaseModel):
    """Append-only evidence used to project World state."""

    schema_version: int = SCHEMA_VERSION
    id: str
    entity_id: str
    property: str
    value: Any
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    observed_at: datetime
    received_at: datetime
    trace_id: str | None = None
    execution_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorldSnapshot(BaseModel):
    """Reasoning/policy projection for one World entity."""

    schema_version: int = SCHEMA_VERSION
    entity: Entity
    relationships: list[Relationship] = Field(default_factory=list)
    latest_observations: dict[str, Observation] = Field(default_factory=dict)
    captured_at: datetime = Field(default_factory=_now)


class GoalStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Goal(BaseModel):
    """Durable desired outcome spanning one or more Intents/Executions."""

    schema_version: int = SCHEMA_VERSION
    id: str
    name: str
    objective: str = ""
    target_entity_id: str | None = None
    requires: list[str] = Field(default_factory=list)
    status: GoalStatus = GoalStatus.CREATED
    intent_ids: list[str] = Field(default_factory=list)
    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GoalIntentRun(BaseModel):
    schema_version: int = SCHEMA_VERSION
    intent_id: str
    intent_name: str
    status: str
    execution_id: str | None = None
    trace_id: str | None = None
    result: Any | None = None
    error: str | None = None
    decisions: list[str] = Field(default_factory=list)


class GoalRun(BaseModel):
    """Inspectable durable Goal orchestration checkpoint."""

    schema_version: int = SCHEMA_VERSION
    goal: Goal
    current_index: int = 0
    intent_runs: list[GoalIntentRun] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RemoteOutcomeStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"
    REJECTED = "rejected"


class RemoteExecutionRequest(BaseModel):
    """Transport-neutral request to enter governed remote execution."""

    schema_version: int = SCHEMA_VERSION
    request_id: str
    actor: str
    intent_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    target_entity_id: str | None = None
    trace_id: str | None = None
    parent_execution_id: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemoteExecutionOutcome(BaseModel):
    """Transport-neutral terminal or WAITING result of governed remote work."""

    schema_version: int = SCHEMA_VERSION
    request_id: str
    status: RemoteOutcomeStatus
    execution_id: str | None = None
    trace_id: str | None = None
    result: Any | None = None
    error: str | None = None
    approval_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


OPERATIONAL_PROTOCOL_ENTITIES: dict[str, type[BaseModel]] = {
    "Entity": Entity,
    "Relationship": Relationship,
    "Observation": Observation,
    "WorldSnapshot": WorldSnapshot,
    "Goal": Goal,
    "GoalIntentRun": GoalIntentRun,
    "GoalRun": GoalRun,
    "RemoteExecutionRequest": RemoteExecutionRequest,
    "RemoteExecutionOutcome": RemoteExecutionOutcome,
}
