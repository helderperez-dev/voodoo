"""Tests for Mesh + EventBus integration (Sprint 7)."""

from __future__ import annotations

import asyncio

import pytest

from voodoo.mesh.event_bus import EventBusAwareMesh
from voodoo.storage.events.local import LocalEventBus
from voodoo.storage.events.sqlite import SQLiteEventBus


@pytest.mark.asyncio
async def test_mesh_with_local_bus() -> None:
    mesh = EventBusAwareMesh(LocalEventBus())
    received = []

    @mesh.on("test.event")
    async def handler(payload):
        received.append(payload)

    await mesh.emit("test.event", {"key": "value"})
    await asyncio.sleep(0.01)
    assert received == [{"key": "value"}]


@pytest.mark.asyncio
async def test_mesh_with_sqlite_bus(tmp_path) -> None:
    bus = SQLiteEventBus(tmp_path / "events.db")
    mesh = EventBusAwareMesh(bus)
    received = []

    @mesh.on("test.sqlite")
    async def handler(payload):
        received.append(payload)

    await mesh.emit("test.sqlite", {"data": "hello"})
    await asyncio.sleep(0.01)
    assert received == [{"data": "hello"}]
    bus.close()


@pytest.mark.asyncio
async def test_mesh_replay_after_restart(tmp_path) -> None:
    path = tmp_path / "events.db"

    # First run: publish events
    bus1 = SQLiteEventBus(path)
    mesh1 = EventBusAwareMesh(bus1)
    await mesh1.emit("test.durable", {"n": 1})
    await mesh1.emit("test.durable", {"n": 2})
    bus1.close()

    # Second run: replay to a late-registered handler
    bus2 = SQLiteEventBus(path)
    mesh2 = EventBusAwareMesh(bus2)
    received = []

    @mesh2.on("test.durable")
    def handler(payload):
        received.append(payload)

    count = mesh2.replay("test.durable")
    assert count == 2
    assert received == [{"n": 1}, {"n": 2}]
    bus2.close()
