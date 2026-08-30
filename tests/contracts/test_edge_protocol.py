"""Edge transport contract tests — HTTP/MQTT semantic equivalence (EDGE §36, §74).

Protocol-level tests independent of transport: the same logical message
must produce the same runtime behavior through either transport. The
MQTT leg runs against the gateway directly (the transport-decoded path)
so equivalence is provable without a live broker.
"""

from __future__ import annotations

import pytest

from voodoo.edge.auth import create_enrollment
from voodoo.edge.errors import AuthorizationFailedError, InvalidStateVersionError
from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import TransportKind
from voodoo.edge.protocol import EdgeMessageType, make_message
from voodoo.edge.store import InMemoryDeviceStore
from voodoo.runtime.engine import ExecutionEngine


async def _make_gateway() -> DeviceGateway:
    store = InMemoryDeviceStore()
    engine = ExecutionEngine()
    return DeviceGateway(store, engine)


async def _enroll(gateway: DeviceGateway, capabilities: list[str]) -> tuple[str, str]:
    key = await create_enrollment(
        gateway.store, device_type="esp32", capabilities=capabilities
    )
    device, credential = await gateway.enroll(key)
    return device.device_id, credential


class TestTransportEquivalence:
    """The same message through HTTP-context and MQTT-session paths must
    produce identical runtime state (EDGE §36)."""

    async def test_event_message_semantics(self):
        """EVENT → same execution, same actor, same intent either way."""
        results = {}
        for transport in (TransportKind.HTTP, TransportKind.MQTT):
            gateway = await _make_gateway()
            device_id, credential = await _enroll(gateway, ["relay.control"])
            ctx, _ = await gateway.connect(credential, transport=transport)
            msg = make_message(
                EdgeMessageType.EVENT,
                device_id=device_id,
                payload={
                    "event_name": "temperature.changed",
                    "event_payload": {"value": 30.0},
                },
            ).model_dump()
            response = await gateway.handle_message(
                msg, transport=transport, context=ctx
            )
            execution_id = response.payload["execution_id"]
            execution = gateway.engine.get(execution_id)  # type: ignore[union-attr]
            results[transport] = {
                "status": response.payload["status"],
                "intent": execution.intent.name,
                "actor": execution.actor,
                "device_state": (
                    await gateway.store.get_device(device_id)
                ).state_version,
            }
        http_result = results[TransportKind.HTTP]
        mqtt_result = results[TransportKind.MQTT]
        assert http_result["status"] == mqtt_result["status"] == "accepted"
        assert http_result["intent"] == mqtt_result["intent"]
        # Each transport uses a fresh device; assert the actor *pattern* —
        # the device actor id (not a user, not "system") in both.
        assert http_result["actor"].startswith("device:device_")
        assert mqtt_result["actor"].startswith("device:device_")

    async def test_state_sync_message_semantics(self):
        for transport in (TransportKind.HTTP, TransportKind.MQTT):
            gateway = await _make_gateway()
            device_id, credential = await _enroll(gateway, [])
            ctx, _ = await gateway.connect(credential, transport=transport)
            ok = make_message(
                EdgeMessageType.STATE_SYNC,
                device_id=device_id,
                payload={"state": {"v": 1}, "state_version": 1},
            ).model_dump()
            response = await gateway.handle_message(
                ok, transport=transport, context=ctx
            )
            assert response.payload["status"] == "accepted"

            stale = make_message(
                EdgeMessageType.STATE_SYNC,
                device_id=device_id,
                payload={"state": {"v": 0}, "state_version": 0},
            ).model_dump()
            with pytest.raises(InvalidStateVersionError):
                await gateway.handle_message(stale, transport=transport, context=ctx)

    async def test_effect_message_semantics(self):
        for transport in (TransportKind.HTTP, TransportKind.MQTT):
            gateway = await _make_gateway()
            device_id, credential = await _enroll(gateway, ["relay.control"])
            ctx, _ = await gateway.connect(credential, transport=transport)

            # Capability enforcement is transport-independent (EDGE §50)
            with pytest.raises(AuthorizationFailedError):
                await gateway.submit_effect(
                    effect_id="e1",
                    execution_id="x",
                    device_id=device_id,
                    capability="motor.control",
                    payload={},
                )
            delivery = await gateway.submit_effect(
                effect_id="e2",
                execution_id="x",
                device_id=device_id,
                capability="relay.control",
                payload={"state": "on"},
            )
            assert delivery.status == "pending"

            ack = make_message(
                EdgeMessageType.EFFECT_ACK,
                device_id=device_id,
                payload={"effect_id": "e2", "status": "completed"},
            ).model_dump()
            response = await gateway.handle_message(
                ack, transport=transport, context=ctx
            )
            assert response.payload["status"] == "accepted"
            final = await gateway.store.get_effect_delivery("e2")
            assert final.status == "completed"

    async def test_heartbeat_no_execution_both_transports(self):
        for transport in (TransportKind.HTTP, TransportKind.MQTT):
            gateway = await _make_gateway()
            device_id, credential = await _enroll(gateway, [])
            ctx, _ = await gateway.connect(credential, transport=transport)
            before = len(gateway.engine.executions)  # type: ignore[union-attr]
            msg = make_message(
                EdgeMessageType.HEARTBEAT,
                device_id=device_id,
                payload={"uptime_seconds": 5},
            ).model_dump()
            response = await gateway.handle_message(
                msg, transport=transport, context=ctx
            )
            assert response.payload["status"] == "ok"
            assert len(gateway.engine.executions) == before  # type: ignore[union-attr]


class TestMQTTSessionFlow:
    """MQTT devices authenticate once (AUTH) then reference the session —
    the gateway must honor that path identically to header-auth HTTP."""

    async def test_session_based_messaging_matches_direct_context(self):
        gateway = await _make_gateway()
        device_id, credential = await _enroll(gateway, ["relay.control"])

        # AUTH establishes the session (as the MQTT transport delivers it)
        auth = make_message(
            EdgeMessageType.AUTH,
            device_id=device_id,
            payload={"credential": credential},
        ).model_dump()
        auth_response = await gateway.handle_message(auth, transport=TransportKind.MQTT)
        session_id = auth_response.payload["session_id"]

        # Subsequent messages carry session_id in the payload — no context
        event = make_message(
            EdgeMessageType.EVENT,
            device_id=device_id,
            payload={
                "session_id": session_id,
                "event_name": "motion.detected",
                "event_payload": {},
            },
        ).model_dump()
        response = await gateway.handle_message(event, transport=TransportKind.MQTT)
        assert response.payload["status"] == "accepted"
        execution = gateway.engine.get(response.payload["execution_id"])  # type: ignore[union-attr]
        assert execution.actor == f"device:{device_id}"

    async def test_session_cannot_impersonate_other_device(self):
        gateway = await _make_gateway()
        device_id, _ = await _enroll(gateway, [])
        other_id, other_credential = await _enroll(gateway, [])

        auth = make_message(
            EdgeMessageType.AUTH,
            device_id=other_id,
            payload={"credential": other_credential},
        ).model_dump()
        session_id = (
            await gateway.handle_message(auth, transport=TransportKind.MQTT)
        ).payload["session_id"]

        spoofed = make_message(
            EdgeMessageType.EVENT,
            device_id=device_id,  # claims the other device
            payload={
                "session_id": session_id,
                "event_name": "motion.detected",
                "event_payload": {},
            },
        ).model_dump()
        from voodoo.edge.errors import AuthenticationFailedError

        with pytest.raises(AuthenticationFailedError):
            await gateway.handle_message(spoofed, transport=TransportKind.MQTT)
