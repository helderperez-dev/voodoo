"""Sprint 27 operational protocol convergence tests."""

from __future__ import annotations

from datetime import UTC, datetime

from voodoo.protocol import (
    Entity,
    Goal,
    GoalRun,
    Observation,
    RemoteExecutionOutcome,
    RemoteExecutionRequest,
    RemoteOutcomeStatus,
    WorldSnapshot,
    export_json_schemas,
    schema_for,
)


def test_operational_entities_round_trip() -> None:
    now = datetime.now(UTC)
    observation = Observation(
        id="obs-1",
        entity_id="device:lab",
        property="temperature",
        value=24.0,
        source="edge:device-lab",
        confidence=0.98,
        observed_at=now,
        received_at=now,
        trace_id="trace-1",
        execution_id="exec-1",
    )
    snapshot = WorldSnapshot(
        entity=Entity(
            id="device:lab",
            type="device",
            properties={"temperature": 24.0},
        ),
        latest_observations={"temperature": observation},
    )

    restored = WorldSnapshot.model_validate(snapshot.model_dump(mode="json"))

    assert restored.entity.id == "device:lab"
    assert restored.latest_observations["temperature"].execution_id == "exec-1"


def test_goal_and_remote_execution_are_protocol_surface() -> None:
    goal = Goal(id="goal-1", name="keep-lab-safe", target_entity_id="device:lab")
    run = GoalRun(goal=goal)
    request = RemoteExecutionRequest(
        request_id="request-1",
        actor="device:controller",
        intent_name="cool-lab",
        capabilities=["cooling.set"],
        target_entity_id="device:lab",
        idempotency_key="idem-1",
    )
    outcome = RemoteExecutionOutcome(
        request_id=request.request_id,
        status=RemoteOutcomeStatus.COMPLETED,
        execution_id="exec-1",
        result={"ok": True},
    )

    assert GoalRun.model_validate(run.model_dump(mode="json")).goal.id == "goal-1"
    assert RemoteExecutionRequest.model_validate(
        request.model_dump(mode="json")
    ).idempotency_key == "idem-1"
    assert RemoteExecutionOutcome.model_validate(
        outcome.model_dump(mode="json")
    ).status is RemoteOutcomeStatus.COMPLETED


def test_schema_export_includes_post_sprint_24_runtime_semantics() -> None:
    schemas = export_json_schemas()

    for name in (
        "Entity",
        "Relationship",
        "Observation",
        "WorldSnapshot",
        "Goal",
        "GoalRun",
        "RemoteExecutionRequest",
        "RemoteExecutionOutcome",
    ):
        assert name in schemas
        assert schemas[name]["x-voodoo-schema-version"] >= 1
        assert schema_for(name)["$id"].startswith("urn:voodoo:protocol:")
