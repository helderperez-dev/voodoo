"""Voodoo protocol — canonical entity schemas for cross-language interop.

This package defines the **stable semantic boundary** for the Voodoo runtime.
Every entity is a Pydantic model with a ``schema_version`` field and full
JSON Schema export support.

Quick start::

    from voodoo.protocol import Execution, Intent, SCHEMA_VERSION

    intent = Intent(name="summarize", params={"text": "hello"})
    execution = Execution(
        id="exec-001",
        trace_id="trace-001",
        intent=intent,
    )

    # Serialize to JSON
    data = execution.model_dump(mode="json")

    # Round-trip
    restored = Execution.model_validate(data)

    # Export JSON Schema
    from voodoo.protocol import export_json_schemas
    schemas = export_json_schemas()

See ``docs/protocol.md`` for the compatibility policy.
"""

from __future__ import annotations

from .export import export_json_schemas, export_json_schemas_json, schema_for
from .schemas import (
    PROTOCOL_ENTITIES,
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

__all__ = [
    # Schema metadata
    "SCHEMA_VERSION",
    "PROTOCOL_ENTITIES",
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
    # Export
    "export_json_schemas",
    "export_json_schemas_json",
    "schema_for",
]
