"""Device Gateway — the Edge boundary into the Voodoo Runtime (EDGE §32, §72).

The Gateway authenticates devices, validates protocol messages, ingests
events and state, and delivers effects. It contains **no** business
logic: device-triggered work enters the standard ExecutionEngine, device
events use the standard event system, and device state uses the standard
State semantics. There is no DeviceExecutionEngine (EDGE §1, §86).

    Device → Event → Gateway → Execution → Effect → Gateway → Device

Every message carries/propagates a trace_id through the full lifecycle
(EDGE §51) and all device lifecycle transitions emit namespaced mesh
events. Credentials never appear in events, logs, or telemetry.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from voodoo.edge.auth import authenticate_device, consume_enrollment
from voodoo.edge.errors import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    DeviceIdMismatchError,
    DeviceNotFoundError,
    EffectNotFoundError,
    InvalidMessageError,
    InvalidStateVersionError,
    PayloadTooLargeError,
)
from voodoo.edge.models import (
    AuthenticatedDeviceContext,
    Device,
    DeviceSession,
    DeviceStatus,
    TransportKind,
)
from voodoo.edge.protocol import (
    AuthPayload,
    EdgeMessage,
    EdgeMessageType,
    EffectAckPayload,
    EventPayload,
    HelloPayload,
    StateSyncPayload,
    decode_message,
    make_message,
)
from voodoo.edge.store import DeviceStoreProtocol, EffectDelivery

if TYPE_CHECKING:
    from voodoo.runtime.engine import ExecutionEngine

logger = logging.getLogger("voodoo.edge")

__all__ = ["DeviceGateway"]


def _redact(value: str, *, show: int = 4) -> str:
    """Redact a sensitive value, showing only the last *show* characters.

    Used for debug logging of device IDs and session tokens — credentials
    are never logged (EDGE §9).
    """
    if len(value) <= show:
        return "***"
    return f"{'*' * (len(value) - show)}{value[-show:]}"


# Events that are pure telemetry — never become Executions (EDGE §21).
_TELEMETRY_EVENTS = frozenset({"heartbeat", "device.heartbeat"})


class DeviceGateway:
    """Coordinates Edge transports and delegates to the Voodoo Runtime.

    Parameters
    ----------
    store:
        Device persistence (devices, credentials, sessions, effects,
        message idempotency).
    engine:
        The authoritative ExecutionEngine. Device-triggered work runs
        here; the gateway never executes domain logic itself.
    """

    def __init__(
        self,
        store: DeviceStoreProtocol,
        engine: ExecutionEngine | None = None,
        *,
        config: Any | None = None,
    ) -> None:
        self._store = store
        self._engine = engine
        self._config = config
        # Authenticated contexts by session_id — reconnects re-attach.
        self._contexts: dict[str, AuthenticatedDeviceContext] = {}

    @property
    def store(self) -> DeviceStoreProtocol:
        return self._store

    @property
    def engine(self) -> ExecutionEngine | None:
        return self._engine

    # ------------------------------------------------------------------
    # Enrollment
    # ------------------------------------------------------------------

    async def enroll(
        self, enrollment_key: str, *, firmware_version: str | None = None
    ) -> tuple[Device, str]:
        """Consume an enrollment key → (device, raw credential)."""
        device, raw_credential = await consume_enrollment(
            self._store, enrollment_key, firmware_version=firmware_version
        )
        await self._emit(
            "device.enrolled",
            {"device_id": device.device_id, "device_type": device.type},
            trace_id=None,
        )
        return device, raw_credential

    # ------------------------------------------------------------------
    # Canonical authentication entry point
    # ------------------------------------------------------------------

    async def connect(
        self,
        credential: str,
        *,
        claimed_device_id: str | None = None,
        transport: TransportKind = TransportKind.HTTP,
    ) -> tuple[AuthenticatedDeviceContext, DeviceSession]:
        """Authenticate a device and register its live context.

        This is the canonical way transports authenticate — direct calls
        to ``authenticate_device`` bypass session tracking. Returns
        ``(context, session)`` with the context registered for subsequent
        messages. On reconnect, stale contexts for the same device are
        evicted first.
        """
        ctx, session = await authenticate_device(
            self._store,
            credential,
            claimed_device_id=claimed_device_id,
            transport=transport,
        )
        stale_sids = [
            sid for sid, c in self._contexts.items() if c.device_id == ctx.device_id
        ]
        for sid in stale_sids:
            self._contexts.pop(sid, None)
        self._contexts[session.session_id] = ctx
        await self._emit(
            "device.connected",
            {
                "device_id": ctx.device_id,
                "session_id": session.session_id,
                "transport": transport.value,
            },
            trace_id=None,
        )
        return ctx, session

    # ------------------------------------------------------------------
    # Stateless authentication (HTTP — no session created)
    # ------------------------------------------------------------------

    async def authenticate_request(
        self,
        credential: str,
        *,
        transport: TransportKind = TransportKind.HTTP,
    ) -> AuthenticatedDeviceContext:
        """Authenticate a device credential without creating a session."""
        ctx, _session = await authenticate_device(
            self._store,
            credential,
            transport=transport,
        )
        await self._store.update_last_seen(ctx.device_id)
        return ctx

    # ------------------------------------------------------------------
    # Message entry point (EDGE §72 — thin route → gateway)
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        raw: str | bytes | dict[str, Any],
        *,
        transport: TransportKind = TransportKind.HTTP,
        context: AuthenticatedDeviceContext | None = None,
    ) -> EdgeMessage:
        """Decode, validate, authenticate (if needed), and route a message."""
        message = decode_message(raw)

        if self._config is not None:
            edge_cfg = getattr(self._config, "edge", None)
            if edge_cfg is not None:
                max_size = getattr(edge_cfg, "max_message_size", 0)
                if max_size > 0:
                    raw_size = (
                        len(raw) if isinstance(raw, (str, bytes)) else len(str(raw))
                    )
                    if raw_size > max_size:
                        raise PayloadTooLargeError(
                            f"Message size {raw_size} exceeds limit {max_size}"
                        )

        if message.type is EdgeMessageType.AUTH:
            return await self.handle_auth(message, transport=transport)

        ctx = context or await self._require_context(message)
        if message.device_id and message.device_id != ctx.device_id:
            raise DeviceIdMismatchError(
                f"Message device_id '{message.device_id}' does not match "
                f"authenticated device '{ctx.device_id}'"
            )

        handler = {
            EdgeMessageType.HELLO: self.handle_hello,
            EdgeMessageType.STATE_SYNC: self.handle_state_sync,
            EdgeMessageType.EVENT: self.handle_event,
            EdgeMessageType.EFFECT_ACK: self.handle_effect_ack,
            EdgeMessageType.HEARTBEAT: self.handle_heartbeat,
        }.get(message.type)
        if handler is None:
            raise InvalidMessageError(
                f"Unsupported message type '{message.type.value}'"
            )
        return await handler(message, ctx)

    async def handle_auth(
        self, message: EdgeMessage, *, transport: TransportKind
    ) -> EdgeMessage:
        payload = message.typed_payload()
        if not isinstance(payload, AuthPayload):
            raise InvalidMessageError("AUTH handler received a non-AUTH payload")
        ctx, session = await self.connect(
            payload.credential,
            claimed_device_id=payload.device_id or None,
            transport=transport,
        )
        return make_message(
            EdgeMessageType.AUTH,
            device_id=ctx.device_id,
            payload={
                "session_id": session.session_id,
                "device_id": ctx.device_id,
                "protocol_version": message.version,
                "capabilities": ctx.capabilities,
            },
            correlation_id=message.message_id,
            trace_id=message.trace_id,
        )

    async def handle_hello(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        payload = message.typed_payload()
        if not isinstance(payload, HelloPayload):
            raise InvalidMessageError("HELLO handler received a non-HELLO payload")
        device = await self._require_device(ctx.device_id)

        if payload.capabilities:
            device.capabilities = list(
                set(device.capabilities) | set(payload.capabilities)
            )
            await self._store.update_device_capabilities(
                ctx.device_id, device.capabilities
            )
            ctx.capabilities = list(device.capabilities)
        if payload.firmware_version:
            device.metadata["firmware_version"] = payload.firmware_version

        await self._store.update_device_status(ctx.device_id, DeviceStatus.CONNECTED)
        return make_message(
            EdgeMessageType.HELLO,
            device_id=ctx.device_id,
            payload={
                "device_id": ctx.device_id,
                "status": "connected",
                "capabilities": device.capabilities,
            },
            correlation_id=message.message_id,
            trace_id=message.trace_id,
        )

    async def handle_event(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        """Ingest a device event (EDGE §19–§21)."""
        payload = message.typed_payload()
        if not isinstance(payload, EventPayload):
            raise InvalidMessageError("EVENT handler received a non-EVENT payload")
        if await self._store.seen_message(message.message_id):
            stored = await self._store.get_stored_response(message.message_id)
            if stored is not None:
                return EdgeMessage.model_validate_json(stored)
            return make_message(
                EdgeMessageType.EVENT,
                device_id=ctx.device_id,
                payload={"status": "duplicate", "event_name": payload.event_name},
                correlation_id=message.message_id,
                trace_id=message.trace_id,
            )
        await self._store.mark_message_seen(message.message_id)

        event_name = payload.event_name
        full_name = (
            event_name if event_name.startswith("device.") else f"device.{event_name}"
        )
        await self._emit(
            "device.event",
            {
                "device_id": ctx.device_id,
                "event": full_name,
                "message_id": message.message_id,
            },
            trace_id=message.trace_id,
        )

        if event_name in _TELEMETRY_EVENTS:
            await self._store.update_last_seen(ctx.device_id)
            response = make_message(
                EdgeMessageType.EVENT,
                device_id=ctx.device_id,
                payload={
                    "status": "accepted",
                    "event_name": event_name,
                    "telemetry": True,
                },
                correlation_id=message.message_id,
                trace_id=message.trace_id,
            )
            await self._store.store_response(
                message.message_id, response.model_dump_json()
            )
            return response

        execution_id: str | None = None
        if self._engine is not None:
            from voodoo.primitives.intent import Intent
            from voodoo.runtime.engine import ComputeResult

            intent = Intent(
                name=f"device:{event_name}",
                params={
                    "device_id": ctx.device_id,
                    "event": event_name,
                    "payload": payload.event_payload,
                },
            )

            async def telemetry_only(ctx_: Any) -> ComputeResult:
                return ComputeResult(value={"ingested": True, "event": event_name})

            execution = await self._engine.execute(
                intent, telemetry_only, actor=f"device:{ctx.device_id}"
            )
            execution_id = execution.id

        response = make_message(
            EdgeMessageType.EVENT,
            device_id=ctx.device_id,
            payload={
                "status": "accepted",
                "event_name": event_name,
                "execution_id": execution_id,
            },
            correlation_id=message.message_id,
            trace_id=message.trace_id,
        )
        await self._store.store_response(message.message_id, response.model_dump_json())
        return response

    async def handle_state_sync(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        """Versioned state ingestion — stale writes rejected (EDGE §22–§24)."""
        payload = message.typed_payload()
        if not isinstance(payload, StateSyncPayload):
            raise InvalidMessageError(
                "STATE_SYNC handler received a non-STATE_SYNC payload"
            )
        device = await self._require_device(ctx.device_id)

        if self._config is not None:
            edge_cfg = getattr(self._config, "edge", None)
            if edge_cfg is not None:
                max_size = getattr(edge_cfg, "max_state_size", 0)
                if max_size > 0:
                    import json

                    state_size = len(json.dumps(payload.state).encode())
                    if state_size > max_size:
                        raise PayloadTooLargeError(
                            f"State size {state_size} exceeds limit {max_size}"
                        )

        applied = await self._store.update_device_state(
            ctx.device_id, payload.state, payload.state_version
        )
        if not applied:
            raise InvalidStateVersionError(
                f"Stale state_version {payload.state_version} "
                f"(runtime has {device.state_version})",
                detail={
                    "incoming": payload.state_version,
                    "current": device.state_version,
                },
            )

        await self._store.update_last_seen(ctx.device_id)
        return make_message(
            EdgeMessageType.STATE_SYNC,
            device_id=ctx.device_id,
            payload={
                "status": "accepted",
                "state_version": payload.state_version,
                "state": payload.state,
            },
            correlation_id=message.message_id,
            trace_id=message.trace_id,
        )

    async def handle_effect_ack(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        """Record a device's acknowledgement of a delivered effect."""
        payload = message.typed_payload()
        if not isinstance(payload, EffectAckPayload):
            raise InvalidMessageError(
                "EFFECT_ACK handler received a non-EFFECT_ACK payload"
            )
        delivery = await self._store.get_effect_delivery(payload.effect_id)
        if delivery is None:
            raise EffectNotFoundError(f"Effect '{payload.effect_id}' not found")
        if delivery.device_id != ctx.device_id:
            raise AuthorizationFailedError("Effect belongs to a different device")

        delivery = await self._store.mark_effect_acked(
            payload.effect_id, payload.status.value
        )
        await self._emit(
            "device.effect.acked",
            {
                "device_id": ctx.device_id,
                "effect_id": payload.effect_id,
                "ack_status": payload.status.value,
                "execution_id": delivery.execution_id if delivery else "",
            },
            trace_id=message.trace_id,
        )
        return make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=ctx.device_id,
            payload={"status": "accepted", "effect_id": payload.effect_id},
            correlation_id=message.message_id,
            trace_id=message.trace_id,
        )

    async def handle_heartbeat(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        """Update liveness — never creates an Execution (EDGE §30)."""
        message.typed_payload()
        await self._store.update_last_seen(ctx.device_id)
        device = await self._store.get_device(ctx.device_id)
        return make_message(
            EdgeMessageType.HEARTBEAT,
            device_id=ctx.device_id,
            payload={
                "status": "ok",
                "state_version": device.state_version if device else 0,
            },
            correlation_id=message.message_id,
            trace_id=message.trace_id,
        )

    # ------------------------------------------------------------------
    # Effect delivery (EDGE §25–§29)
    # ------------------------------------------------------------------

    async def submit_effect(
        self,
        *,
        effect_id: str,
        execution_id: str,
        device_id: str,
        capability: str,
        payload: dict[str, Any],
    ) -> EffectDelivery:
        """Queue an effect for delivery to a device."""
        device = await self._require_device(device_id)
        if capability not in device.capabilities:
            raise AuthorizationFailedError(
                f"Device '{device_id}' lacks capability '{capability}'",
                detail={
                    "required": capability,
                    "device_capabilities": device.capabilities,
                },
            )
        if self._config is not None:
            edge_cfg = getattr(self._config, "edge", None)
            if edge_cfg is not None:
                max_pending = getattr(edge_cfg, "max_pending_effects", 0)
                if max_pending > 0:
                    pending = await self._store.pending_effects(device_id)
                    if len(pending) >= max_pending:
                        raise PayloadTooLargeError(
                            f"Device '{device_id}' has {len(pending)} pending effects "
                            f"(limit {max_pending})"
                        )
        max_retries = 3
        if self._config is not None:
            try:
                max_retries = int(self._config.edge.max_effect_retries)
            except (AttributeError, TypeError, ValueError):
                pass
        delivery = EffectDelivery(
            effect_id=effect_id,
            execution_id=execution_id,
            device_id=device_id,
            capability=capability,
            payload=payload,
            max_retries=max_retries,
        )
        await self._store.add_effect_delivery(delivery)
        await self._emit(
            "device.effect.submitted",
            {
                "device_id": device_id,
                "effect_id": effect_id,
                "capability": capability,
            },
            trace_id=None,
        )
        return delivery

    async def pending_effects(
        self, device_id: str, ctx: AuthenticatedDeviceContext
    ) -> list[EffectDelivery]:
        """Retrieve and claim pending effects for a device."""
        if device_id != ctx.device_id:
            raise AuthorizationFailedError("Devices may only list their own effects")
        deliveries = await self._store.pending_effects(device_id)
        claimed: list[EffectDelivery] = []
        for delivery in deliveries:
            if await self._store.claim_effect(device_id, delivery.effect_id):
                claimed.append(delivery)
        await self._emit(
            "device.effect.delivered",
            {"device_id": device_id, "count": len(claimed)},
            trace_id=None,
        )
        return claimed

    async def retry_effects(self, device_id: str) -> int:
        """Reset stale delivering effects back to pending for retry."""
        stale = await self._store.stale_deliveries(device_id)
        retried = 0
        for delivery in stale:
            if await self._store.retry_effect(delivery.effect_id):
                retried += 1
        return retried

    # ------------------------------------------------------------------
    # Sessions & revocation
    # ------------------------------------------------------------------

    async def disconnect(self, session_id: str) -> None:
        """Detach a session; the device entity remains valid (EDGE §7)."""
        ctx = self._contexts.pop(session_id, None)
        session = await self._store.get_session(session_id)
        await self._store.delete_session(session_id)
        device_id = (
            ctx.device_id
            if ctx is not None
            else (session.device_id if session is not None else None)
        )
        if device_id is not None:
            await self._store.update_device_status(device_id, DeviceStatus.DISCONNECTED)
            await self._emit(
                "device.disconnected",
                {"device_id": device_id, "session_id": session_id},
                trace_id=None,
            )

    async def revoke_device(self, device_id: str) -> bool:
        """Revoke a device — credentials cascade-revoked (EDGE §49)."""
        revoked = await self._store.revoke_device(device_id)
        if revoked:
            to_drop = [
                sid for sid, ctx in self._contexts.items() if ctx.device_id == device_id
            ]
            for sid in to_drop:
                self._contexts.pop(sid, None)
            await self._emit("device.revoked", {"device_id": device_id}, trace_id=None)
        return revoked

    def context_for_session(self, session_id: str) -> AuthenticatedDeviceContext | None:
        return self._contexts.get(session_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _require_context(
        self, message: EdgeMessage
    ) -> AuthenticatedDeviceContext:
        """Resolve the authenticated context for a non-AUTH message."""
        session_id = str(message.payload.get("session_id", "") or "")
        if not session_id:
            raise AuthenticationFailedError(
                "No authenticated device context; send AUTH first or "
                "present a device credential"
            )
        ctx = self._contexts.get(session_id)
        if ctx is None:
            raise AuthenticationFailedError("Unknown or expired session")
        if message.device_id and message.device_id != ctx.device_id:
            raise AuthenticationFailedError(
                "Message device_id does not match the authenticated session"
            )
        return ctx

    async def _require_device(self, device_id: str) -> Device:
        device = await self._store.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        return device

    async def _emit(
        self, event: str, payload: dict[str, Any], *, trace_id: str | None
    ) -> None:
        """Publish a namespaced mesh event (best-effort, redacted)."""
        try:
            from voodoo.mesh import mesh
            from voodoo.security.redaction import redact

            body = dict(payload)
            if trace_id:
                body["trace_id"] = trace_id
            await mesh.broadcast(event, redact(body))
        except Exception:  # noqa: BLE001
            pass
