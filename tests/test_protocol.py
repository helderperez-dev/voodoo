"""Tests for voodoo.protocol — round-trip serialization and JSON Schema export.

Sprint 21: Protocol schemas & versioning.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from voodoo.protocol import (
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
    export_json_schemas,
    export_json_schemas_json,
    schema_for,
)

# ---------------------------------------------------------------------------
# Fixtures — minimal valid instances for every entity
# ---------------------------------------------------------------------------


def _make_identity() -> Identity:
    return Identity(id="id-1", kind="agent")


def _make_capability() -> Capability:
    return Capability(name="filesystem.read")


def _make_constraint() -> Constraint:
    return Constraint(kind="rate_limit", operator="<=", value=100)


def _make_resource() -> Resource:
    return Resource(cost=0.05, latency_ms=120.0, tokens=500)


def _make_time_spec() -> TimeSpec:
    return TimeSpec(max_retries=3, interval=1.0)


def _make_compute_spec() -> ComputeSpec:
    return ComputeSpec(kind=ComputeKind.INFERENCE, provider="openai", model="gpt-4o")


def _make_intent() -> Intent:
    return Intent(id="intent-1", name="summarize", params={"text": "hello world"})


def _make_effect() -> Effect:
    return Effect(
        id="eff-1",
        name="file_write",
        status=EffectStatus.SUCCEEDED,
        result={"path": "/tmp/out.txt"},
    )


def _make_execution() -> Execution:
    return Execution(
        id="exec-1",
        trace_id="trace-1",
        intent=_make_intent(),
        status=ExecutionStatus.COMPLETED,
    )


def _make_task() -> Task:
    return Task(
        id=1,
        type="process",
        payload={"data": "value"},
        status=TaskStatus.COMPLETED,
    )


def _make_event() -> Event:
    return Event(
        event_id="evt-1",
        event_type="execution.started",
        timestamp=1735689600.0,
        source="runtime",
        payload={"execution_id": "exec-1"},
    )


def _make_object_ref() -> ObjectRef:
    return ObjectRef(
        key="/tmp/test.txt",
        size_bytes=1024,
        content_type="text/plain",
    )


def _make_error() -> Error:
    return Error(code="E_TIMEOUT", message="Operation timed out")


def _make_telemetry_span() -> TelemetrySpan:
    return TelemetrySpan(
        trace_id="trace-1",
        span_id="aabbccdd11223344",
        name="llm.complete",
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 1, 1, 0, 0, 1, tzinfo=UTC),
        status="ok",
    )


def _make_approval() -> Approval:
    return Approval(
        id="appr-1",
        execution_id="exec-1",
        trace_id="trace-1",
        status=ApprovalStatus.APPROVED,
        decided_by="human-1",
    )


def _make_agent_entity() -> AgentEntity:
    return AgentEntity(
        agent_id="agent-1",
        name="summarizer",
        capabilities=["filesystem.read"],
    )


def _make_agent_run() -> AgentRun:
    return AgentRun(
        run_id="run-1",
        agent_id="agent-1",
        execution_id="exec-1",
        status="completed",
        started_at=1735689600.0,
    )


def _make_memory_entry() -> MemoryEntry:
    return MemoryEntry(
        id="mem-1",
        entity_id="agent-1",
        content="It was great.",
    )


# Map entity name → factory for parametrized tests
_ENTITY_FACTORIES: dict[str, callable] = {
    "Identity": _make_identity,
    "Capability": _make_capability,
    "Constraint": _make_constraint,
    "Resource": _make_resource,
    "TimeSpec": _make_time_spec,
    "ComputeSpec": _make_compute_spec,
    "Intent": _make_intent,
    "Effect": _make_effect,
    "Execution": _make_execution,
    "Task": _make_task,
    "Event": _make_event,
    "ObjectRef": _make_object_ref,
    "Error": _make_error,
    "TelemetrySpan": _make_telemetry_span,
    "Approval": _make_approval,
    "AgentEntity": _make_agent_entity,
    "AgentRun": _make_agent_run,
    "MemoryEntry": _make_memory_entry,
}


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Every entity must survive serialize → deserialize without data loss."""

    @pytest.mark.parametrize("name", sorted(_ENTITY_FACTORIES.keys()))
    def test_round_trip(self, name: str) -> None:
        factory = _ENTITY_FACTORIES[name]
        original = factory()
        data = original.model_dump(mode="json")
        restored = type(original).model_validate(data)
        assert restored == original

    @pytest.mark.parametrize("name", sorted(_ENTITY_FACTORIES.keys()))
    def test_json_string_round_trip(self, name: str) -> None:
        """Serialize to JSON string and back — tests full JSON compat."""
        factory = _ENTITY_FACTORIES[name]
        original = factory()
        json_str = original.model_dump_json()
        restored = type(original).model_validate_json(json_str)
        assert restored == original


# ---------------------------------------------------------------------------
# Schema version tests
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    """Every entity carries a schema_version field."""

    @pytest.mark.parametrize("name", sorted(_ENTITY_FACTORIES.keys()))
    def test_schema_version_present(self, name: str) -> None:
        factory = _ENTITY_FACTORIES[name]
        instance = factory()
        data = instance.model_dump(mode="json")
        assert "schema_version" in data
        assert data["schema_version"] == SCHEMA_VERSION

    @pytest.mark.parametrize("name", sorted(_ENTITY_FACTORIES.keys()))
    def test_schema_version_ge_1(self, name: str) -> None:
        factory = _ENTITY_FACTORIES[name]
        instance = factory()
        assert instance.schema_version >= 1


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    """All enums must have expected members."""

    def test_execution_status_values(self) -> None:
        expected = {
            "created",
            "planned",
            "authorized",
            "running",
            "waiting",
            "completed",
            "failed",
            "cancelled",
            "timed_out",
        }
        assert {s.value for s in ExecutionStatus} == expected

    def test_intent_status_values(self) -> None:
        expected = {
            "created",
            "queued",
            "evaluating",
            "executing",
            "paused",
            "completed",
            "rejected",
            "expired",
            "cancelled",
        }
        assert {s.value for s in IntentStatus} == expected

    def test_effect_status_values(self) -> None:
        expected = {"pending", "executing", "succeeded", "failed", "rolled_back"}
        assert {s.value for s in EffectStatus} == expected

    def test_task_status_values(self) -> None:
        expected = {"pending", "running", "retrying", "completed", "failed"}
        assert {s.value for s in TaskStatus} == expected

    def test_approval_status_values(self) -> None:
        expected = {"pending", "approved", "denied"}
        assert {s.value for s in ApprovalStatus} == expected

    def test_compute_kind_values(self) -> None:
        expected = {
            "deterministic",
            "probabilistic",
            "reasoning",
            "inference",
            "search",
            "optimization",
            "simulation",
            "symbolic",
            "human",
        }
        assert {s.value for s in ComputeKind} == expected


# ---------------------------------------------------------------------------
# JSON Schema export tests
# ---------------------------------------------------------------------------


class TestJsonSchemaExport:
    """export_json_schemas must produce valid, complete schema dicts."""

    def test_export_returns_all_entities(self) -> None:
        schemas = export_json_schemas()
        assert set(schemas.keys()) == set(PROTOCOL_ENTITIES.keys())

    def test_export_contains_metadata(self) -> None:
        schemas = export_json_schemas()
        for name, schema in schemas.items():
            assert "$schema" in schema, f"{name} missing $schema"
            assert "$id" in schema, f"{name} missing $id"
            assert "x-voodoo-schema-version" in schema, f"{name} missing version"
            assert schema["x-voodoo-schema-version"] == SCHEMA_VERSION

    def test_export_json_string_is_valid_json(self) -> None:
        json_str = export_json_schemas_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert len(parsed) == len(PROTOCOL_ENTITIES)

    def test_schema_for_single_entity(self) -> None:
        schema = schema_for("Execution")
        assert schema["title"] == "Execution"
        assert "properties" in schema

    def test_schema_for_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            schema_for("NonExistentEntity")

    def test_schema_for_all_entities(self) -> None:
        """Every entity in PROTOCOL_ENTITIES must be retrievable by name."""
        for name in PROTOCOL_ENTITIES:
            schema = schema_for(name)
            assert schema["title"] == name


# ---------------------------------------------------------------------------
# PROTOCOL_ENTITIES registry tests
# ---------------------------------------------------------------------------


class TestProtocolEntities:
    """PROTOCOL_ENTITIES must be complete and consistent."""

    def test_all_factories_registered(self) -> None:
        for name in _ENTITY_FACTORIES:
            assert name in PROTOCOL_ENTITIES, f"{name} not in PROTOCOL_ENTITIES"

    def test_registry_count(self) -> None:
        assert len(PROTOCOL_ENTITIES) == 18

    def test_registry_values_are_classes(self) -> None:
        for name, cls in PROTOCOL_ENTITIES.items():
            assert hasattr(cls, "model_dump"), f"{name} is not a Pydantic model"


# ---------------------------------------------------------------------------
# JSON-friendly serialization tests
# ---------------------------------------------------------------------------


class TestJsonFriendly:
    """All serialized values must be JSON-compatible primitives."""

    @pytest.mark.parametrize("name", sorted(_ENTITY_FACTORIES.keys()))
    def test_dump_is_json_serializable(self, name: str) -> None:
        factory = _ENTITY_FACTORIES[name]
        instance = factory()
        data = instance.model_dump(mode="json")
        # Must not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    def test_execution_nested_intent_serializes(self) -> None:
        exec_ = _make_execution()
        data = exec_.model_dump(mode="json")
        assert isinstance(data["intent"], dict)
        assert data["intent"]["name"] == "summarize"

    def test_agent_entity_nested_capabilities_serialize(self) -> None:
        agent = _make_agent_entity()
        data = agent.model_dump(mode="json")
        assert isinstance(data["capabilities"], list)
        assert len(data["capabilities"]) == 1
        assert data["capabilities"][0] == "filesystem.read"
