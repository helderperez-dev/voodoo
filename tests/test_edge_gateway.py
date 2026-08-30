"""Edge gateway tests — Phase 3: routing, auth, events, state, effects (Sprint 23)."""

from __future__ import annotations

import pytest

from voodoo.edge.auth import create_enrollment
from voodoo.edge.errors import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    EffectNotFoundError,
    InvalidStateVersionError,
)
from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import TransportKind
from voodoo.edge.protocol import EdgeMessageType, make_message
from voodoo.edge.store import InMemoryDeviceStore
from voodoo.runtime.engine import ExecutionEngine

# ---------------------------------------------------------------------------
# Fixture — enrolled device + authenticated gateway
# ---------------------------------------------------------------------------


async def _make_gateway() -> tuple[DeviceGateway, InMemoryDeviceStore, ExecutionEngine]:
    store = InMemoryDeviceStore()
    engine = ExecutionEngine()
    return DeviceGateway(store, engine), store, engine


async def _enrolled_device(gateway: DeviceGateway) -> tuple[str, str]:
    """Enroll via the gateway, returning (device_id, raw_credential)."""
    key = await create_enrollment(
        gateway.store, device_type="esp32", capabilities=["relay.fan.control"]
    )
    device, credential = await gateway.enroll(key)
    return device.device_id, credential


def _event_msg(device_id: str, event_name: str, message_id: str = "msg_1") -> dict:
    return make_message(
        EdgeMessageType.EVENT,
        device_id=device_id,
        payload={
            "event_name": event_name,
            "event_payload": {"value": 31.4},
            "message_id": message_id,
        },
    ).model_dump()


# ---------------------------------------------------------------------------
# AUTH routing
# ---------------------------------------------------------------------------


class TestGatewayAuth:
    async def test_auth_establishes_session(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)

        msg = make_message(
            EdgeMessageType.AUTH,
            device_id=device_id,
            payload={"device_id": device_id, "credential": credential},
        )
        response = await gateway.handle_message(
            msg.model_dump(), transport=TransportKind.HTTP
        )
        assert response.type is EdgeMessageType.AUTH
        session_id = response.payload["session_id"]
        assert session_id
        assert response.payload["device_id"] == device_id
        assert "relay.fan.control" in response.payload["capabilities"]

    async def test_auth_requires_context_for_other_messages(self):
        """A device cannot send events without authenticating first."""
        gateway, store, _ = await _make_gateway()
        device_id, _ = await _enrolled_device(gateway)

        msg = _event_msg(device_id, "temperature.changed")
        with pytest.raises(AuthenticationFailedError):
            await gateway.handle_message(msg)

    async def test_engine_executions_created_for_device_events(self):
        """Device events become real Executions in the engine (EDGE §21)."""
        gateway, store, engine = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)

        # AUTH first
        auth = make_message(
            EdgeMessageType.AUTH,
            device_id=device_id,
            payload={"credential": credential},
        )
        auth_response = await gateway.handle_message(auth.model_dump())
        assert auth_response.payload["session_id"]

        # EVENT via session
        ctx, _session = await gateway.connect(credential)
        msg = _event_msg(device_id, "motion.detected")
        response = await gateway.handle_message(msg, context=ctx)
        assert response.payload["status"] == "accepted"
        execution_id = response.payload["execution_id"]
        assert execution_id

        execution = engine.get(execution_id)
        assert execution is not None
        assert execution.actor == f"device:{device_id}"
        assert execution.intent.name == "device:motion.detected"

    async def test_heartbeat_never_creates_execution(self):
        """Heartbeat = telemetry only (EDGE §21, §30)."""
        gateway, store, engine = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        before = len(engine.executions)
        msg = make_message(
            EdgeMessageType.HEARTBEAT,
            device_id=device_id,
            payload={"uptime_seconds": 1},
        ).model_dump()
        response = await gateway.handle_message(msg, context=ctx)
        assert response.payload["status"] == "ok"
        assert len(engine.executions) == before


# ---------------------------------------------------------------------------
# Event idempotency (EDGE §46)
# ---------------------------------------------------------------------------


class TestEventIdempotency:
    async def test_duplicate_message_id_is_idempotent(self):
        gateway, store, engine = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)

        msg = _event_msg(device_id, "motion.detected", message_id="msg_dup")
        first = await gateway.handle_message(dict(msg), context=ctx)
        second = await gateway.handle_message(dict(msg), context=ctx)

        assert first.payload["status"] == "accepted"
        assert second.payload["status"] == "duplicate"
        # Exactly one execution for one semantic event
        executions = [
            e
            for e in engine.executions.values()
            if e.intent.name == "device:motion.detected"
        ]
        assert len(executions) == 1


# ---------------------------------------------------------------------------
# State synchronization (EDGE §22–§24, §48)
# ---------------------------------------------------------------------------


class TestStateSync:
    async def _ctx_gateway(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        return gateway, ctx

    async def test_state_sync_accepted(self):
        gateway, ctx = await self._ctx_gateway()
        msg = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=ctx.device_id,
            payload={"state": {"temperature": 31.4}, "state_version": 1},
        ).model_dump()
        response = await gateway.handle_message(msg, context=ctx)
        assert response.payload["status"] == "accepted"

        device = await gateway.store.get_device(ctx.device_id)
        assert device.state == {"temperature": 31.4}
        assert device.state_version == 1

    async def test_stale_state_rejected(self):
        gateway, ctx = await self._ctx_gateway()
        ok = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=ctx.device_id,
            payload={"state": {"v": 42}, "state_version": 42},
        ).model_dump()
        await gateway.handle_message(ok, context=ctx)

        stale = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=ctx.device_id,
            payload={"state": {"v": 41}, "state_version": 41},
        ).model_dump()
        with pytest.raises(InvalidStateVersionError):
            await gateway.handle_message(stale, context=ctx)

        device = await gateway.store.get_device(ctx.device_id)
        assert device.state == {"v": 42}

    async def test_equal_version_is_idempotent(self):
        gateway, ctx = await self._ctx_gateway()
        msg = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=ctx.device_id,
            payload={"state": {"v": 42}, "state_version": 42},
        ).model_dump()
        await gateway.handle_message(msg, context=ctx)
        # Same version retried → accepted (protocol retry)
        await gateway.handle_message(dict(msg), context=ctx)


# ---------------------------------------------------------------------------
# Effect delivery (EDGE §25–§29, §47, §50)
# ---------------------------------------------------------------------------


class TestEffects:
    async def test_submit_and_ack_full_cycle(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)

        delivery = await gateway.submit_effect(
            effect_id="effect_1",
            execution_id="exec_1",
            device_id=device_id,
            capability="relay.fan.control",
            payload={"state": "on"},
        )
        assert delivery.status == "pending"

        pending = await gateway.pending_effects(device_id, ctx)
        assert len(pending) == 1
        assert pending[0].effect_id == "effect_1"

        ack = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device_id,
            payload={"effect_id": "effect_1", "status": "completed"},
        ).model_dump()
        response = await gateway.handle_message(ack, context=ctx)
        assert response.payload["status"] == "accepted"

        final = await store.get_effect_delivery("effect_1")
        assert final.status == "completed"
        assert final.ack_status == "completed"

    async def test_duplicate_effect_submission_idempotent(self):
        gateway, store, _ = await _make_gateway()
        device_id, _ = await _enrolled_device(gateway)
        await gateway.submit_effect(
            effect_id="effect_dup",
            execution_id="e",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        await gateway.submit_effect(
            effect_id="effect_dup",
            execution_id="e",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        pending = await store.pending_effects(device_id)
        assert len(pending) == 1

    async def test_unauthorized_capability_rejected(self):
        """Runtime boundary rejects effects the device lacks (EDGE §50)."""
        gateway, store, _ = await _make_gateway()
        device_id, _ = await _enrolled_device(gateway)  # has relay.fan.control
        with pytest.raises(AuthorizationFailedError):
            await gateway.submit_effect(
                effect_id="effect_2",
                execution_id="e",
                device_id=device_id,
                capability="motor.control",
                payload={},
            )

    async def test_unknown_effect_ack_rejected(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        ack = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device_id,
            payload={"effect_id": "ghost", "status": "completed"},
        ).model_dump()
        with pytest.raises(EffectNotFoundError):
            await gateway.handle_message(ack, context=ctx)

    async def test_cross_device_isolation(self):
        """Device A cannot ack device B's effects (EDGE §77)."""
        gateway, store, _ = await _make_gateway()

        key_a = await create_enrollment(gateway.store, capabilities=["relay.control"])
        device_a, cred_a = await gateway.enroll(key_a)
        key_b = await create_enrollment(gateway.store, capabilities=["relay.control"])
        device_b, cred_b = await gateway.enroll(key_b)

        ctx_a, _ = await gateway.connect(cred_a)
        ctx_b, _ = await gateway.connect(cred_b)

        await gateway.submit_effect(
            effect_id="effect_b1",
            execution_id="e",
            device_id=device_b.device_id,
            capability="relay.control",
            payload={},
        )
        ack_for_b = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device_a.device_id,
            payload={"effect_id": "effect_b1", "status": "completed"},
        ).model_dump()
        with pytest.raises(AuthorizationFailedError):
            await gateway.handle_message(ack_for_b, context=ctx_a)

        ack_ok = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device_b.device_id,
            payload={"effect_id": "effect_b1", "status": "completed"},
        ).model_dump()
        await gateway.handle_message(ack_ok, context=ctx_b)


# ---------------------------------------------------------------------------
# Sessions & reconnect (EDGE §45)
# ---------------------------------------------------------------------------


class TestSessions:
    async def test_disconnect_keeps_entity_reconnect_no_duplicate(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device
        from voodoo.edge.models import DeviceStatus

        ctx, session = await authenticate_device(gateway.store, credential)
        await gateway.disconnect(session.session_id)

        device = await store.get_device(device_id)
        assert device.status is DeviceStatus.DISCONNECTED
        # Entity persists — reconnect finds the same device_id
        ctx2, session2 = await authenticate_device(gateway.store, credential)
        assert ctx2.device_id == device_id
        devices = await store.list_devices()
        matching = [d for d in devices if d.device_id == device_id]
        assert len(matching) == 1  # no duplicate entity

    async def test_revoked_device_session_dropped(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, session = await gateway.connect(credential)
        assert gateway.context_for_session(session.session_id) is not None

        await gateway.revoke_device(device_id)
        assert gateway.context_for_session(session.session_id) is None


# ---------------------------------------------------------------------------
# Observability (EDGE §51)
# ---------------------------------------------------------------------------


class TestObservability:
    async def test_mesh_events_emitted_and_trace_propagated(self):
        """Device lifecycle emits namespaced mesh events; trace_id flows
        through message → event (EDGE §51)."""
        from voodoo.mesh import mesh

        captured: list[tuple[str, dict]] = []
        original = mesh.broadcast

        async def spy(event, payload=None, **kwargs):
            captured.append((event, dict(payload or {})))
            return None

        mesh.broadcast = spy  # type: ignore[method-assign]
        try:
            gateway, store, _ = await _make_gateway()
            device_id, credential = await _enrolled_device(gateway)
            ctx, _ = await gateway.connect(credential)

            msg = make_message(
                EdgeMessageType.EVENT,
                device_id=device_id,
                payload={
                    "event_name": "motion.detected",
                    "event_payload": {},
                },
                trace_id="trace_obs_1",
            ).model_dump()
            await gateway.handle_message(msg, context=ctx)
        finally:
            mesh.broadcast = original  # type: ignore[method-assign]

        event_names = [e for e, _ in captured]
        assert "device.connected" in event_names
        assert "device.event" in event_names

        device_event = next(p for e, p in captured if e == "device.event")
        assert device_event["trace_id"] == "trace_obs_1"
        assert device_event["device_id"] == device_id
        # Credentials must never appear in event payloads (EDGE §9).
        assert credential not in str(captured)
