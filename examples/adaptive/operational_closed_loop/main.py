"""Sprint 27 operational closed-loop canary.

A zero-infrastructure executable proof that physical-style evidence and action
share the same Voodoo runtime semantics:

Device state → Edge → Observation → World → Goal/Intent → Planner →
Capability → Execution → Effect delivery → ACK/evidence → Observation → World

Run with::

    python examples/operational_closed_loop/main.py
"""

from __future__ import annotations

import asyncio
from typing import Any

from voodoo.edge import WorldAwareDeviceGateway
from voodoo.edge.models import AuthenticatedDeviceContext, Device, TransportKind
from voodoo.edge.protocol import EdgeMessage, EdgeMessageType
from voodoo.edge.store import InMemoryDeviceStore
from voodoo.primitives.capability import Capability
from voodoo.runtime import (
    AdaptiveSupervisor,
    ComputeParticipant,
    ExecutionEngine,
    Goal,
    GoalRuntime,
    Planner,
)
from voodoo.world import WorldModel


async def run_canary() -> dict[str, Any]:
    world = WorldModel()
    store = InMemoryDeviceStore()
    engine = ExecutionEngine()

    device = Device(
        device_id="device_lab_cooling",
        type="simulated-controller",
        name="Lab cooling controller",
        capabilities=["cooling.set"],
    )
    await store.register_device(device)
    ctx = AuthenticatedDeviceContext(
        device_id=device.device_id,
        device_type=device.type,
        capabilities=list(device.capabilities),
        transport=TransportKind.HTTP,
    )
    gateway = WorldAwareDeviceGateway(store, engine, world=world)

    # 1. Physical-style evidence enters through Edge and becomes World truth.
    await gateway.handle_state_sync(
        EdgeMessage(
            type=EdgeMessageType.STATE_SYNC,
            message_id="canary-state-hot",
            device_id=device.device_id,
            payload={"state_version": 1, "state": {"temperature": 34.0}},
        ),
        ctx,
    )

    # 2. Runtime authority is registered separately from the device's advertised
    # implementation capability.
    engine.capabilities.register(Capability(name="cooling.set"))
    planner = Planner(engine=engine)

    async def set_cooling(exec_ctx: Any) -> dict[str, Any]:
        effect_id = f"effect:{exec_ctx.execution_id}"
        await gateway.submit_effect(
            effect_id=effect_id,
            execution_id=exec_ctx.execution_id,
            device_id=device.device_id,
            capability="cooling.set",
            payload={"target_temperature": 24.0},
        )
        return {"effect_id": effect_id, "target_temperature": 24.0}

    planner.register(
        ComputeParticipant(
            name="lab-controller",
            kind="compute",
            capabilities=["cooling.set"],
            compute=set_cooling,
            metadata={"entity_id": device.entity_id, "priority": 10},
        )
    )
    supervisor = AdaptiveSupervisor(planner, engine=engine)
    goals = GoalRuntime(supervisor, world=world)

    goal = Goal(
        name="keep-lab-safe",
        objective="Bring the laboratory temperature to a safe level.",
        target_entity_id=device.entity_id,
        requires=["cooling.set"],
    )
    run = await goals.achieve(goal)
    if run.status.value != "completed":
        raise RuntimeError(run.error or f"goal stopped as {run.status.value}")

    effect_id = run.result["effect_id"]

    # 3. The Effect itself did not mutate World truth. Only the device's ACK
    # with measured evidence closes the loop.
    before_ack = world.entity(device.entity_id).get("temperature")
    await gateway.handle_effect_ack(
        EdgeMessage(
            type=EdgeMessageType.EFFECT_ACK,
            message_id="canary-ack-safe",
            device_id=device.device_id,
            payload={
                "effect_id": effect_id,
                "execution_id": run.intent_runs[0].execution_id,
                "status": "completed",
                "observed_state": {"temperature": 24.0},
            },
        ),
        ctx,
    )
    after_ack = world.entity(device.entity_id).get("temperature")

    return {
        "goal_status": run.status.value,
        "execution_id": run.intent_runs[0].execution_id,
        "effect_id": effect_id,
        "temperature_before_ack": before_ack,
        "temperature_after_ack": after_ack,
        "observation_count": len(world.history(device.entity_id)),
        "world": world.snapshot(device.entity_id),
    }


async def main() -> None:
    result = await run_canary()
    print("Voodoo operational closed loop: OK")
    print(f"execution: {result['execution_id']}")
    print(f"effect: {result['effect_id']}")
    print(
        "temperature: "
        f"{result['temperature_before_ack']} → {result['temperature_after_ack']}"
    )
    print(f"observations: {result['observation_count']}")


if __name__ == "__main__":
    asyncio.run(main())
