import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from uuid import UUID

from voodoo.config import config
from voodoo.core.errors import AuthError as _VoodooAuthError


class AuthError(_VoodooAuthError):
    """Base exception for authentication errors (part of the VoodooError tree)."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class InvalidCredentialsError(AuthError):
    pass


class ExpiredTokenError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


class PermissionDeniedError(AuthError):
    def __init__(self, message: str = "Permission denied", status_code: int = 403):
        super().__init__(message, status_code=status_code)


# =========================================================================
# JWT / HMAC-SHA256 Signed Access Tokens
# =========================================================================


def _b64encode_str(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode_str(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _json_default(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def create_access_token(
    data: dict[str, Any],
    expires_delta_seconds: int | None = None,
    secret_key: str | None = None,
) -> str:
    """
    Creates an HMAC-SHA256 signed access token (JWT format).
    """
    secret = secret_key or config.auth.secret_key
    expiry = (
        expires_delta_seconds
        if expires_delta_seconds is not None
        else config.auth.token_expiry_seconds
    )

    now = int(time.time())
    payload = data.copy()
    payload["iat"] = now
    if "exp" not in payload and expiry is not None and expiry != 0:
        payload["exp"] = now + expiry

    header = {"alg": "HS256", "typ": "JWT"}

    header_b64 = _b64encode_str(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_b64 = _b64encode_str(
        json.dumps(payload, separators=(",", ":"), default=_json_default).encode(
            "utf-8"
        )
    )

    message = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    sig_b64 = _b64encode_str(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _decode_json_payload(payload_b64: str) -> dict[str, Any]:
    try:
        payload = json.loads(_b64decode_str(payload_b64).decode("utf-8"))
    except Exception:
        raise InvalidTokenError("Malformed token payload") from None
    if not isinstance(payload, dict):
        raise InvalidTokenError("Malformed token payload")
    return payload


def _validate_time_claim(payload: dict[str, Any], claim: str, now: int) -> None:
    if claim not in payload:
        return
    try:
        value = int(payload[claim])
    except (TypeError, ValueError):
        raise InvalidTokenError(f"Malformed token {claim} claim") from None
    if claim == "exp" and now > value:
        raise ExpiredTokenError("Token has expired")
    if claim == "nbf" and now < value:
        raise InvalidTokenError("Token not yet valid")


def decode_access_token(token: str, secret_key: str | None = None) -> dict[str, Any]:
    """Decode and validate an HMAC-SHA256 signed access token."""
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Missing or invalid token")

    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidTokenError("Invalid token format")

    header_b64, payload_b64, sig_b64 = parts
    secret = secret_key or config.auth.secret_key
    message = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    try:
        provided_sig = _b64decode_str(sig_b64)
    except Exception:
        raise InvalidTokenError("Corrupted token signature encoding") from None
    if not secrets.compare_digest(expected_sig, provided_sig):
        raise InvalidTokenError("Invalid token signature")

    payload = _decode_json_payload(payload_b64)
    now = int(time.time())
    _validate_time_claim(payload, "exp", now)
    _validate_time_claim(payload, "nbf", now)
    return payload
