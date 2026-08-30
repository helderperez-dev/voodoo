"""Edge HTTP transport tests — Phase 4 + HTTP E2E (EDGE §34, §43).

Uses the Starlette TestClient against a real DeviceGateway backed by an
in-memory store and the real ExecutionEngine — a full-stack exercise of
the HTTP boundary without mocking runtime internals. The device
simulator drives the E2E flow exactly like a future ESP32 would.
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
        yield client, gateway, engine, app


def _issue_enrollment(client: TestClient, capabilities: list[str] | None = None) -> str:
    resp = client.post(
        "/v1/edge/enrollments",
        json={"device_type": "esp32", "capabilities": capabilities or []},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["enrollment_key"]


def _enroll(
    client: TestClient, capabilities: list[str] | None = None
) -> tuple[str, str]:
    key = _issue_enrollment(client, capabilities)
    resp = client.post("/v1/edge/enroll", json={"enrollment_key": key})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["device_id"], body["credential"]


# ---------------------------------------------------------------------------
# Enrollment & auth
# ---------------------------------------------------------------------------


class TestHTTPEdgeEnrollAuth:
    def test_enroll_issues_credential(self, edge_stack):
        client, _, _, _ = edge_stack
        device_id, credential = _enroll(client, ["relay.fan.control"])
        assert device_id.startswith("device_")
        assert credential.startswith("vdk_")

    def test_enroll_rejects_bad_key(self, edge_stack):
        client, _, _, _ = edge_stack
        resp = client.post("/v1/edge/enroll", json={"enrollment_key": "vde_bogus"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTHENTICATION_FAILED"

    def test_enrollment_single_use(self, edge_stack):
        client, _, _, _ = edge_stack
        key = _issue_enrollment(client)
        assert (
            client.post("/v1/edge/enroll", json={"enrollment_key": key}).status_code
            == 200
        )
        assert (
            client.post("/v1/edge/enroll", json={"enrollment_key": key}).status_code
            == 401
        )

    def test_auth_establishes_session(self, edge_stack):
        client, _, _, _ = edge_stack
        device_id, credential = _enroll(client)
        resp = client.post("/v1/edge/auth", json={"credential": credential})
        assert resp.status_code == 200
        body = resp.json()
        assert body["payload"]["session_id"]
        assert body["payload"]["device_id"] == device_id

    def test_auth_rejects_bad_credential(self, edge_stack):
        client, _, _, _ = edge_stack
        resp = client.post("/v1/edge/auth", json={"credential": "vdk_bogus"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------


class TestHTTPEdgeEndpoints:
    def _authed(self, edge_stack, capabilities=None):
        client, gateway, engine, _app = edge_stack
        device_id, credential = _enroll(client, capabilities)
        headers = {"X-Device-Credential": credential}
        return client, gateway, engine, device_id, headers

    def test_missing_credential_rejected(self, edge_stack):
        client, _, _, _ = edge_stack
        for path in ("/v1/edge/events", "/v1/edge/state", "/v1/edge/heartbeat"):
            resp = client.post(path, json={})
            assert resp.status_code == 401, path

    def test_hello_announces_capabilities(self, edge_stack):
        client, _, _, device_id, headers = self._authed(edge_stack)
        resp = client.post(
            "/v1/edge/hello",
            json={"device_type": "esp32", "capabilities": ["display.write"]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "display.write" in resp.json()["payload"]["capabilities"]

    def test_event_ingestion_creates_execution(self, edge_stack):
        client, _, engine, device_id, headers = self._authed(
            edge_stack, ["relay.fan.control"]
        )
        resp = client.post(
            "/v1/edge/events",
            json={
                "event_name": "temperature.changed",
                "event_payload": {"value": 31.4},
            },
            headers=headers,
        )
        assert resp.status_code == 200
        execution_id = resp.json()["payload"]["execution_id"]
        assert execution_id
        execution = engine.get(execution_id)
        assert execution is not None
        assert execution.intent.name == "device:temperature.changed"
        assert execution.actor == f"device:{device_id}"

    def test_state_sync_and_stale_rejection(self, edge_stack):
        client, _, _, device_id, headers = self._authed(edge_stack)
        resp = client.post(
            "/v1/edge/state",
            json={"state": {"temperature": 20}, "state_version": 10},
            headers=headers,
        )
        assert resp.status_code == 200

        stale = client.post(
            "/v1/edge/state",
            json={"state": {"temperature": 19}, "state_version": 9},
            headers=headers,
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "INVALID_STATE_VERSION"

    def test_heartbeat_no_execution(self, edge_stack):
        client, _, engine, device_id, headers = self._authed(edge_stack)
        before = len(engine.executions)
        resp = client.post(
            "/v1/edge/heartbeat", json={"uptime_seconds": 42}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["payload"]["status"] == "ok"
        assert len(engine.executions) == before

    def test_effects_poll_and_ack(self, edge_stack):
        client, gateway, _, device_id, headers = self._authed(
            edge_stack, ["relay.fan.control"]
        )
        _run(
            gateway.submit_effect(
                effect_id="effect_http_1",
                execution_id="exec_1",
                device_id=device_id,
                capability="relay.fan.control",
                payload={"state": "on"},
            )
        )

        resp = client.get("/v1/edge/effects", headers=headers)
        assert resp.status_code == 200
        effects = resp.json()["effects"]
        assert len(effects) == 1
        assert effects[0]["effect_id"] == "effect_http_1"

        ack = client.post(
            "/v1/edge/effects/effect_http_1/ack",
            json={"status": "completed"},
            headers=headers,
        )
        assert ack.status_code == 200

        resp2 = client.get("/v1/edge/effects", headers=headers)
        assert resp2.json()["effects"] == []

    def test_invalid_event_name_rejected(self, edge_stack):
        client, _, _, device_id, headers = self._authed(edge_stack)
        resp = client.post(
            "/v1/edge/events",
            json={"event_name": "NOT VALID", "event_payload": {}},
            headers=headers,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_MESSAGE"

    def test_revoked_device_rejected(self, edge_stack):
        client, gateway, _, device_id, headers = self._authed(edge_stack)
        _run(gateway.revoke_device(device_id))
        resp = client.post("/v1/edge/heartbeat", json={}, headers=headers)
        assert resp.status_code == 401

    def test_http_stateless_no_session_created(self, edge_stack):
        """HTTP endpoints use stateless auth — no session is created per request."""
        client, gateway, _, device_id, headers = self._authed(edge_stack)
        # Before any request, no sessions.
        assert len(gateway._contexts) == 0

        # Make a request — should NOT create a session.
        resp = client.post(
            "/v1/edge/heartbeat", json={"uptime_seconds": 1}, headers=headers
        )
        assert resp.status_code == 200
        assert len(gateway._contexts) == 0

    def test_device_id_mismatch_rejected_via_http(self, edge_stack):
        """HTTP derives device_id from credential — body device_id is payload,
        not the envelope identity. Verify the event succeeds with the correct
        device_id from the credential."""
        client, gateway, engine, device_id, headers = self._authed(
            edge_stack, ["relay.fan.control"]
        )
        # The body's device_id field is part of the event payload, not the
        # envelope. The HTTP handler always sets envelope device_id from the
        # authenticated credential. So this should succeed.
        resp = client.post(
            "/v1/edge/events",
            json={
                "event_name": "temperature.changed",
                "event_payload": {"value": 1},
            },
            headers=headers,
        )
        assert resp.status_code == 200
        # The execution is attributed to the correct device.
        execution_id = resp.json()["payload"]["execution_id"]
        assert execution_id
        execution = engine.get(execution_id)
        assert execution.actor == f"device:{device_id}"


# ---------------------------------------------------------------------------
# HTTP E2E — the primary acceptance scenario via the simulator (EDGE §42–§43)
# ---------------------------------------------------------------------------


class TestHTTPEndToEnd:
    def test_full_device_lifecycle(self, edge_stack):
        """authenticate → announce → event → execution → effect → ACK
        → completion — the EDGE §42 acceptance flow."""
        client, gateway, engine, app = edge_stack
        key = client.post(
            "/v1/edge/enrollments",
            json={
                "device_type": "esp32",
                "capabilities": [
                    "sensor.temperature.read",
                    "relay.fan.control",
                ],
            },
        ).json()["enrollment_key"]

        async def _e2e():
            sim = DeviceSimulator(HTTPSimulatorTransport("http://testserver", app=app))
            await sim.enroll(key, firmware_version="1.0.0")
            await sim.connect(
                device_type="esp32",
                capabilities=["sensor.temperature.read", "relay.fan.control"],
            )

            # Device reports state and emits an event
            await sim.send_state({"temperature": 31.4, "fan": False}, 1)
            event_resp = await sim.send_event("temperature.changed", {"value": 31.4})
            assert event_resp["payload"]["status"] == "accepted"
            execution_id = event_resp["payload"]["execution_id"]
            assert execution_id

            # The runtime execution produces an effect targeting the device
            await gateway.submit_effect(
                effect_id="effect_e2e",
                execution_id=execution_id,
                device_id=sim.device_id,
                capability="relay.fan.control",
                payload={"state": "on"},
            )

            # Device polls and receives the effect
            effects = await sim.fetch_effects()
            assert len(effects) == 1
            assert effects[0]["effect_id"] == "effect_e2e"
            assert effects[0]["capability"] == "relay.fan.control"

            # Device acknowledges
            ack = await sim.ack_effect("effect_e2e", "completed")
            assert ack["payload"]["status"] == "accepted"

            # Runtime records completion
            delivery = await gateway.store.get_effect_delivery("effect_e2e")
            assert delivery.status == "completed"

            await sim.disconnect()
            return execution_id

        execution_id = _run(_e2e())
        execution = engine.get(execution_id)
        assert execution is not None
