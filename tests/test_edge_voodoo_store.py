"""Sprint 28 Edge persistence acceptance over application.vstore."""

from __future__ import annotations

import pytest

from voodoo.edge import (
    AuthenticatedDeviceContext,
    Device,
    DeviceGateway,
    EffectAckStatus,
    EdgeMessageType,
    VoodooStoreDeviceStore,
    make_message,
)
from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store


@pytest.mark.asyncio
async def test_edge_device_and_effect_survive_store_restart(tmp_path) -> None:
    path = tmp_path / "application.vstore"
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    store = VoodooStoreDeviceStore(runtime)
    gateway = DeviceGateway(store)
    device = Device(device_id="device-1", capabilities=["relay.control"])
    await store.register_device(device)
    await gateway.submit_effect(
        effect_id="effect-1",
        execution_id="exec-1",
        device_id=device.device_id,
        capability="relay.control",
        payload={"on": True},
    )
    runtime.stop()
    bind_active_runtime_store(None)

    reopened = RuntimeStore(StoreConfig(path=path))
    reopened.start()
    bind_active_runtime_store(reopened)
    try:
        restored_store = VoodooStoreDeviceStore(reopened)
        restored = await restored_store.get_device("device-1")
        delivery = await restored_store.get_effect_delivery("effect-1")
        assert restored is not None
        assert restored.capabilities == ["relay.control"]
        assert delivery is not None
        assert delivery.payload == {"on": True}
        assert delivery.status == "pending"
    finally:
        bind_active_runtime_store(None)
        reopened.stop()


@pytest.mark.asyncio
async def test_edge_closed_loop_ack_is_durable(tmp_path) -> None:
    path = tmp_path / "edge-loop.vstore"
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        store = VoodooStoreDeviceStore(runtime)
        gateway = DeviceGateway(store)
        device = Device(device_id="robot-1", capabilities=["robot.move"])
        await store.register_device(device)
        await gateway.submit_effect(
            effect_id="move-1",
            execution_id="exec-move-1",
            device_id=device.device_id,
            capability="robot.move",
            payload={"x": 1},
        )
        ctx = AuthenticatedDeviceContext(device_id=device.device_id)
        claimed = await gateway.pending_effects(device.device_id, ctx)
        assert [item.effect_id for item in claimed] == ["move-1"]

        ack = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device.device_id,
            payload={"effect_id": "move-1", "status": EffectAckStatus.COMPLETED.value},
        )
        await gateway.handle_effect_ack(ack, ctx)
        delivery = await store.get_effect_delivery("move-1")
        assert delivery is not None
        assert delivery.status == EffectAckStatus.COMPLETED.value
    finally:
        bind_active_runtime_store(None)
        runtime.stop()

    reopened = RuntimeStore(StoreConfig(path=path))
    reopened.start()
    bind_active_runtime_store(reopened)
    try:
        store = VoodooStoreDeviceStore(reopened)
        delivery = await store.get_effect_delivery("move-1")
        assert delivery is not None
        assert delivery.status == EffectAckStatus.COMPLETED.value
        assert delivery.execution_id == "exec-move-1"
    finally:
        bind_active_runtime_store(None)
        reopened.stop()
