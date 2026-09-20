from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from voodoo.world import Entity, Observation, WorldModel


def test_entity_projection_supports_dotted_paths() -> None:
    robot = Entity(type="robot", id="robot-1")
    robot.set("battery.level", 0.82)
    robot.set("pose.x", 12.5)

    assert robot.get("battery.level") == 0.82
    assert robot.get("pose.x") == 12.5
    assert robot.get("missing", "fallback") == "fallback"


def test_world_relationships_are_queryable_in_both_directions() -> None:
    world = WorldModel()
    robot = world.put_entity(Entity(type="robot", id="robot-1"))
    warehouse = world.put_entity(Entity(type="place", id="warehouse-2"))
    mission = world.put_entity(Entity(type="mission", id="mission-31"))

    world.relate(robot.id, "located_in", warehouse.id)
    world.relate(robot.id, "assigned_to", mission.id)

    assert [e.id for e in world.neighbors(robot.id, direction="out")] == [
        warehouse.id,
        mission.id,
    ]
    assert [e.id for e in world.neighbors(warehouse.id, direction="in")] == [robot.id]
    assert [e.id for e in world.neighbors(robot.id, predicate="assigned_to")] == [
        mission.id
    ]


def test_observation_updates_projection_and_preserves_lineage() -> None:
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))

    observation = world.observe(
        "robot-1",
        "battery.level",
        0.82,
        source="telemetry:bms",
        confidence=0.97,
        trace_id="trace-1",
        execution_id="exec-1",
    )

    robot = world.entity("robot-1")
    assert robot is not None
    assert robot.get("battery.level") == 0.82
    assert observation.source == "telemetry:bms"
    assert observation.confidence == 0.97
    assert observation.trace_id == "trace-1"
    assert observation.execution_id == "exec-1"

    snapshot = world.snapshot("robot-1")
    assert snapshot.latest_observations["battery.level"].id == observation.id


def test_stale_observation_is_retained_but_does_not_replace_projection() -> None:
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))

    now = datetime.now(UTC)
    world.observe(
        "robot-1",
        "battery.level",
        0.80,
        source="telemetry",
        observed_at=now,
    )
    stale = world.observe(
        "robot-1",
        "battery.level",
        0.95,
        source="delayed-packet",
        observed_at=now - timedelta(seconds=30),
    )

    robot = world.entity("robot-1")
    assert robot is not None
    assert robot.get("battery.level") == 0.80

    history = world.history("robot-1", "battery.level")
    assert [item.value for item in history] == [0.95, 0.80]
    assert history[0].id == stale.id


def test_duplicate_observation_id_is_idempotent() -> None:
    world = WorldModel()
    world.put_entity(Entity(type="sensor", id="sensor-1"))

    world.observe(
        "sensor-1",
        "temperature.c",
        23.1,
        source="sensor",
        observation_id="obs-1",
    )
    world.observe(
        "sensor-1",
        "temperature.c",
        99.9,
        source="duplicate-delivery",
        observation_id="obs-1",
    )

    history = world.history("sensor-1", "temperature.c")
    assert len(history) == 1
    assert history[0].value == 23.1


def test_unknown_relationship_endpoint_is_rejected() -> None:
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))

    with pytest.raises(KeyError, match="unknown world entity"):
        world.relate("robot-1", "located_in", "missing-place")


def test_observation_confidence_is_bounded() -> None:
    with pytest.raises(ValueError, match="confidence"):
        Observation(
            entity_id="robot-1",
            property="battery.level",
            value=0.8,
            source="telemetry",
            confidence=1.1,
        )
