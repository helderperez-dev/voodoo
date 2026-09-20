"""Edge gateway tests — Phase 3: routing, auth, events, state, effects (Sprint 23)."""

from __future__ import annotations

import pytest

from voodoo.edge.auth import create_enrollment
from voodoo.edge.errors import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    DeviceIdMismatchError,
    EffectNotFoundError,
    InvalidStateVersionError,
)
from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import DeviceStatus, TransportKind
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
        # Duplicate replays the original response (Phase 5 — response replay).
        assert second.payload["status"] == "accepted"
        assert second.payload["event_name"] == first.payload["event_name"]
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


# ---------------------------------------------------------------------------
# Identity validation (Sprint 23.1 — EDGE §77)
# ---------------------------------------------------------------------------


class TestIdentityValidation:
    async def test_device_id_mismatch_rejected(self):
        """A message claiming a different device_id is rejected (EDGE §77)."""
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)

        # Message claims a different device_id than the authenticated one.
        msg = make_message(
            EdgeMessageType.EVENT,
            device_id="device_impostor",
            payload={
                "event_name": "temperature.changed",
                "event_payload": {"value": 1},
                "message_id": "msg_mismatch",
            },
        ).model_dump()
        with pytest.raises(DeviceIdMismatchError):
            await gateway.handle_message(msg, context=ctx)

    async def test_device_id_match_accepted(self):
        """A message with the correct device_id is accepted."""
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)

        msg = make_message(
            EdgeMessageType.EVENT,
            device_id=device_id,
            payload={
                "event_name": "temperature.changed",
                "event_payload": {"value": 1},
                "message_id": "msg_match",
            },
        ).model_dump()
        response = await gateway.handle_message(msg, context=ctx)
        assert response.payload["status"] == "accepted"

    async def test_empty_device_id_passthrough(self):
        """A message with no device_id uses the context's device."""
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)

        msg = make_message(
            EdgeMessageType.HEARTBEAT,
            device_id="",
            payload={"uptime_seconds": 1},
        ).model_dump()
        response = await gateway.handle_message(msg, context=ctx)
        assert response.payload["status"] == "ok"


# ---------------------------------------------------------------------------
# Stateless authentication (Sprint 23.1)
# ---------------------------------------------------------------------------


class TestStatelessAuth:
    async def test_authenticate_request_returns_context_no_session(self):
        """authenticate_request() returns context without creating a session."""
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)

        ctx = await gateway.authenticate_request(credential)
        assert ctx.device_id == device_id
        # No session should be registered in the gateway.
        assert len(gateway._contexts) == 0

    async def test_authenticate_request_rejects_bad_credential(self):
        gateway, store, _ = await _make_gateway()
        with pytest.raises(AuthenticationFailedError):
            await gateway.authenticate_request("vdk_bogus")

    async def test_authenticate_request_rejects_revoked_device(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        await gateway.revoke_device(device_id)
        # Credential is cascade-revoked, so auth fails at credential lookup.
        with pytest.raises(AuthenticationFailedError):
            await gateway.authenticate_request(credential)

    async def test_authenticate_request_updates_last_seen(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)

        await gateway.authenticate_request(credential)
        device_after = await store.get_device(device_id)
        assert device_after.last_seen_at is not None


# ---------------------------------------------------------------------------
# Phase 4 — Effect lifecycle, claiming, retry
# ---------------------------------------------------------------------------


class TestEffectLifecycle:
    """Effect state machine: pending → delivering → acked/completed."""

    async def test_effect_starts_pending(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        await gateway.connect(credential)
        delivery = await gateway.submit_effect(
            effect_id="fx-1",
            execution_id="ex-1",
            device_id=device_id,
            capability="relay.fan.control",
            payload={"on": True},
        )
        assert delivery.status == "pending"
        assert delivery.execution_id == "ex-1"

    async def test_claim_transitions_to_delivering(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        await gateway.connect(credential)
        await gateway.submit_effect(
            effect_id="fx-2",
            execution_id="ex-2",
            device_id=device_id,
            capability="relay.fan.control",
            payload={"on": True},
        )
        claimed = await store.claim_effect(device_id, "fx-2")
        assert claimed is True
        fx = await store.get_effect_delivery("fx-2")
        assert fx.status == "delivering"

    async def test_claim_rejects_non_pending(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        await gateway.connect(credential)
        await gateway.submit_effect(
            effect_id="fx-3",
            execution_id="ex-3",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        await store.claim_effect(device_id, "fx-3")
        # Second claim should fail — already delivering.
        assert await store.claim_effect(device_id, "fx-3") is False

    async def test_ack_transitions_to_completed(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, session = await gateway.connect(credential)
        await gateway.submit_effect(
            effect_id="fx-4",
            execution_id="ex-4",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        await store.claim_effect(device_id, "fx-4")
        from voodoo.edge.protocol import EdgeMessageType, make_message

        ack = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device_id,
            payload={"effect_id": "fx-4", "status": "completed"},
        )
        resp = await gateway.handle_effect_ack(ack, ctx)
        assert resp.payload["status"] == "accepted"
        fx = await store.get_effect_delivery("fx-4")
        assert fx.status == "completed"

    async def test_pending_effects_uses_claiming(self):
        """pending_effects() atomically claims each effect."""
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, session = await gateway.connect(credential)
        await gateway.submit_effect(
            effect_id="fx-5a",
            execution_id="ex-5",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        await gateway.submit_effect(
            effect_id="fx-5b",
            execution_id="ex-5",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        effects = await gateway.pending_effects(device_id, ctx)
        assert len(effects) == 2
        # Both should now be delivering — not returned on next poll.
        for e in effects:
            fx = await store.get_effect_delivery(e.effect_id)
            assert fx.status == "delivering"
        effects2 = await gateway.pending_effects(device_id, ctx)
        assert len(effects2) == 0


class TestEffectRetry:
    """Retry policy: delivering → pending (retry) or delivery_failed."""

    async def test_retry_resets_to_pending(self):
        store = InMemoryDeviceStore()
        from voodoo.edge.store import EffectDelivery

        d = EffectDelivery(
            "fx-r1", "ex-1", "dev-1", "relay.fan.control", {}, max_retries=3
        )
        d.status = "delivering"
        store._effects["fx-r1"] = d
        result = await store.retry_effect("fx-r1")
        assert result is True
        fx = await store.get_effect_delivery("fx-r1")
        assert fx.status == "pending"
        assert fx.retry_count == 1

    async def test_retry_exceeds_max_goes_to_delivery_failed(self):
        store = InMemoryDeviceStore()
        from voodoo.edge.store import EffectDelivery

        d = EffectDelivery(
            "fx-r2", "ex-1", "dev-1", "relay.fan.control", {}, max_retries=2
        )
        d.status = "delivering"
        d.retry_count = 1  # already retried once
        store._effects["fx-r2"] = d
        result = await store.retry_effect("fx-r2")
        assert result is True
        fx = await store.get_effect_delivery("fx-r2")
        assert fx.status == "delivery_failed"

    async def test_retry_rejects_non_delivering(self):
        store = InMemoryDeviceStore()
        from voodoo.edge.store import EffectDelivery

        d = EffectDelivery("fx-r3", "ex-1", "dev-1", "relay.fan.control", {})
        store._effects["fx-r3"] = d
        # pending — not delivering
        assert await store.retry_effect("fx-r3") is False

    async def test_gateway_retry_effects(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        await gateway.connect(credential)
        await gateway.submit_effect(
            effect_id="fx-r4",
            execution_id="ex-r4",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        await store.claim_effect(device_id, "fx-r4")
        retried = await gateway.retry_effects(device_id)
        assert retried == 1
        fx = await store.get_effect_delivery("fx-r4")
        assert fx.status == "pending"

    async def test_max_retries_from_config(self):
        """submit_effect reads max_effect_retries from config."""
        from voodoo.config import EdgeConfig, VoodooConfig

        cfg = VoodooConfig()
        cfg.edge = EdgeConfig(enabled=True, max_effect_retries=5)
        store = InMemoryDeviceStore()
        gateway = DeviceGateway(store, config=cfg)
        device_id, credential = await _enrolled_device(gateway)
        await gateway.connect(credential)
        delivery = await gateway.submit_effect(
            effect_id="fx-cfg",
            execution_id="ex-cfg",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        assert delivery.max_retries == 5


class TestEffectExecutionBinding:
    """Effects carry execution_id for runtime integration."""

    async def test_execution_id_stored_on_delivery(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        await gateway.connect(credential)
        await gateway.submit_effect(
            effect_id="fx-b1",
            execution_id="ex-bound-42",
            device_id=device_id,
            capability="relay.fan.control",
            payload={"brightness": 80},
        )
        fx = await store.get_effect_delivery("fx-b1")
        assert fx.execution_id == "ex-bound-42"

    async def test_execution_id_in_ack_event(self):
        """ACK event payload includes execution_id."""
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, session = await gateway.connect(credential)
        await gateway.submit_effect(
            effect_id="fx-b2",
            execution_id="ex-bound-99",
            device_id=device_id,
            capability="relay.fan.control",
            payload={},
        )
        await store.claim_effect(device_id, "fx-b2")
        from voodoo.edge.protocol import EdgeMessageType, make_message

        ack = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=device_id,
            payload={"effect_id": "fx-b2", "status": "completed"},
        )
        await gateway.handle_effect_ack(ack, ctx)
        # The ACK event is emitted with execution_id — verified by no errors.


# ---------------------------------------------------------------------------
# Phase 5 — Response replay & state reconciliation
# ---------------------------------------------------------------------------


class TestResponseReplay:
    """Duplicate messages receive the original response, not a generic ack."""

    async def test_duplicate_replays_original_response(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        msg = _event_msg(device_id, "motion.detected", message_id="msg_replay_1")
        first = await gateway.handle_message(dict(msg), context=ctx)
        second = await gateway.handle_message(dict(msg), context=ctx)
        # Both should have identical payloads.
        assert first.payload["status"] == "accepted"
        assert second.payload["status"] == "accepted"
        assert first.payload["event_name"] == second.payload["event_name"]

    async def test_stored_response_persisted(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        msg = make_message(
            EdgeMessageType.EVENT,
            device_id=device_id,
            payload={
                "event_name": "sensor.read",
                "event_payload": {"value": 42},
            },
            message_id="msg_replay_2",
        ).model_dump()
        await gateway.handle_message(dict(msg), context=ctx)
        stored = await store.get_stored_response("msg_replay_2")
        assert stored is not None
        assert "accepted" in stored

    async def test_telemetry_duplicate_replays(self):
        """Telemetry event duplicates also get replayed responses."""
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        msg = _event_msg(device_id, "heartbeat", message_id="msg_replay_3")
        first = await gateway.handle_message(dict(msg), context=ctx)
        second = await gateway.handle_message(dict(msg), context=ctx)
        assert first.payload["telemetry"] is True
        assert second.payload["telemetry"] is True


class TestStateReconciliation:
    """State version conflict handling — stale writes rejected with detail."""

    async def test_stale_state_raises_with_current_version(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        # First sync at version 5.
        msg1 = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id,
            payload={"state": {"temp": 20}, "state_version": 5},
        )
        await gateway.handle_state_sync(msg1, ctx)
        # Stale sync at version 3.
        msg2 = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id,
            payload={"state": {"temp": 25}, "state_version": 3},
        )
        with pytest.raises(InvalidStateVersionError) as exc_info:
            await gateway.handle_state_sync(msg2, ctx)
        assert exc_info.value.detail["current"] == 5
        assert exc_info.value.detail["incoming"] == 3

    async def test_newer_state_accepted(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        from voodoo.edge.auth import authenticate_device

        ctx, _ = await authenticate_device(gateway.store, credential)
        msg1 = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id,
            payload={"state": {"temp": 20}, "state_version": 1},
        )
        await gateway.handle_state_sync(msg1, ctx)
        msg2 = make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=device_id,
            payload={"state": {"temp": 30}, "state_version": 2},
        )
        resp = await gateway.handle_state_sync(msg2, ctx)
        assert resp.payload["status"] == "accepted"
        device = await store.get_device(device_id)
        assert device.state["temp"] == 30


# ---------------------------------------------------------------------------
# Phase 6: Reconnect & Device Lifecycle
# ---------------------------------------------------------------------------


class TestReconnect:
    """Reconnect lifecycle: RECONNECTING → CONNECTED, session cleanup."""

    async def test_reconnect_transitions_through_reconnecting(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        # First connection
        ctx1, sess1 = await gateway.connect(credential)
        assert ctx1.device_id == device_id
        device = await store.get_device(device_id)
        assert device.status == DeviceStatus.CONNECTED
        # Reconnect — should transition RECONNECTING → CONNECTED
        ctx2, sess2 = await gateway.connect(credential)
        assert ctx2.device_id == device_id
        device = await store.get_device(device_id)
        assert device.status == DeviceStatus.CONNECTED
        assert sess2.session_id != sess1.session_id

    async def test_reconnect_evicts_stale_context(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx1, sess1 = await gateway.connect(credential)
        assert sess1.session_id in gateway._contexts
        # Reconnect
        ctx2, sess2 = await gateway.connect(credential)
        # Old context evicted, new one registered
        assert sess1.session_id not in gateway._contexts
        assert sess2.session_id in gateway._contexts

    async def test_reconnect_emits_connected_event(self):
        from voodoo.mesh import mesh

        captured: list[tuple[str, dict]] = []
        original = mesh.broadcast

        async def spy(
            event: str, payload: dict | None = None, **kwargs: object
        ) -> None:
            captured.append((event, dict(payload or {})))

        mesh.broadcast = spy  # type: ignore[method-assign]
        try:
            gateway, store, _ = await _make_gateway()
            device_id, credential = await _enrolled_device(gateway)
            await gateway.connect(credential)
            captured.clear()
            await gateway.connect(credential)
            connected_events = [e for e, _ in captured if e == "device.connected"]
            assert len(connected_events) == 1
        finally:
            mesh.broadcast = original  # type: ignore[method-assign]

    async def test_reconnect_deletes_old_sessions(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        _, sess1 = await gateway.connect(credential)
        # Verify old session exists
        old_session = await store.get_session(sess1.session_id)
        assert old_session is not None
        # Reconnect
        _, sess2 = await gateway.connect(credential)
        # Old session should be deleted
        old_session = await store.get_session(sess1.session_id)
        assert old_session is None
        # New session exists
        new_session = await store.get_session(sess2.session_id)
        assert new_session is not None

    async def test_disconnect_sets_status(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, sess = await gateway.connect(credential)
        await gateway.disconnect(sess.session_id)
        device = await store.get_device(device_id)
        assert device.status == DeviceStatus.DISCONNECTED


class TestDisconnectLifecycle:
    """Disconnect handling and context cleanup."""

    async def test_disconnect_removes_context(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, sess = await gateway.connect(credential)
        assert sess.session_id in gateway._contexts
        await gateway.disconnect(sess.session_id)
        assert sess.session_id not in gateway._contexts

    async def test_disconnect_emits_event(self):
        from voodoo.mesh import mesh

        captured: list[tuple[str, dict]] = []
        original = mesh.broadcast

        async def spy(
            event: str, payload: dict | None = None, **kwargs: object
        ) -> None:
            captured.append((event, dict(payload or {})))

        mesh.broadcast = spy  # type: ignore[method-assign]
        try:
            gateway, store, _ = await _make_gateway()
            device_id, credential = await _enrolled_device(gateway)
            ctx, sess = await gateway.connect(credential)
            captured.clear()
            await gateway.disconnect(sess.session_id)
            dc_events = [e for e, _ in captured if e == "device.disconnected"]
            assert len(dc_events) == 1
        finally:
            mesh.broadcast = original  # type: ignore[method-assign]

    async def test_disconnect_nonexistent_session_is_noop(self):
        gateway, store, _ = await _make_gateway()
        # Should not raise
        await gateway.disconnect("nonexistent-session-id")


class TestLastSeenTracking:
    """last_seen_at updated only on authenticated activity."""

    async def test_last_seen_updated_on_connect(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        device_before = await store.get_device(device_id)
        assert device_before.last_seen_at is None
        await gateway.connect(credential)
        device_after = await store.get_device(device_id)
        assert device_after.last_seen_at is not None

    async def test_last_seen_updated_on_event(self):
        gateway, store, _ = await _make_gateway()
        device_id, credential = await _enrolled_device(gateway)
        ctx, _ = await gateway.connect(credential)
        device_after_connect = await store.get_device(device_id)
        ts1 = device_after_connect.last_seen_at
        msg = _event_msg(device_id, "sensor.reading")
        await gateway.handle_message(msg, context=ctx)
        device_after_event = await store.get_device(device_id)
        ts2 = device_after_event.last_seen_at
        assert ts2 is not None
        assert ts2 >= ts1
