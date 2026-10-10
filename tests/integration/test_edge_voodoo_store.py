"""Sprint 28 Edge persistence acceptance over application.vstore."""

from __future__ import annotations

import json

import pytest

from voodoo.edge import (
    AuthenticatedDeviceContext,
    Device,
    DeviceGateway,
    EdgeMessageType,
    EffectAckStatus,
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
    raw = runtime.provider.native.get_record(
        b"runtime.edge_devices", b"device-1"
    )
    assert raw is not None
    assert json.loads(bytes(raw[1]))["_schema_version"] == 1
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


@pytest.mark.asyncio
async def test_edge_replay_records_use_native_collections(tmp_path) -> None:
    path = tmp_path / "edge-replay.vstore"
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        store = VoodooStoreDeviceStore(runtime)
        await store.mark_message_seen("message-1")
        await store.store_response("message-1", '{"status":"accepted"}')
        native = runtime.provider.native
        assert native.get_record(b"runtime.edge_seen", b"message-1")[1] == b"1"
        assert native.get_record(b"runtime.edge_responses", b"message-1")[1] == (
            b'{"status":"accepted"}'
        )
        assert native.get(b"runtime:edge:seen:message-1") is None
        assert native.get(b"runtime:edge:response:message-1") is None
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


@pytest.mark.asyncio
async def test_edge_future_schema_fails_closed_on_hydration(tmp_path) -> None:
    path = tmp_path / "edge-future.vstore"
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        store = VoodooStoreDeviceStore(runtime)
        store._native.upsert_record(
            b"runtime.edge_devices",
            b"future-device",
            json.dumps(
                {
                    "_schema_version": 99,
                    "device_id": "future-device",
                    "capabilities": [],
                }
            ).encode("utf-8"),
        )
        with pytest.raises(ValueError, match="unsupported edge schema version"):
            VoodooStoreDeviceStore(runtime)
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


@pytest.mark.asyncio
async def test_edge_reads_legacy_unversioned_device_record(tmp_path) -> None:
    path = tmp_path / "edge-legacy.vstore"
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        first = VoodooStoreDeviceStore(runtime)
        device = Device(device_id="legacy-device", capabilities=["relay.control"])
        await first.register_device(device)
        raw = device.to_dict()
        raw.pop("_schema_version", None)
        runtime.provider.native.upsert_record(
            b"runtime.edge_devices", b"legacy-device", json.dumps(raw).encode()
        )

        restored = VoodooStoreDeviceStore(runtime)
        loaded = await restored.get_device("legacy-device")
        assert loaded is not None
        assert loaded.capabilities == ["relay.control"]
        await restored.register_device(loaded)
        assert runtime.provider.native.get(b"runtime:edge:device:legacy-device") is None
    finally:
        bind_active_runtime_store(None)
        runtime.stop()
