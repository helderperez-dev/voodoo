from __future__ import annotations

from voodoo.runtime.store import (
    RuntimeStore,
    StoreConfig,
    bind_active_runtime_store,
)
from voodoo.storage.events.store import VoodooStoreEventBus


def test_store_event_bus_persists_notifies_and_replays_in_order(tmp_path) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "events.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    bus = VoodooStoreEventBus()

    delivered: list[dict] = []
    replayed: list[dict] = []
    bus.subscribe("patient.updated", delivered.append)

    try:
        first = bus.publish("patient.updated", {"id": 1, "status": "ready"})
        second = bus.publish("patient.updated", {"id": 2, "status": "done"})

        assert [event["event_id"] for event in delivered] == [
            first["event_id"],
            second["event_id"],
        ]
        assert bus.replay("patient.updated", replayed.append) == 2
        assert [event["event_id"] for event in replayed] == [
            first["event_id"],
            second["event_id"],
        ]
        assert [event["payload"]["id"] for event in replayed] == [1, 2]

        capabilities = bus.capabilities()
        assert capabilities.provider == "voodoo"
        assert capabilities.durable is True
        assert capabilities.replay is True
        assert capabilities.ordering is True
    finally:
        bus.close()
        bind_active_runtime_store(None)
        runtime.stop()


def test_store_event_bus_isolated_by_event_type(tmp_path) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "events.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    bus = VoodooStoreEventBus()

    replayed: list[dict] = []
    try:
        bus.publish("alpha", {"value": 1})
        bus.publish("beta", {"value": 2})
        bus.publish("alpha", {"value": 3})

        assert bus.replay("alpha", replayed.append) == 2
        assert [event["payload"]["value"] for event in replayed] == [1, 3]
    finally:
        bus.close()
        bind_active_runtime_store(None)
        runtime.stop()
