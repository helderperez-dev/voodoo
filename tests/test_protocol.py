"""Tests for the language-neutral Voodoo protocol schemas."""

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
    Entity,
    Error,
    Event,
    Execution,
    ExecutionStatus,
    Goal,
    GoalIntentRun,
    GoalRun,
    GoalStatus,
    Identity,
    Intent,
    IntentStatus,
    MemoryEntry,
    ObjectRef,
    Observation,
    Relationship,
    RemoteExecutionOutcome,
    RemoteExecutionRequest,
    RemoteOutcomeStatus,
    Resource,
    Task,
    TaskStatus,
    TelemetrySpan,
    TimeSpec,
    WorldSnapshot,
    export_json_schemas,
    export_json_schemas_json,
    schema_for,
)


_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _factories():
    identity = Identity(id="identity-1", kind="user", name="Ada")
    intent = Intent(id="intent-1", name="summarize", params={"text": "hello"})
    capability = Capability(name="text.summarize")
    effect = Effect(id="effect-1", kind="result", payload={"ok": True})
    execution = Execution(
        id="exec-1", trace_id="trace-1", intent=intent, actor=identity
    )
    entity = Entity(id="entity-1", type="device", properties={"temperature": 22.0})
    observation = Observation(
        id="observation-1",
        entity_id=entity.id,
        property="temperature",
        value=22.0,
        source="sensor",
        observed_at=_NOW,
        received_at=_NOW,
    )
    goal = Goal(id="goal-1", name="keep-safe", objective="Keep the room safe")
    goal_intent_run = GoalIntentRun(
        intent_id=intent.id,
        intent_name=intent.name,
        status="completed",
        execution_id=execution.id,
        trace_id=execution.trace_id,
        result="ok",
    )
    return {
        "Identity": lambda: identity,
        "Capability": lambda: capability,
        "Constraint": lambda: Constraint(kind="budget", value=10),
        "Resource": lambda: Resource(cost=0.1, latency_ms=12),
        "TimeSpec": lambda: TimeSpec(deadline=_NOW, retries=2),
        "ComputeSpec": lambda: ComputeSpec(kind=ComputeKind.DETERMINISTIC),
        "Intent": lambda: intent,
        "Effect": lambda: effect,
        "Execution": lambda: execution,
        "Task": lambda: Task(id="task-1", name="work", status=TaskStatus.PENDING),
        "Event": lambda: Event(id="event-1", name="thing.happened", payload={}),
        "ObjectRef": lambda: ObjectRef(uri="object://bucket/key"),
        "Error": lambda: Error(code="FAILED", message="nope"),
        "TelemetrySpan": lambda: TelemetrySpan(
            trace_id="trace-1", span_id="span-1", name="test", started_at=_NOW
        ),
        "Approval": lambda: Approval(
            id="approval-1", status=ApprovalStatus.PENDING, prompt="Approve?"
        ),
        "AgentEntity": lambda: AgentEntity(id="agent-1", name="helper"),
        "AgentRun": lambda: AgentRun(
            id="run-1", agent_id="agent-1", status="completed", output="done"
        ),
        "MemoryEntry": lambda: MemoryEntry(
            id="memory-1", entity_id="agent-1", content="remember"
        ),
        "Entity": lambda: entity,
        "Relationship": lambda: Relationship(
            id="relationship-1",
            source_id="entity-1",
            predicate="located_in",
            target_id="zone-1",
        ),
        "Observation": lambda: observation,
        "WorldSnapshot": lambda: WorldSnapshot(
            entity=entity, latest_observations={"temperature": observation}
        ),
        "Goal": lambda: goal,
        "GoalIntentRun": lambda: goal_intent_run,
        "GoalRun": lambda: GoalRun(
            goal=goal,
            planned_intents=[intent],
            intent_runs=[goal_intent_run],
            started_at=_NOW,
        ),
        "RemoteExecutionRequest": lambda: RemoteExecutionRequest(
            request_id="request-1", operation="thing.run", arguments={}
        ),
        "RemoteExecutionOutcome": lambda: RemoteExecutionOutcome(
            request_id="request-1",
            operation="thing.run",
            status=RemoteOutcomeStatus.COMPLETED,
            result="ok",
        ),
    }


_ENTITY_FACTORIES = _factories()


class TestSchemaVersion:
    def test_constant_is_positive_integer(self) -> None:
        assert isinstance(SCHEMA_VERSION, int)
        assert SCHEMA_VERSION >= 1

    def test_every_entity_carries_schema_version(self) -> None:
        for factory in _ENTITY_FACTORIES.values():
            entity = factory()
            assert entity.schema_version == SCHEMA_VERSION


class TestRoundTrips:
    @pytest.mark.parametrize("name", sorted(_ENTITY_FACTORIES))
    def test_round_trip(self, name: str) -> None:
        entity = _ENTITY_FACTORIES[name]()
        dumped = entity.model_dump(mode="json")
        restored = type(entity).model_validate(dumped)
        assert restored == entity


class TestEnums:
    def test_execution_status(self) -> None:
        assert ExecutionStatus.WAITING.value == "waiting"
        assert ExecutionStatus.COMPLETED.value == "completed"

    def test_intent_status(self) -> None:
        assert IntentStatus.EXECUTING.value == "executing"

    def test_effect_status(self) -> None:
        assert EffectStatus.SUCCEEDED.value == "succeeded"

    def test_task_status(self) -> None:
        assert TaskStatus.RETRYING.value == "retrying"

    def test_approval_status(self) -> None:
        assert ApprovalStatus.APPROVED.value == "approved"


class TestSchemaExport:
    def test_export_matches_public_registry(self) -> None:
        exported = export_json_schemas()
        assert set(exported) == set(PROTOCOL_ENTITIES)

    def test_json_export_is_parseable(self) -> None:
        exported = json.loads(export_json_schemas_json())
        assert set(exported) == set(PROTOCOL_ENTITIES)

    def test_single_schema(self) -> None:
        schema = schema_for("Execution")
        assert schema["title"] == "Execution"

    def test_all_registered_schemas_are_retrievable(self) -> None:
        for name in PROTOCOL_ENTITIES:
            schema = schema_for(name)
            assert schema["title"] == name


class TestProtocolEntities:
    """PROTOCOL_ENTITIES must represent the complete stable boundary."""

    def test_all_factories_registered(self) -> None:
        assert set(_ENTITY_FACTORIES) == set(PROTOCOL_ENTITIES)

    def test_registry_contains_core_and_operational_semantics(self) -> None:
        assert {
            "Execution",
            "Intent",
            "Capability",
            "Entity",
            "Observation",
            "WorldSnapshot",
            "Goal",
            "GoalRun",
            "RemoteExecutionRequest",
            "RemoteExecutionOutcome",
        } <= set(PROTOCOL_ENTITIES)

    def test_registry_values_are_classes(self) -> None:
        for name, cls in PROTOCOL_ENTITIES.items():
            assert hasattr(cls, "model_dump"), f"{name} is not a Pydantic model"


class TestJsonFriendly:
    """All serialized values must be JSON-compatible primitives."""

    @pytest.mark.parametrize("name", sorted(_ENTITY_FACTORIES))
    def test_dump_is_json_serializable(self, name: str) -> None:
        dumped = _ENTITY_FACTORIES[name]().model_dump(mode="json")
        json.dumps(dumped)
