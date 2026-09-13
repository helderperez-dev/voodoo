from __future__ import annotations

from datetime import UTC, datetime, timedelta

from voodoo.world import Entity, SQLiteWorldStore, WorldModel


def test_world_survives_store_reopen(tmp_path):
    path = tmp_path / "world.db"

    store = SQLiteWorldStore(str(path))
    world = WorldModel(store)
    world.put_entity(Entity(id="robot-1", type="robot"))
    world.put_entity(Entity(id="room-1", type="place"))
    world.relate("robot-1", "located_in", "room-1", metadata={"source": "map"})
    world.observe(
        "robot-1",
        "battery.level",
        0.82,
        source="telemetry:bms",
        confidence=0.97,
        trace_id="trace-1",
        execution_id="exec-1",
        observation_id="obs-1",
    )
    store.close()

    reopened = SQLiteWorldStore(str(path))
    recovered = WorldModel(reopened)

    robot = recovered.entity("robot-1")
    assert robot is not None
    assert robot.get("battery.level") == 0.82

    neighbors = recovered.neighbors("robot-1", predicate="located_in")
    assert [entity.id for entity in neighbors] == ["room-1"]

    history = recovered.history("robot-1", "battery.level")
    assert len(history) == 1
    assert history[0].id == "obs-1"
    assert history[0].trace_id == "trace-1"
    assert history[0].execution_id == "exec-1"
    assert history[0].confidence == 0.97
    reopened.close()


def test_duplicate_observation_remains_idempotent_after_restart(tmp_path):
    path = tmp_path / "world.db"
    store = SQLiteWorldStore(str(path))
    world = WorldModel(store)
    world.put_entity(Entity(id="sensor-1", type="sensor"))

    world.observe(
        "sensor-1",
        "temperature",
        22.5,
        source="sensor",
        observation_id="reading-1",
    )
    world.observe(
        "sensor-1",
        "temperature",
        22.5,
        source="sensor",
        observation_id="reading-1",
    )
    store.close()

    reopened = SQLiteWorldStore(str(path))
    recovered = WorldModel(reopened)
    assert len(recovered.history("sensor-1", "temperature")) == 1
    reopened.close()


def test_stale_observation_is_history_not_current_state_after_restart(tmp_path):
    path = tmp_path / "world.db"
    store = SQLiteWorldStore(str(path))
    world = WorldModel(store)
    world.put_entity(Entity(id="robot-1", type="robot"))

    now = datetime.now(UTC)
    world.observe(
        "robot-1",
        "battery.level",
        0.60,
        source="bms",
        observed_at=now,
        observation_id="newer",
    )
    world.observe(
        "robot-1",
        "battery.level",
        0.90,
        source="bms",
        observed_at=now - timedelta(minutes=5),
        observation_id="older",
    )
    store.close()

    reopened = SQLiteWorldStore(str(path))
    recovered = WorldModel(reopened)
    robot = recovered.entity("robot-1")
    assert robot is not None
    assert robot.get("battery.level") == 0.60
    assert [item.id for item in recovered.history("robot-1", "battery.level")] == [
        "older",
        "newer",
    ]
    reopened.close()


def test_relationship_queries_survive_restart(tmp_path):
    path = tmp_path / "world.db"
    store = SQLiteWorldStore(str(path))
    world = WorldModel(store)
    world.put_entity(Entity(id="agent-1", type="agent"))
    world.put_entity(Entity(id="robot-1", type="robot"))
    world.relate("agent-1", "controls", "robot-1", relationship_id="rel-1")
    store.close()

    reopened = SQLiteWorldStore(str(path))
    recovered = WorldModel(reopened)
    outbound = recovered.relationships("agent-1", predicate="controls", direction="out")
    inbound = recovered.relationships("robot-1", predicate="controls", direction="in")
    assert [relationship.id for relationship in outbound] == ["rel-1"]
    assert [relationship.id for relationship in inbound] == ["rel-1"]
    reopened.close()
