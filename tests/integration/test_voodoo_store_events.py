from __future__ import annotations

import json
import logging

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


def test_store_event_subscriber_failure_is_diagnostic_and_non_fatal(
    tmp_path, caplog
) -> None:
    """Subscriber failures do not lose the persisted event or break publish."""
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "events.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    bus = VoodooStoreEventBus()

    def broken_subscriber(_event: dict) -> None:
        raise RuntimeError("password=super-secret")

    bus.subscribe("patient.updated", broken_subscriber)
    try:
        with caplog.at_level(logging.WARNING, logger="voodoo.events"):
            event = bus.publish("patient.updated", {"id": 3})

        assert event["event_type"] == "patient.updated"
        assert "event subscriber failed" in caplog.text
        assert "super-secret" not in caplog.text
        replayed: list[dict] = []
        assert bus.replay("patient.updated", replayed.append) == 1
        assert replayed[0]["event_id"] == event["event_id"]
    finally:
        bus.close()
        bind_active_runtime_store(None)
        runtime.stop()


def test_store_event_replay_rejects_future_schema(tmp_path, caplog) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "future-events.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    bus = VoodooStoreEventBus()
    try:
        topic = bus._topic("future.event")
        runtime.provider.native.publish_topic(
            topic,
            json.dumps(
                {
                    "event_id": "future",
                    "event_type": "future.event",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "source": "fixture",
                    "payload": {},
                    "schema_version": 99,
                }
            ).encode(),
        )
        replayed: list[dict] = []
        with caplog.at_level(logging.WARNING, logger="voodoo.events"):
            assert bus.replay("future.event", replayed.append) == 0
        assert replayed == []
        assert "unsupported event schema" in caplog.text
    finally:
        bus.close()
        bind_active_runtime_store(None)
        runtime.stop()


def test_store_event_replay_accepts_legacy_unversioned_envelope(tmp_path) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "legacy-events.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    bus = VoodooStoreEventBus()
    try:
        runtime.provider.native.publish_topic(
            bus._topic("legacy.event"),
            json.dumps(
                {
                    "event_id": "legacy",
                    "event_type": "legacy.event",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "source": "fixture",
                    "payload": {"value": 1},
                }
            ).encode(),
        )
        replayed: list[dict] = []
        assert bus.replay("legacy.event", replayed.append) == 1
        assert replayed[0]["event_id"] == "legacy"
    finally:
        bus.close()
        bind_active_runtime_store(None)
        runtime.stop()
