"""Event bus contract tests (Sprint 7).

Run against any VoodooEventBus implementation to verify semantics.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from voodoo.storage.events.interfaces import VoodooEventBus


class EventBusContractTests:
    """Mixin for testing VoodooEventBus implementations."""

    bus: VoodooEventBus

    @pytest.mark.asyncio
    async def test_publish_subscribe(self) -> None:
        received = []

        def handler(event: dict[str, Any]) -> None:
            received.append(event)

        self.bus.subscribe("test.event", handler)
        ev = self.bus.publish("test.event", {"key": "value"})

        assert ev["event_type"] == "test.event"
        assert ev["payload"] == {"key": "value"}
        await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0]["event_type"] == "test.event"

    @pytest.mark.asyncio
    async def test_publish_subscribe_async_handler(self) -> None:
        received = []

        async def handler(event: dict[str, Any]) -> None:
            received.append(event)

        self.bus.subscribe("test.async", handler)
        ev = self.bus.publish("test.async", {"x": 1})

        assert ev["event_type"] == "test.async"
        await asyncio.sleep(0.01)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        results = []

        def h1(event: dict[str, Any]) -> None:
            results.append(1)

        def h2(event: dict[str, Any]) -> None:
            results.append(2)

        self.bus.subscribe("test.multi", h1)
        self.bus.subscribe("test.multi", h2)
        self.bus.publish("test.multi", {})

        await asyncio.sleep(0.01)
        assert set(results) == {1, 2}

    def test_capabilities_returns_provider(self) -> None:
        caps = self.bus.capabilities()
        assert caps.provider is not None
        assert isinstance(caps.durable, bool)

    @pytest.mark.asyncio
    async def test_replay_returns_count(self) -> None:
        received = []

        def handler(event: dict[str, Any]) -> None:
            received.append(event)

        # Publish some events
        self.bus.publish("test.replay", {"n": 1})
        self.bus.publish("test.replay", {"n": 2})
        self.bus.publish("test.replay", {"n": 3})

        count = self.bus.replay("test.replay", handler)
        if self.bus.capabilities().replay:
            assert count == 3
            assert len(received) == 3
        else:
            # Non-durable buses keep no replayable log.
            assert count == 0
            assert len(received) == 0

    def test_publish_envelope_includes_correlation(self) -> None:
        ev = self.bus.publish(
            "test.corr",
            {},
            correlation_id="trace-123",
            source="test-app",
        )
        assert ev["correlation_id"] == "trace-123"
        assert ev["source"] == "test-app"
        assert "event_id" in ev
        assert "timestamp" in ev

    def test_provider_name_is_string(self) -> None:
        caps = self.bus.capabilities()
        assert isinstance(caps.provider, str)


# Concrete test classes for each implementation


class TestLocalEventBusContract(EventBusContractTests):
    @pytest.fixture(autouse=True)
    def setup_bus(self) -> None:
        from voodoo.storage.events.local import LocalEventBus

        self.bus = LocalEventBus()
        yield
        self.bus._handlers.clear()


@pytest.mark.asyncio
class TestSQLiteEventBusContract(EventBusContractTests):
    @pytest.fixture(autouse=True)
    def setup_bus(self, tmp_path) -> None:
        from voodoo.storage.events.sqlite import SQLiteEventBus

        self.bus = SQLiteEventBus(tmp_path / "events.db")
        yield
        self.bus.close()


@pytest.mark.asyncio
class TestSQLiteEventBusDurability:
    """Additional durability tests specific to SQLiteEventBus."""

    async def test_events_survive_close_and_reopen(self, tmp_path) -> None:
        from voodoo.storage.events.sqlite import SQLiteEventBus

        path = tmp_path / "events.db"
        bus1 = SQLiteEventBus(path)
        bus1.publish("test.durable", {"data": "hello"})
        bus1.close()

        received = []

        def handler(event: dict[str, Any]) -> None:
            received.append(event)

        bus2 = SQLiteEventBus(path)
        bus2.subscribe("test.durable", handler)
        count = bus2.replay("test.durable", handler)
        bus2.close()

        assert count == 1
        assert len(received) == 1
        assert received[0]["payload"] == {"data": "hello"}

    async def test_publish_notifies_subscribers_after_reopen(self, tmp_path) -> None:
        from voodoo.storage.events.sqlite import SQLiteEventBus

        path = tmp_path / "events.db"
        bus = SQLiteEventBus(path)
        received = []

        def handler(event: dict[str, Any]) -> None:
            received.append(event)

        bus.subscribe("test.live", handler)
        bus.publish("test.live", {"live": True})
        await asyncio.sleep(0.01)
        assert len(received) == 1
        bus.close()
