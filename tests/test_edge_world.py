"""Sprint 27 — Edge evidence converges into the World Model."""

from __future__ import annotations

from voodoo.edge import WorldAwareDeviceGateway
from voodoo.edge.models import AuthenticatedDeviceContext, Device, TransportKind
from voodoo.edge.protocol import EdgeMessage, EdgeMessageType
from voodoo.edge.store import InMemoryDeviceStore
from voodoo.runtime.engine import ExecutionEngine
from voodoo.world import WorldModel


def _context(device: Device) -> AuthenticatedDeviceContext:
    return AuthenticatedDeviceContext(
        device_id=device.device_id,
        capabilities=list(device.capabilities),
        transport=TransportKind.HTTP,
    )


async def test_state_sync_projects_observations_into_world() -> None:
    store = InMemoryDeviceStore()
    device = Device(device_id="device_sensor", type="esp32")
    await store.add_device(device)
    world = WorldModel()
    gateway = WorldAwareDeviceGateway(store, ExecutionEngine(), world=world)

    message = EdgeMessage(
        type=EdgeMessageType.STATE_SYNC,
        message_id="msg-state-1",
        device_id=device.device_id,
        payload={
            "state_version": 1,
            "state": {"temperature": 22.5, "battery": {"level": 81}},
        },
    )
    response = await gateway.handle_state_sync(message, _context(device))

    assert response.payload["status"] == "accepted"
    entity = world.entity(device.entity_id)
    assert entity is not None
    assert entity.get("temperature") == 22.5
    assert entity.get("battery.level") == 81
    history = world.history(device.entity_id)
    assert {item.property for item in history} == {"temperature", "battery.level"}
    assert all(item.source == "edge:device_sensor" for item in history)


async def test_semantic_event_ingests_only_explicit_observations() -> None:
    store = InMemoryDeviceStore()
    device = Device(device_id="device_motion", type="esp32")
    await store.add_device(device)
    world = WorldModel()
    engine = ExecutionEngine()
    gateway = WorldAwareDeviceGateway(store, engine, world=world)

    message = EdgeMessage(
        type=EdgeMessageType.EVENT,
        message_id="msg-event-1",
        device_id=device.device_id,
        payload={
            "event_name": "motion.detected",
            "event_payload": {
                "zone": "hallway",
                "observations": [
                    {"property": "motion.detected", "value": True, "confidence": 0.9},
                    {"property": "location.zone", "value": "hallway"},
                ],
            },
        },
    )
    response = await gateway.handle_event(message, _context(device))

    execution_id = response.payload["execution_id"]
    assert execution_id
    entity = world.entity(device.entity_id)
    assert entity is not None
    assert entity.get("motion.detected") is True
    assert entity.get("location.zone") == "hallway"
    observations = world.history(device.entity_id)
    assert all(item.execution_id == execution_id for item in observations)


async def test_duplicate_event_does_not_duplicate_world_evidence() -> None:
    store = InMemoryDeviceStore()
    device = Device(device_id="device_dup", type="esp32")
    await store.add_device(device)
    world = WorldModel()
    gateway = WorldAwareDeviceGateway(store, ExecutionEngine(), world=world)
    ctx = _context(device)

    message = EdgeMessage(
        type=EdgeMessageType.EVENT,
        message_id="msg-duplicate",
        device_id=device.device_id,
        payload={
            "event_name": "temperature.changed",
            "event_payload": {
                "observations": [{"property": "temperature", "value": 30}]
            },
        },
    )
    await gateway.handle_event(message, ctx)
    await gateway.handle_event(message, ctx)

    assert len(world.history(device.entity_id, "temperature")) == 1


async def test_effect_ack_only_changes_world_when_evidence_is_reported() -> None:
    store = InMemoryDeviceStore()
    device = Device(
        device_id="device_actuator",
        type="esp32",
        capabilities=["relay.control"],
    )
    await store.add_device(device)
    world = WorldModel()
    gateway = WorldAwareDeviceGateway(store, ExecutionEngine(), world=world)
    await gateway.submit_effect(
        effect_id="effect-1",
        execution_id="exec-1",
        device_id=device.device_id,
        capability="relay.control",
        payload={"relay": True},
    )

    no_evidence = EdgeMessage(
        type=EdgeMessageType.EFFECT_ACK,
        message_id="msg-ack-1",
        device_id=device.device_id,
        payload={"effect_id": "effect-1", "execution_id": "exec-1", "status": "completed"},
    )
    await gateway.handle_effect_ack(no_evidence, _context(device))
    entity = world.entity(device.entity_id)
    assert entity is not None
    assert world.history(device.entity_id) == []

    with_evidence = EdgeMessage(
        type=EdgeMessageType.EFFECT_ACK,
        message_id="msg-ack-2",
        device_id=device.device_id,
        payload={
            "effect_id": "effect-1",
            "execution_id": "exec-1",
            "status": "completed",
            "observed_state": {"relay": True},
        },
    )
    await gateway.handle_effect_ack(with_evidence, _context(device))
    assert world.entity(device.entity_id).get("relay") is True
    observation = world.history(device.entity_id, "relay")[-1]
    assert observation.execution_id == "exec-1"
