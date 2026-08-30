"""Edge HTTP transport — REST endpoints for the Edge Protocol (EDGE §34, §43).

Routes stay thin (EDGE §72): each endpoint decodes the request into an
EdgeMessage, delegates to the DeviceGateway, and serializes the response
envelope. Device authentication uses the ``X-Device-Credential`` header
(or ``Authorization: Device <credential>``) — deliberately separate from
user authentication.
"""

from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from voodoo.edge.auth import create_enrollment
from voodoo.edge.errors import (
    AuthenticationFailedError,
    EdgeError,
    error_response,
)
from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import TransportKind
from voodoo.edge.protocol import (
    EdgeMessageType,
    make_message,
)

__all__ = ["build_edge_routes", "EdgeHTTPRouter"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _credential_from_request(request: Request) -> str | None:
    """Extract the device credential from headers, if present.

    Supported: ``X-Device-Credential: <cred>`` and
    ``Authorization: Device <cred>``. Never logged or echoed.
    """
    cred = request.headers.get("x-device-credential")
    if cred:
        return cred.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("device "):
        return auth[7:].strip()
    return None


def _error_to_response(error: EdgeError) -> JSONResponse:
    return JSONResponse(error_response(error), status_code=error.status)


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _envelope_response(message: Any) -> JSONResponse:
    return JSONResponse(json.loads(message.model_dump_json()))


# ---------------------------------------------------------------------------
# Route handlers — closures over the gateway
# ---------------------------------------------------------------------------


def _make_enrollments_endpoint(gateway: DeviceGateway):
    """POST /v1/edge/enrollments — issue a single-use enrollment key."""

    async def enrollments(request: Request) -> Response:
        body = await _json_body(request)
        raw_key = await create_enrollment(
            gateway.store,
            device_type=str(body.get("device_type", "generic")),
            device_name=str(body.get("device_name", "")),
            capabilities=list(body.get("capabilities", []) or []),
            expires_in_seconds=int(body.get("expires_in_seconds", 3600)),
        )
        return JSONResponse({"enrollment_key": raw_key})

    return enrollments


def _make_enroll_endpoint(gateway: DeviceGateway):
    """POST /v1/edge/enroll — consume a key, issue device + credential."""

    async def enroll(request: Request) -> Response:
        body = await _json_body(request)
        key = str(body.get("enrollment_key", "") or "")
        if not key:
            return _error_to_response(
                AuthenticationFailedError("Missing enrollment_key")
            )
        try:
            device, raw_credential = await gateway.enroll(
                key, firmware_version=body.get("firmware_version")
            )
        except EdgeError as e:
            return _error_to_response(e)
        # The raw credential is returned exactly once, at enrollment.
        return JSONResponse(
            {
                "device_id": device.device_id,
                "entity_id": device.entity_id,
                "device_type": device.type,
                "name": device.name,
                "credential": raw_credential,
            }
        )

    return enroll


def _make_auth_endpoint(gateway: DeviceGateway):
    """POST /v1/edge/auth — credential → session (EDGE §18)."""

    async def auth(request: Request) -> Response:
        body = await _json_body(request)
        credential = _credential_from_request(request) or str(
            body.get("credential", "") or ""
        )
        device_id = str(body.get("device_id", "") or "")
        if not credential:
            return _error_to_response(
                AuthenticationFailedError("Missing device credential")
            )
        message = make_message(
            EdgeMessageType.AUTH,
            device_id=device_id,
            payload={"device_id": device_id, "credential": credential},
            trace_id=request.headers.get("x-trace-id"),
        )
        try:
            response = await gateway.handle_message(
                message.model_dump(), transport=TransportKind.HTTP
            )
        except EdgeError as e:
            return _error_to_response(e)
        return _envelope_response(response)

    return auth


def _make_device_endpoint(gateway: DeviceGateway, message_type: EdgeMessageType):
    """Shared factory for authenticated device → runtime endpoints."""

    async def handler(request: Request) -> Response:
        credential = _credential_from_request(request)
        if not credential:
            return _error_to_response(
                AuthenticationFailedError("Missing device credential")
            )
        body = await _json_body(request)
        try:
            ctx, _session = await gateway.connect(
                credential, transport=TransportKind.HTTP
            )
        except EdgeError as e:
            return _error_to_response(e)

        message = make_message(
            message_type,
            device_id=ctx.device_id,
            payload=body,
            trace_id=request.headers.get("x-trace-id"),
        )
        try:
            response = await gateway.handle_message(
                message.model_dump(),
                transport=TransportKind.HTTP,
                context=ctx,
            )
        except EdgeError as e:
            return _error_to_response(e)
        return _envelope_response(response)

    return handler


def _make_effects_endpoint(gateway: DeviceGateway):
    """GET /v1/edge/effects — poll pending effects (EDGE §34)."""

    async def effects(request: Request) -> Response:
        credential = _credential_from_request(request)
        if not credential:
            return _error_to_response(
                AuthenticationFailedError("Missing device credential")
            )
        try:
            ctx, _session = await gateway.connect(
                credential, transport=TransportKind.HTTP
            )
        except EdgeError as e:
            return _error_to_response(e)
        try:
            deliveries = await gateway.pending_effects(ctx.device_id, ctx)
        except EdgeError as e:
            return _error_to_response(e)
        return JSONResponse(
            {
                "effects": [
                    {
                        "type": "effect",
                        "effect_id": d.effect_id,
                        "execution_id": d.execution_id,
                        "device_id": d.device_id,
                        "capability": d.capability,
                        "payload": d.payload,
                        "status": d.status,
                    }
                    for d in deliveries
                ]
            }
        )

    return effects


def _make_effect_ack_endpoint(gateway: DeviceGateway):
    """POST /v1/edge/effects/{effect_id}/ack — acknowledge an effect (EDGE §27)."""

    async def ack(request: Request) -> Response:
        credential = _credential_from_request(request)
        if not credential:
            return _error_to_response(
                AuthenticationFailedError("Missing device credential")
            )
        body = await _json_body(request)
        effect_id = str(request.path_params.get("effect_id", ""))
        body.setdefault("effect_id", effect_id)
        try:
            ctx, _session = await gateway.connect(
                credential, transport=TransportKind.HTTP
            )
        except EdgeError as e:
            return _error_to_response(e)
        message = make_message(
            EdgeMessageType.EFFECT_ACK,
            device_id=ctx.device_id,
            payload=body,
            trace_id=request.headers.get("x-trace-id"),
        )
        try:
            response = await gateway.handle_message(
                message.model_dump(),
                transport=TransportKind.HTTP,
                context=ctx,
            )
        except EdgeError as e:
            return _error_to_response(e)
        return _envelope_response(response)

    return ack


# ---------------------------------------------------------------------------
# Route assembly
# ---------------------------------------------------------------------------


def build_edge_routes(gateway: DeviceGateway) -> list[Route]:
    """Build the /v1/edge route table for a Starlette app."""
    return [
        Route(
            "/v1/edge/enrollments",
            _make_enrollments_endpoint(gateway),
            methods=["POST"],
        ),
        Route("/v1/edge/enroll", _make_enroll_endpoint(gateway), methods=["POST"]),
        Route("/v1/edge/auth", _make_auth_endpoint(gateway), methods=["POST"]),
        Route(
            "/v1/edge/hello",
            _make_device_endpoint(gateway, EdgeMessageType.HELLO),
            methods=["POST"],
        ),
        Route(
            "/v1/edge/events",
            _make_device_endpoint(gateway, EdgeMessageType.EVENT),
            methods=["POST"],
        ),
        Route(
            "/v1/edge/state",
            _make_device_endpoint(gateway, EdgeMessageType.STATE_SYNC),
            methods=["POST"],
        ),
        Route(
            "/v1/edge/heartbeat",
            _make_device_endpoint(gateway, EdgeMessageType.HEARTBEAT),
            methods=["POST"],
        ),
        Route("/v1/edge/effects", _make_effects_endpoint(gateway), methods=["GET"]),
        Route(
            "/v1/edge/effects/{effect_id}/ack",
            _make_effect_ack_endpoint(gateway),
            methods=["POST"],
        ),
    ]


class EdgeHTTPRouter:
    """Bundles the gateway with its HTTP route table."""

    def __init__(self, gateway: DeviceGateway) -> None:
        self.gateway = gateway

    def routes(self) -> list[Route]:
        return build_edge_routes(self.gateway)
