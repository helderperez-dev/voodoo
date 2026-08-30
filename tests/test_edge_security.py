"""Edge security & adversarial tests — Sprint 23.1 Phase 7.

Covers authentication enforcement, credential validation, device isolation,
enrollment security, and protocol-level adversarial scenarios (EDGE §18,
§46–48).
"""

from __future__ import annotations

import pytest

from voodoo.edge.auth import consume_enrollment, create_enrollment
from voodoo.edge.errors import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    DeviceIdMismatchError,
    DeviceRevokedError,
    InvalidStateVersionError,
)
from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import DeviceStatus
from voodoo.edge.protocol import EdgeMessageType, make_message
from voodoo.edge.store import InMemoryDeviceStore
from voodoo.runtime.engine import ExecutionEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_gateway() -> tuple[DeviceGateway, InMemoryDeviceStore]:
    store = InMemoryDeviceStore()
    engine = ExecutionEngine()
    return DeviceGateway(store, engine), store


async def _enrolled_device(
    gateway: DeviceGateway,
    *,
    device_type: str = "esp32",
    capabilities: list[str] | None = None,
) -> tuple[str, str]:
    """Create an enrollment and consume it to get a device + credential."""
    caps = capabilities or ["relay.fan.control"]
    raw_key = await create_enrollment(
        gateway.store,
        device_type=device_type,
        capabilities=caps,
    )
    device, credential = await consume_enrollment(gateway.store, raw_key)
    return device.device_id, credential


# ---------------------------------------------------------------------------
# Authentication enforcement — unauthenticated requests rejected
# ---------------------------------------------------------------------------


class TestAuthenticationEnforcement:
    """Every non-AUTH message requires an authenticated context."""

    async def test_event_without_auth_rejected(self):
        gateway, _ = await _make_gateway()
        device_id, _ = await _enrolled_device(gateway)
        msg = make_message(
            EdgeMessageType.EVENT,
            device_id=device_id,
            payload={"event_name": "sensor.read", "event_payload": {}},
        ).model_dump()
        with pytest.raises(AuthenticationFailedError):
            await gateway.handle_message(msg)

    async def test_state_sync_without_auth_rejected(self):
        gateway, _ = await _make_gateway()
        device_id, _ = await _enrolled_device(gateway)
        msg = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id,
            payload={"state": {"temp": 20}, "state_version": 1},
        ).model_dump()
        with pytest.raises(AuthenticationFailedError):
            await gateway.handle_message(msg)

    async def test_heartbeat_without_auth_rejected(self):
        gateway, _ = await _make_gateway()
        device_id, _ = await _enrolled_device(gateway)
        msg = make_message(
            EdgeMessageType.HEARTBEAT,
            device_id=device_id,
            payload={},
        ).model_dump()
        with pytest.raises(AuthenticationFailedError):
            await gateway.handle_message(msg)

    async def test_effect_ack_without_auth_rejected(self):
        gateway, _ = await _make_gateway()
        device_id, _ = await _enrolled_device(gateway)
        msg = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device_id,
            payload={"effect_id": "fx_1", "status": "completed"},
        ).model_dump()
        with pytest.raises(AuthenticationFailedError):
            await gateway.handle_message(msg)


# ---------------------------------------------------------------------------
# Credential validation
# ---------------------------------------------------------------------------


class TestCredentialValidation:
    """Invalid, revoked, and wrong-device credentials rejected."""

    async def test_invalid_credential_rejected(self):
        gateway, _ = await _make_gateway()
        await _enrolled_device(gateway)
        with pytest.raises(AuthenticationFailedError):
            await gateway.connect("cred_invalid_nonexistent")

    async def test_revoked_device_credential_rejected(self):
        gateway, store = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        # Revoke the device
        await store.update_device_status(device_id, DeviceStatus.REVOKED)
        with pytest.raises(DeviceRevokedError):
            await gateway.connect(credential)

    async def test_credential_for_wrong_device_rejected(self):
        gateway, _ = await _make_gateway()
        device_id1, _ = await _enrolled_device(gateway, device_type="esp32")
        device_id2, credential2 = await _enrolled_device(gateway, device_type="rpi")
        # Try to use device2's credential claiming to be device1
        with pytest.raises((AuthenticationFailedError, AuthorizationFailedError)):
            ctx, _ = await gateway.connect(credential2, claimed_device_id=device_id1)


# ---------------------------------------------------------------------------
# Device identity isolation
# ---------------------------------------------------------------------------


class TestDeviceIsolation:
    """Device A cannot impersonate or access Device B."""

    async def test_message_with_wrong_device_id_rejected(self):
        gateway, _ = await _make_gateway()
        device_id_a, credential_a = await _enrolled_device(gateway)
        device_id_b, _ = await _enrolled_device(gateway)
        ctx_a, _ = await gateway.connect(credential_a)
        # Device A sends event with Device B's ID
        msg = make_message(
            EdgeMessageType.EVENT,
            device_id=device_id_b,
            payload={"event_name": "sensor.read", "event_payload": {}},
        ).model_dump()
        with pytest.raises(DeviceIdMismatchError):
            await gateway.handle_message(msg, context=ctx_a)

    async def test_state_sync_with_wrong_device_id_rejected(self):
        gateway, _ = await _make_gateway()
        device_id_a, credential_a = await _enrolled_device(gateway)
        device_id_b, _ = await _enrolled_device(gateway)
        ctx_a, _ = await gateway.connect(credential_a)
        msg = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id_b,
            payload={"state": {"temp": 99}, "state_version": 1},
        ).model_dump()
        with pytest.raises(DeviceIdMismatchError):
            await gateway.handle_message(msg, context=ctx_a)

    async def test_heartbeat_with_wrong_device_id_rejected(self):
        gateway, _ = await _make_gateway()
        device_id_a, credential_a = await _enrolled_device(gateway)
        device_id_b, _ = await _enrolled_device(gateway)
        ctx_a, _ = await gateway.connect(credential_a)
        msg = make_message(
            EdgeMessageType.HEARTBEAT,
            device_id=device_id_b,
            payload={},
        ).model_dump()
        with pytest.raises(DeviceIdMismatchError):
            await gateway.handle_message(msg, context=ctx_a)


# ---------------------------------------------------------------------------
# Enrollment security
# ---------------------------------------------------------------------------


class TestEnrollmentSecurity:
    """Enrollment creation protected by admin token."""

    async def test_enrollment_requires_admin_token_when_configured(self):
        """When enrollment_auth_required=True, missing token → 401."""
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from voodoo.config import VoodooConfig
        from voodoo.edge.http import build_edge_routes

        config = VoodooConfig()
        config.edge.enabled = True
        config.edge.enrollment_auth_required = True
        config.edge.enrollment_admin_token = "secret-admin-token"
        store = InMemoryDeviceStore()
        engine = ExecutionEngine()
        gateway = DeviceGateway(store, engine, config=config)
        app = Starlette(routes=build_edge_routes(gateway))
        with TestClient(app) as client:
            resp = client.post(
                "/v1/edge/enrollments",
                json={"device_type": "esp32", "capabilities": ["sensor.temp"]},
            )
            assert resp.status_code == 401

    async def test_enrollment_wrong_token_rejected(self):
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from voodoo.config import VoodooConfig
        from voodoo.edge.http import build_edge_routes

        config = VoodooConfig()
        config.edge.enabled = True
        config.edge.enrollment_auth_required = True
        config.edge.enrollment_admin_token = "secret-admin-token"
        store = InMemoryDeviceStore()
        engine = ExecutionEngine()
        gateway = DeviceGateway(store, engine, config=config)
        app = Starlette(routes=build_edge_routes(gateway))
        with TestClient(app) as client:
            resp = client.post(
                "/v1/edge/enrollments",
                json={"device_type": "esp32", "capabilities": ["sensor.temp"]},
                headers={"X-Admin-Token": "wrong-token"},
            )
            assert resp.status_code == 401

    async def test_enrollment_accepted_with_valid_token(self):
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from voodoo.config import VoodooConfig
        from voodoo.edge.http import build_edge_routes

        config = VoodooConfig()
        config.edge.enabled = True
        config.edge.enrollment_auth_required = True
        config.edge.enrollment_admin_token = "secret-admin-token"
        store = InMemoryDeviceStore()
        engine = ExecutionEngine()
        gateway = DeviceGateway(store, engine, config=config)
        app = Starlette(routes=build_edge_routes(gateway))
        with TestClient(app) as client:
            resp = client.post(
                "/v1/edge/enrollments",
                json={"device_type": "esp32", "capabilities": ["sensor.temp"]},
                headers={"X-Admin-Token": "secret-admin-token"},
            )
            assert resp.status_code == 200
            assert "enrollment_key" in resp.json()

    async def test_enrollment_open_when_auth_disabled(self):
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from voodoo.config import VoodooConfig
        from voodoo.edge.http import build_edge_routes

        config = VoodooConfig()
        config.edge.enabled = True
        config.edge.enrollment_auth_required = False
        store = InMemoryDeviceStore()
        engine = ExecutionEngine()
        gateway = DeviceGateway(store, engine, config=config)
        app = Starlette(routes=build_edge_routes(gateway))
        with TestClient(app) as client:
            resp = client.post(
                "/v1/edge/enrollments",
                json={"device_type": "esp32", "capabilities": ["sensor.temp"]},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Idempotency & replay
# ---------------------------------------------------------------------------


class TestIdempotencySecurity:
    """Duplicate messages replay original response, not generic 'duplicate'."""

    async def test_duplicate_event_replays_original_response(self):
        gateway, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, _ = await gateway.connect(credential)
        msg = make_message(
            EdgeMessageType.EVENT,
            device_id=device_id,
            payload={
                "event_name": "motion.detected",
                "event_payload": {},
                "message_id": "msg_idem_1",
            },
        ).model_dump()
        first = await gateway.handle_message(msg, context=ctx)
        second = await gateway.handle_message(msg, context=ctx)
        assert first.payload["status"] == "accepted"
        assert second.payload["status"] == "accepted"
        assert second.payload["execution_id"] == first.payload["execution_id"]


# ---------------------------------------------------------------------------
# State reconciliation
# ---------------------------------------------------------------------------


class TestStateReconciliationSecurity:
    """Stale state rejected with current version info."""

    async def test_stale_state_rejected_with_current_version(self):
        gateway, store = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, _ = await gateway.connect(credential)
        # Set state at version 5
        msg1 = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id,
            payload={"state": {"temp": 20}, "state_version": 5},
        ).model_dump()
        await gateway.handle_message(msg1, context=ctx)
        # Try stale version 3
        msg2 = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id,
            payload={"state": {"temp": 30}, "state_version": 3},
        ).model_dump()
        with pytest.raises(InvalidStateVersionError) as exc_info:
            await gateway.handle_message(msg2, context=ctx)
        assert exc_info.value.detail["current"] == 5
        assert exc_info.value.detail["incoming"] == 3


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------


class TestSecretRedaction:
    """Credentials never appear in events, errors, or mesh payloads."""

    async def test_credential_not_in_mesh_event_payload(self):
        from voodoo.mesh import mesh

        captured: list[tuple[str, dict]] = []
        original = mesh.broadcast

        async def spy(
            event: str, payload: dict | None = None, **kwargs: object
        ) -> None:
            captured.append((event, dict(payload or {})))

        mesh.broadcast = spy  # type: ignore[method-assign]
        try:
            gateway, _ = await _make_gateway()
            device_id, credential = await _enrolled_device(gateway)
            ctx, _ = await gateway.connect(credential)
            msg = make_message(
                EdgeMessageType.EVENT,
                device_id=device_id,
                payload={
                    "event_name": "sensor.read",
                    "event_payload": {},
                },
            ).model_dump()
            await gateway.handle_message(msg, context=ctx)
        finally:
            mesh.broadcast = original  # type: ignore[method-assign]

        # Credential must not appear anywhere in captured events
        all_text = str(captured)
        assert credential not in all_text

    async def test_credential_not_in_error_detail(self):
        gateway, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, _ = await gateway.connect(credential)
        # Trigger a DeviceIdMismatchError
        other_id = "device_other_999"
        msg = make_message(
            EdgeMessageType.EVENT,
            device_id=other_id,
            payload={"event_name": "sensor.read", "event_payload": {}},
        ).model_dump()
        with pytest.raises(DeviceIdMismatchError) as exc_info:
            await gateway.handle_message(msg, context=ctx)
        assert credential not in str(exc_info.value.detail)
