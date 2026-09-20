"""Edge E2E integration tests — Sprint 23.1 Phase 8.

Full lifecycle tests exercising the Edge Protocol through the HTTP
transport with the DeviceSimulator — the same path a real ESP32 would
take (EDGE §41, §57).
"""

from __future__ import annotations

import asyncio

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.http import build_edge_routes
from voodoo.edge.simulator import DeviceSimulator, HTTPSimulatorTransport
from voodoo.edge.store import InMemoryDeviceStore
from voodoo.runtime.engine import ExecutionEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _run(coro):
    """Run a coroutine to completion inside a fresh loop."""
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def edge_stack():
    store = InMemoryDeviceStore()
    engine = ExecutionEngine()
    gateway = DeviceGateway(store, engine)
    app = Starlette(routes=build_edge_routes(gateway))
    with TestClient(app) as client:
        yield client, gateway, store, engine, app


def _issue_enrollment(client: TestClient, capabilities: list[str] | None = None) -> str:
    resp = client.post(
        "/v1/edge/enrollments",
        json={"device_type": "esp32", "capabilities": capabilities or []},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["enrollment_key"]


def _make_simulator(app) -> DeviceSimulator:
    transport = HTTPSimulatorTransport(app=app)
    return DeviceSimulator(transport)


# ---------------------------------------------------------------------------
# Full lifecycle: enroll → connect → event → execution → effect → ack
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """End-to-end: Device → AUTH → EVENT → Execution → Effect → ACK."""

    def test_event_creates_execution(self, edge_stack):
        client, gateway, store, engine, app = edge_stack
        key = _issue_enrollment(client, ["relay.fan.control"])
        sim = _make_simulator(app)
        _run(sim.enroll(key))
        _run(sim.connect())
        result = _run(sim.send_event("motion.detected", {"zone": "hallway"}))
        payload = result.get("payload", result)
        assert payload["status"] == "accepted"
        execution_id = payload.get("execution_id")
        assert execution_id
        execution = engine.get(execution_id)
        assert execution is not None
        assert execution.intent.name == "device:motion.detected"

    def test_heartbeat_no_execution(self, edge_stack):
        client, gateway, store, engine, app = edge_stack
        key = _issue_enrollment(client)
        sim = _make_simulator(app)
        _run(sim.enroll(key))
        _run(sim.connect())
        result = _run(sim.heartbeat())
        payload = result.get("payload", result)
        assert payload["status"] in ("accepted", "ok")
        # No execution created for heartbeat
        assert len([e for e in engine.recent(50) if "heartbeat" in e.intent.name]) == 0

    def test_state_sync_updates_device(self, edge_stack):
        client, gateway, store, engine, app = edge_stack
        key = _issue_enrollment(client)
        sim = _make_simulator(app)
        _run(sim.enroll(key))
        _run(sim.connect())
        result = _run(sim.send_state({"temp": 22.5, "humidity": 60}, 1))
        payload = result.get("payload", result)
        assert payload["status"] == "accepted"
        device = _run(store.get_device(sim.device_id))
        assert device.state["temp"] == 22.5


# ---------------------------------------------------------------------------
# Reconnect lifecycle
# ---------------------------------------------------------------------------


class TestReconnectE2E:
    """Reconnect after disconnect — same device, no duplicate."""

    def test_reconnect_preserves_device(self, edge_stack):
        client, gateway, store, engine, app = edge_stack
        key = _issue_enrollment(client, ["relay.fan.control"])
        sim = _make_simulator(app)
        _run(sim.enroll(key))
        device_id = sim.device_id
        _run(sim.connect())
        # Send an event to establish activity
        _run(sim.send_event("sensor.read", {"value": 1}))
        # Reconnect
        _run(sim.reconnect())
        assert sim.device_id == device_id
        assert sim.connected is True
        # Device still exists, no duplicate
        device = _run(store.get_device(device_id))
        assert device is not None

    def test_reconnect_can_send_events(self, edge_stack):
        client, gateway, store, engine, app = edge_stack
        key = _issue_enrollment(client, ["relay.fan.control"])
        sim = _make_simulator(app)
        _run(sim.enroll(key))
        _run(sim.connect())
        _run(sim.send_event("sensor.read", {"value": 1}))
        _run(sim.reconnect())
        result = _run(sim.send_event("sensor.read", {"value": 2}))
        payload = result.get("payload", result)
        assert payload["status"] == "accepted"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotencyE2E:
    """Duplicate events produce one execution, replay original response."""

    def test_duplicate_event_single_execution(self, edge_stack):
        client, gateway, store, engine, app = edge_stack
        key = _issue_enrollment(client, ["relay.fan.control"])
        sim = _make_simulator(app)
        _run(sim.enroll(key))
        _run(sim.connect())
        first, second = _run(
            sim.send_duplicate_event("motion.detected", {"zone": "hallway"})
        )
        first_payload = first.get("payload", first)
        second_payload = second.get("payload", second)
        assert first_payload["status"] == "accepted"
        assert second_payload["status"] == "accepted"
        assert second_payload["execution_id"] == first_payload["execution_id"]


# ---------------------------------------------------------------------------
# Stale state rejection
# ---------------------------------------------------------------------------


class TestStaleStateE2E:
    """Stale state version rejected with current version info."""

    def test_stale_state_rejected(self, edge_stack):
        client, gateway, store, engine, app = edge_stack
        key = _issue_enrollment(client)
        sim = _make_simulator(app)
        _run(sim.enroll(key))
        _run(sim.connect())
        # Set state at version 5
        _run(sim.send_state({"temp": 20}, 5))
        # Try stale version 3 — should fail
        import httpx

        with pytest.raises(httpx.HTTPStatusError):
            _run(sim.send_stale_state({"temp": 30}, 3))
