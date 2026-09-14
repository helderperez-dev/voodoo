"""Voodoo protocol — stable semantic schemas for cross-language interop.

The protocol is the boundary for participants that must understand Voodoo
semantics without importing Python runtime internals. Sprint 28 extends the
operational protocol with governed node-fabric membership and routed work.
"""

from __future__ import annotations

from .export import export_json_schemas, export_json_schemas_json, schema_for
from .fabric import (
    FABRIC_PROTOCOL_ENTITIES,
    FABRIC_SCHEMA_VERSION,
    FabricWorkOutcome,
    FabricWorkRequest,
    NodeAdvertisement,
    NodeMembership,
)
from .operational import (
    OPERATIONAL_PROTOCOL_ENTITIES,
    Entity,
    Goal,
    GoalIntentRun,
    GoalRun,
    GoalStatus,
    Observation,
    Relationship,
    RemoteExecutionOutcome,
    RemoteExecutionRequest,
    RemoteOutcomeStatus,
    WorldSnapshot,
)
from .schemas import PROTOCOL_ENTITIES as CORE_PROTOCOL_ENTITIES
from .schemas import (
    SCHEMA_VERSION,
    AgentEntity,
    AgentRun,
    Approval,
    ApprovalStatus,
    Capability,
    ComputeKind,
    ComputeSpec,
    Constraint,
    Effect,
    EffectStatus,
    Error,
    Event,
    Execution,
    ExecutionStatus,
    Identity,
    Intent,
    IntentStatus,
    MemoryEntry,
    ObjectRef,
    Resource,
    Task,
    TaskStatus,
    TelemetrySpan,
    TimeSpec,
)

PROTOCOL_ENTITIES = {
    **CORE_PROTOCOL_ENTITIES,
    **OPERATIONAL_PROTOCOL_ENTITIES,
    **FABRIC_PROTOCOL_ENTITIES,
}

__all__ = [
    "SCHEMA_VERSION",
    "FABRIC_SCHEMA_VERSION",
    "PROTOCOL_ENTITIES",
    "OPERATIONAL_PROTOCOL_ENTITIES",
    "FABRIC_PROTOCOL_ENTITIES",
    "ExecutionStatus",
    "IntentStatus",
    "EffectStatus",
    "TaskStatus",
    "ApprovalStatus",
    "ComputeKind",
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
    "NodeAdvertisement",
    "NodeMembership",
    "FabricWorkRequest",
    "FabricWorkOutcome",
    "export_json_schemas",
    "export_json_schemas_json",
    "schema_for",
]
