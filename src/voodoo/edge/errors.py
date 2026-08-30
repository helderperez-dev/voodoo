"""Edge error hierarchy — machine-readable protocol errors (EDGE §52).

Every error carries a stable ``code`` string from the Edge Protocol error
taxonomy so non-Python clients (ESP32 C++) can branch without parsing
human-readable messages.
"""

from __future__ import annotations

from typing import Any

from voodoo.core.errors import VoodooError

__all__ = [
    "EdgeErrorCode",
    "EdgeError",
    "AuthenticationFailedError",
    "AuthorizationFailedError",
    "DeviceNotFoundError",
    "DeviceRevokedError",
    "InvalidMessageError",
    "InvalidProtocolVersionError",
    "InvalidCapabilityError",
    "InvalidStateVersionError",
    "DuplicateMessageError",
    "EffectNotFoundError",
    "EffectExpiredError",
    "TransportError",
    "HTTP_STATUS",
    "error_response",
]


# ---------------------------------------------------------------------------
# Error codes — stable protocol contract (EDGE §52)
# ---------------------------------------------------------------------------


class EdgeErrorCode:
    """Stable string codes — part of the voodoo-edge/v1 contract."""

    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    DEVICE_REVOKED = "DEVICE_REVOKED"
    INVALID_MESSAGE = "INVALID_MESSAGE"
    INVALID_PROTOCOL_VERSION = "INVALID_PROTOCOL_VERSION"
    INVALID_CAPABILITY = "INVALID_CAPABILITY"
    INVALID_STATE_VERSION = "INVALID_STATE_VERSION"
    DUPLICATE_MESSAGE = "DUPLICATE_MESSAGE"
    EFFECT_NOT_FOUND = "EFFECT_NOT_FOUND"
    EFFECT_EXPIRED = "EFFECT_EXPIRED"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"


# HTTP status mapping used by the HTTP transport.
HTTP_STATUS: dict[str, int] = {
    EdgeErrorCode.AUTHENTICATION_FAILED: 401,
    EdgeErrorCode.AUTHORIZATION_FAILED: 403,
    EdgeErrorCode.DEVICE_NOT_FOUND: 404,
    EdgeErrorCode.DEVICE_REVOKED: 403,
    EdgeErrorCode.INVALID_MESSAGE: 400,
    EdgeErrorCode.INVALID_PROTOCOL_VERSION: 400,
    EdgeErrorCode.INVALID_CAPABILITY: 403,
    EdgeErrorCode.INVALID_STATE_VERSION: 409,
    EdgeErrorCode.DUPLICATE_MESSAGE: 200,  # idempotent success, not an error for the client
    EdgeErrorCode.EFFECT_NOT_FOUND: 404,
    EdgeErrorCode.EFFECT_EXPIRED: 410,
    EdgeErrorCode.TRANSPORT_ERROR: 502,
}


class EdgeError(VoodooError):
    """Base class for all Edge Protocol errors.

    ``code`` is a stable string from :class:`EdgeErrorCode`; ``status``
    carries the suggested HTTP status; ``detail`` is machine-readable
    context (never contains secrets).
    """

    code: str = EdgeErrorCode.INVALID_MESSAGE
    status: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        self.detail: dict[str, Any] = detail or {}


# ---------------------------------------------------------------------------
# Concrete errors
# ---------------------------------------------------------------------------


class AuthenticationFailedError(EdgeError):
    code = EdgeErrorCode.AUTHENTICATION_FAILED
    status = 401


class AuthorizationFailedError(EdgeError):
    code = EdgeErrorCode.AUTHORIZATION_FAILED
    status = 403


class DeviceNotFoundError(EdgeError):
    code = EdgeErrorCode.DEVICE_NOT_FOUND
    status = 404


class DeviceRevokedError(EdgeError):
    code = EdgeErrorCode.DEVICE_REVOKED
    status = 403


class InvalidMessageError(EdgeError):
    code = EdgeErrorCode.INVALID_MESSAGE
    status = 400


class InvalidProtocolVersionError(EdgeError):
    code = EdgeErrorCode.INVALID_PROTOCOL_VERSION
    status = 400


class InvalidCapabilityError(EdgeError):
    code = EdgeErrorCode.INVALID_CAPABILITY
    status = 403


class InvalidStateVersionError(EdgeError):
    code = EdgeErrorCode.INVALID_STATE_VERSION
    status = 409


class DuplicateMessageError(EdgeError):
    code = EdgeErrorCode.DUPLICATE_MESSAGE
    status = 200


class EffectNotFoundError(EdgeError):
    code = EdgeErrorCode.EFFECT_NOT_FOUND
    status = 404


class EffectExpiredError(EdgeError):
    code = EdgeErrorCode.EFFECT_EXPIRED
    status = 410


class TransportError(EdgeError):
    code = EdgeErrorCode.TRANSPORT_ERROR
    status = 502


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def error_response(error: EdgeError) -> dict[str, Any]:
    """Serialize an error into the canonical machine-readable body."""
    body: dict[str, Any] = {
        "error": {
            "code": error.code,
            "message": error.message,
        }
    }
    if error.detail:
        body["error"]["detail"] = error.detail
    return body
