from __future__ import annotations

from voodoo.primitives.capability import Capability
from voodoo.primitives.effect import Effect
from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine, bind_world, world_aware
from voodoo.runtime.execution.engine import ComputeResult
from voodoo.world import Entity, WorldModel


async def test_bound_world_is_visible_inside_compute_context():
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))
    world.observe("robot-1", "battery.level", 0.82, source="bms")
    engine = bind_world(ExecutionEngine(), world)
    engine.capabilities.register(Capability(name="robot.inspect"))

    async def inspect_robot(ctx):
        snapshot = ctx.world_snapshot()
        assert snapshot is not None
        return snapshot.entity.get("battery.level")

    execution = await engine.execute(
        Intent(
            name="inspect-robot",
            params={"entity_id": "robot-1"},
        ).require("robot.inspect"),
        world_aware(inspect_robot),
        capabilities=["robot.inspect"],
    )

    assert execution.result == 0.82


async def test_context_observation_carries_execution_lineage():
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))
    engine = bind_world(ExecutionEngine(), world)
    engine.capabilities.register(Capability(name="robot.observe"))

    async def observe_robot(ctx):
        observation = ctx.observe(
            "robot-1",
            "position.x",
            12.5,
            source="localization",
        )
        return observation.id

    execution = await engine.execute(
        Intent(
            name="observe-robot",
            params={"entity_id": "robot-1"},
        ).require("robot.observe"),
        world_aware(observe_robot),
        capabilities=["robot.observe"],
    )

    history = world.history("robot-1", "position.x")
    assert len(history) == 1
    assert history[0].execution_id == execution.id
    assert history[0].trace_id == execution.trace_id
    entity = world.entity("robot-1")
    assert entity is not None
    assert entity.get("position.x") == 12.5


async def test_effect_does_not_become_observed_world_truth():
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))
    world.observe("robot-1", "motor.speed", 0, source="motor-controller")
    engine = bind_world(ExecutionEngine(), world)
    engine.capabilities.register(Capability(name="motor.drive"))

    async def command_motor(ctx):
        return ComputeResult(
            value="commanded",
            effects=[Effect(name="motor.drive")],
        )

    execution = await engine.execute(
        Intent(
            name="drive",
            params={"entity_id": "robot-1"},
        ).require("motor.drive"),
        world_aware(command_motor),
        capabilities=["motor.drive"],
    )

    assert execution.result == "commanded"
    assert len(execution.effects) == 1
    entity = world.entity("robot-1")
    assert entity is not None
    assert entity.get("motor.speed") == 0


async def test_world_binding_is_shared_with_contextual_policy():
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))
    world.observe("robot-1", "battery.level", 0.1, source="bms")
    engine = bind_world(ExecutionEngine(), world)

    assert engine.capabilities.policy.world is world
