import base64
import binascii
import hashlib
import hmac
import json
import secrets
import threading
import time
from typing import Any
from uuid import UUID, uuid4

from voodoo.config import AuthConfig, config
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

_JWT_ALGORITHM = "HS256"
_JWT_TYPE = "JWT"


class _TokenRevocations:
    """Bounded, process-local revocation state for Profile 1 sessions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, int] = {}

    def _purge(self, now: int) -> None:
        expired = [key for key, expiry in self._entries.items() if expiry <= now]
        for key in expired:
            self._entries.pop(key, None)

    def revoke(self, key: str, expiry: int, now: int) -> None:
        with self._lock:
            self._purge(now)
            if expiry <= now:
                return
            self._entries[key] = expiry
            limit = config.auth.jwt_revocation_max_entries
            if len(self._entries) > limit:
                oldest = sorted(self._entries, key=self._entries.__getitem__)
                for stale_key in oldest[: len(self._entries) - limit]:
                    self._entries.pop(stale_key, None)

    def contains(self, key: str, now: int) -> bool:
        with self._lock:
            self._purge(now)
            return key in self._entries

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_token_revocations = _TokenRevocations()


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
    if isinstance(expiry, bool) or not isinstance(expiry, int):
        raise ValueError("token expiry must be an integer number of seconds")
    if expiry == 0:
        raise ValueError("token expiry must not be zero")

    now = int(time.time())
    payload = data.copy()
    payload["iat"] = now
    payload.setdefault("jti", str(uuid4()))
    if "exp" not in payload:
        payload["exp"] = now + expiry
    if config.auth.jwt_issuer is not None:
        payload.setdefault("iss", config.auth.jwt_issuer)
    if config.auth.jwt_audience is not None:
        payload.setdefault("aud", config.auth.jwt_audience)

    header = {"alg": _JWT_ALGORITHM, "typ": _JWT_TYPE}

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
    except (binascii.Error, UnicodeError, ValueError):
        raise InvalidTokenError("Malformed token payload") from None
    if not isinstance(payload, dict):
        raise InvalidTokenError("Malformed token payload")
    return payload


def _decode_json_header(header_b64: str) -> dict[str, Any]:
    try:
        header = json.loads(_b64decode_str(header_b64).decode("utf-8"))
    except (binascii.Error, UnicodeError, ValueError):
        raise InvalidTokenError("Malformed token header") from None
    if not isinstance(header, dict):
        raise InvalidTokenError("Malformed token header")
    if header.get("alg") != _JWT_ALGORITHM or header.get("typ") != _JWT_TYPE:
        raise InvalidTokenError("Unsupported token algorithm or type")
    return header


def _validate_registered_claims(payload: dict[str, Any], auth_config: AuthConfig) -> None:
    issuer = auth_config.jwt_issuer
    if issuer is not None and payload.get("iss") != issuer:
        raise InvalidTokenError("Invalid token issuer")
    audience = auth_config.jwt_audience
    if audience is None:
        return
    token_audience = payload.get("aud")
    if isinstance(token_audience, str):
        valid = token_audience == audience
    elif isinstance(token_audience, list):
        valid = audience in token_audience and all(
            isinstance(value, str) for value in token_audience
        )
    else:
        valid = False
    if not valid:
        raise InvalidTokenError("Invalid token audience")


def _revocation_key(token: str, payload: dict[str, Any]) -> str:
    jti = payload.get("jti")
    if isinstance(jti, str) and jti:
        return f"jti:{jti}"
    return "token:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _subject_revocation_key(payload: dict[str, Any]) -> str | None:
    subject = payload.get("sub")
    if subject is None:
        subject = payload.get("id")
    if subject is None or isinstance(subject, (dict, list, set)):
        return None
    return f"subject:{subject}"


def _validate_time_claim(
    payload: dict[str, Any], claim: str, now: int, clock_skew: int
) -> None:
    if claim not in payload:
        return
    raw_value = payload[claim]
    # JWT NumericDate claims are JSON numbers. Voodoo emits integer seconds;
    # reject bools, strings, and fractional values instead of silently
    # truncating or accepting type-confused claims.
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise InvalidTokenError(f"Malformed token {claim} claim") from None
    value = raw_value
    if claim == "exp" and now > value + clock_skew:
        raise ExpiredTokenError("Token has expired")
    if claim == "nbf" and now < value - clock_skew:
        raise InvalidTokenError("Token not yet valid")
    if claim == "iat" and now < value - clock_skew:
        raise InvalidTokenError("Token issued-at time is in the future")


def decode_access_token(
    token: str,
    secret_key: str | None = None,
    *,
    auth_config: AuthConfig | None = None,
) -> dict[str, Any]:
    """Decode and validate an HMAC-SHA256 signed access token."""
    settings = auth_config or config.auth
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Missing or invalid token")

    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidTokenError("Invalid token format")

    header_b64, payload_b64, sig_b64 = parts
    _decode_json_header(header_b64)
    message = f"{header_b64}.{payload_b64}".encode()
    try:
        provided_sig = _b64decode_str(sig_b64)
    except (binascii.Error, UnicodeError, ValueError):
        raise InvalidTokenError("Corrupted token signature encoding") from None
    keys = [secret_key or settings.secret_key]
    if secret_key is None:
        keys.extend(settings.jwt_previous_secrets)
    valid_signature = any(
        secrets.compare_digest(
            hmac.new(key.encode("utf-8"), message, hashlib.sha256).digest(),
            provided_sig,
        )
        for key in keys
    )
    if not valid_signature:
        raise InvalidTokenError("Invalid token signature")

    payload = _decode_json_payload(payload_b64)
    now = int(time.time())
    clock_skew = settings.jwt_clock_skew_seconds
    _validate_time_claim(payload, "exp", now, clock_skew)
    _validate_time_claim(payload, "nbf", now, clock_skew)
    _validate_time_claim(payload, "iat", now, clock_skew)
    _validate_registered_claims(payload, settings)
    token_key = _revocation_key(token, payload)
    subject_key = _subject_revocation_key(payload)
    if _token_revocations.contains(token_key, now) or (
        subject_key is not None and _token_revocations.contains(subject_key, now)
    ):
        raise InvalidTokenError("Token has been revoked")
    return payload


def revoke_access_token(token: str, secret_key: str | None = None) -> None:
    """Revoke a valid token until its expiry without retaining its contents."""
    payload = decode_access_token(token, secret_key=secret_key)
    now = int(time.time())
    expiry = payload.get("exp")
    if not isinstance(expiry, int):
        expiry = now + config.auth.token_expiry_seconds
    _token_revocations.revoke(_revocation_key(token, payload), expiry, now)


def revoke_subject_sessions(subject: str | int, expires_at: int | None = None) -> None:
    """Invalidate tokens for one subject until a bounded expiry horizon."""
    now = int(time.time())
    expiry = expires_at if expires_at is not None else now + config.auth.token_expiry_seconds
    _token_revocations.revoke(f"subject:{subject}", expiry, now)


def clear_revoked_tokens() -> None:
    """Clear process-local revocation state when resetting a process/test."""
    _token_revocations.clear()
