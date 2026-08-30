"""Canonical entity schemas for the Voodoo protocol.

These Pydantic models form the **stable semantic boundary** for
cross-language interop (TypeScript, Go, Rust SDKs). Every entity
carries a ``schema_version`` field so consumers can evolve independently.

The schemas are intentionally flat and JSON-friendly — no Python-specific
types, no circular references, no lazy imports. Every field uses a
primitive or a nested protocol model.

Compatibility policy (see ``docs/protocol.md``):
  - Additive within a major version (new optional fields are safe).
  - Breaking changes require a major version bump.
  - ``schema_version`` is an integer; consumers should reject unknown
    major versions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    # Enums
    "ExecutionStatus",
    "IntentStatus",
    "EffectStatus",
    "TaskStatus",
    "ApprovalStatus",
    "ComputeKind",
    # Core entities
    "Identity",
    "Capability",
    "Constraint",
    "Resource",
    "TimeSpec",
    "ComputeSpec",
    "Intent",
    "Effect",
    "Execution",
    "Task",
    "Event",
    "ObjectRef",
    "Error",
    "TelemetrySpan",
    "Approval",
    "AgentEntity",
    "AgentRun",
    "MemoryEntry",
    # Schema metadata
    "SCHEMA_VERSION",
    "PROTOCOL_ENTITIES",
]

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION: int = 1
"""Current protocol schema version. Bump on breaking changes."""


# ---------------------------------------------------------------------------
# Enums — shared vocabulary
# ---------------------------------------------------------------------------


class IntentStatus(StrEnum):
    """Lifecycle states for an Intent."""

    CREATED = "created"
    QUEUED = "queued"
    EVALUATING = "evaluating"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ExecutionStatus(StrEnum):
    """Lifecycle states for an Execution."""

    CREATED = "created"
    PLANNED = "planned"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class EffectStatus(StrEnum):
    """Lifecycle states for an Effect."""

    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class TaskStatus(StrEnum):
    """Lifecycle states for a Task (queue item)."""

    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    """Lifecycle states for an Approval."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ComputeKind(StrEnum):
    """Classification of compute type."""

    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"
    REASONING = "reasoning"
    INFERENCE = "inference"
    SEARCH = "search"
    OPTIMIZATION = "optimization"
    SIMULATION = "simulation"
    SYMBOLIC = "symbolic"
    HUMAN = "human"


# ---------------------------------------------------------------------------
# Core protocol entities
# ---------------------------------------------------------------------------


class Identity(BaseModel):
    """Stable identity for any entity in the runtime."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: str = Field(description="Globally unique entity ID (UUID4).")
    kind: str = Field(description="Entity kind (e.g. 'agent', 'execution', 'task').")
    owner: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Capability(BaseModel):
    """A granted capability with optional scope and constraints."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    name: str = Field(description="Capability name (e.g. 'filesystem.write').")
    scope: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    delegate_to: str | None = None
    expires_at: datetime | None = None
    revoked: bool = False
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    issued_by: str | None = None


class Constraint(BaseModel):
    """A constraint on execution (time, resource, policy)."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    kind: str = Field(description="Constraint kind (e.g. 'time', 'cost', 'policy').")
    operator: str = "<="
    value: Any = None
    description: str | None = None


class Resource(BaseModel):
    """Resource accounting for an execution."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    cost: float = 0.0
    latency_ms: float | None = None
    energy: str | None = None
    memory_mb: float | None = None
    tokens: int | None = None
    bandwidth_mbps: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimeSpec(BaseModel):
    """Time-related constraints for an execution."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    deadline: datetime | None = None
    expires_at: datetime | None = None
    schedule: str | None = None
    retry_after: float | None = None
    max_retries: int | None = None
    interval: float | None = None


class ComputeSpec(BaseModel):
    """Specification for how a computation should be performed."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    kind: ComputeKind = ComputeKind.DETERMINISTIC
    provider: str | None = None
    model: str | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    resources: Resource | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Intent(BaseModel):
    """An intent — what an entity wants to accomplish."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: str = Field(description="Unique intent ID (UUID4).")
    name: str = Field(description="Intent name (e.g. 'summarize', 'deploy').")
    params: dict[str, Any] = Field(default_factory=dict)
    status: IntentStatus = IntentStatus.CREATED
    deadline: datetime | None = None
    requires: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    effect_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: Any = None
    error: str | None = None


class Effect(BaseModel):
    """A side-effect produced by an execution."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: str = Field(description="Unique effect ID (UUID4).")
    name: str = Field(description="Effect name (e.g. 'db.write', 'http.request').")
    intent_id: str | None = None
    capability_name: str | None = None
    reversible: bool = False
    idempotent: bool = False
    idempotency_key: str | None = None
    status: EffectStatus = EffectStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executed_at: datetime | None = None
    actor: str | None = None
    principal: str | None = None
    resource: str | None = None
    scope: str | None = None


class Execution(BaseModel):
    """A durable execution — the central runtime entity."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: str = Field(description="Unique execution ID (UUID4).")
    trace_id: str = Field(description="Correlation ID for distributed tracing.")
    parent_execution_id: str | None = None
    status: ExecutionStatus = ExecutionStatus.CREATED
    intent: Intent | None = None
    actor: str = "system"
    compute: ComputeSpec | None = None
    capabilities: list[str] = Field(default_factory=list)
    resources: Resource = Field(default_factory=Resource)
    effects: list[Effect] = Field(default_factory=list)
    state_changes: list[dict[str, Any]] = Field(default_factory=list)
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    checkpoint: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # -- runtime conversion ------------------------------------------------

    @classmethod
    def from_runtime_execution(
        cls,
        exec: Any,  # noqa: ANN401 — runtime.Execution
    ) -> Execution:
        """Convert a runtime ``Execution`` to a protocol ``Execution``.

        Runtime ``State`` objects in ``state_changes`` are converted to dicts
        via ``model_dump()`` so the protocol representation is JSON-safe.
        """
        return cls(
            id=exec.id,
            trace_id=exec.trace_id,
            parent_execution_id=exec.parent_execution_id,
            status=ExecutionStatus(exec.status.value),
            intent=exec.intent,
            actor=exec.actor,
            compute=exec.compute,
            capabilities=list(exec.capabilities),
            resources=exec.resources,
            effects=list(exec.effects),
            state_changes=[
                s.model_dump() if hasattr(s, "model_dump") else s
                for s in exec.state_changes
            ],
            result=exec.result,
            error=exec.error,
            metadata=dict(exec.metadata),
            checkpoint=exec.checkpoint,
            created_at=exec.created_at,
            started_at=exec.started_at,
            completed_at=exec.completed_at,
        )

    def to_runtime_execution(self) -> Any:  # noqa: ANN401
        """Convert this protocol ``Execution`` back to a runtime ``Execution``.

        Requires ``voodoo.runtime.execution.Execution`` to be importable.
        Uses a lazy import to avoid circular dependencies.
        """
        from voodoo.runtime.execution import Execution as RuntimeExecution
        from voodoo.runtime.execution import ExecutionStatus as RuntimeStatus

        return RuntimeExecution(
            id=self.id,
            trace_id=self.trace_id,
            parent_execution_id=self.parent_execution_id,
            status=RuntimeStatus(self.status.value),
            intent=self.intent,
            actor=self.actor,
            compute=self.compute,
            capabilities=list(self.capabilities),
            resources=self.resources,
            effects=list(self.effects),
            state_changes=self.state_changes,
            result=self.result,
            error=self.error,
            metadata=dict(self.metadata),
            checkpoint=self.checkpoint,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )


class Task(BaseModel):
    """A queued work item (worker task)."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: int = Field(description="Auto-increment task ID.")
    type: str = Field(description="Task type / handler name.")
    payload: Any = Field(description="Task payload (JSON-serializable).")
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    available_at: datetime | None = None
    attempts: int = 0
    max_attempts: int = 1
    locked_by: str | None = None
    locked_at: datetime | None = None
    lease_until: datetime | None = None
    idempotency_key: str | None = None
    trace_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None


class Event(BaseModel):
    """A mesh event envelope."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    event_id: str = Field(description="Unique event ID (UUID4).")
    event_type: str = Field(description="Dotted event type (e.g. 'agent.started').")
    timestamp: float = Field(description="Unix timestamp (seconds).")
    source: str = "voodoo"
    subject: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    payload: Any = None


class ObjectRef(BaseModel):
    """A reference to a stored object."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    key: str = Field(description="Object key / path.")
    bucket: str | None = None
    size_bytes: int | None = None
    content_type: str | None = None
    checksum: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Error(BaseModel):
    """A structured error."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    code: str = Field(description="Error code (e.g. 'CAPABILITY_DENIED').")
    message: str = Field(description="Human-readable error message.")
    execution_id: str | None = None
    trace_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    cause: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TelemetrySpan(BaseModel):
    """An OTel-compatible telemetry span."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    trace_id: str = Field(description="Correlation ID.")
    span_id: str = Field(description="Unique span ID (16-char hex).")
    parent_span_id: str | None = None
    name: str = Field(description="Span name (e.g. 'db.query').")
    start_time: datetime = Field(description="Span start time (UTC).")
    end_time: datetime | None = None
    status: str = "ok"
    attributes: dict[str, Any] = Field(default_factory=dict)


class Approval(BaseModel):
    """A human-in-the-loop approval request."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: str = Field(description="Unique approval ID (UUID4).")
    execution_id: str = Field(description="Execution waiting for approval.")
    trace_id: str = Field(description="Correlation ID.")
    capability: str | None = None
    question: str = ""
    requested_by: str = "system"
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    participant: str | None = None


class AgentEntity(BaseModel):
    """A registered agent entity."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    agent_id: str = Field(description="Unique agent ID (UUID4).")
    name: str = ""
    description: str = ""
    model: str = ""
    system_prompt: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    state: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentRun(BaseModel):
    """A record of an agent run."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    run_id: str = Field(description="Unique run ID (UUID4).")
    agent_id: str = ""
    execution_id: str | None = None
    prompt: str = ""
    output: str = ""
    status: str = "completed"
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    started_at: float = Field(description="Unix timestamp (seconds).")
    completed_at: float | None = None
    trace_id: str | None = None


class MemoryEntry(BaseModel):
    """A memory entry (layered memory system)."""

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    id: str = Field(description="Unique entry ID (UUID4).")
    entity_id: str = "default"
    layer: str = "durable"
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    source_execution_id: str | None = None
    importance: float = 0.5
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# Registry of all protocol entities (for export)
# ---------------------------------------------------------------------------

PROTOCOL_ENTITIES: dict[str, type[BaseModel]] = {
    "Identity": Identity,
    "Capability": Capability,
    "Constraint": Constraint,
    "Resource": Resource,
    "TimeSpec": TimeSpec,
    "ComputeSpec": ComputeSpec,
    "Intent": Intent,
    "Effect": Effect,
    "Execution": Execution,
    "Task": Task,
    "Event": Event,
    "ObjectRef": ObjectRef,
    "Error": Error,
    "TelemetrySpan": TelemetrySpan,
    "Approval": Approval,
    "AgentEntity": AgentEntity,
    "AgentRun": AgentRun,
    "MemoryEntry": MemoryEntry,
}
