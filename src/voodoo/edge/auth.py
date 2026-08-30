"""Edge device authentication — credentials and enrollment (EDGE §9–§11).

Device authentication is deliberately separate from user authentication:
devices present dedicated ``vdk_`` credentials issued at enrollment,
never admin/user API keys. Only SHA-256 hashes are stored.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from voodoo.edge.errors import (
    AuthenticationFailedError,
    DeviceNotFoundError,
    DeviceRevokedError,
)
from voodoo.edge.models import (
    AuthenticatedDeviceContext,
    Device,
    DeviceCredential,
    DeviceEnrollment,
    DeviceSession,
    DeviceStatus,
    TransportKind,
    _iso_now,
)
from voodoo.edge.store import DeviceStoreProtocol

if TYPE_CHECKING:
    pass

__all__ = [
    "generate_device_credential",
    "hash_device_credential",
    "generate_enrollment_key",
    "hash_enrollment_key",
    "authenticate_device",
    "create_enrollment",
    "consume_enrollment",
    "rotate_device_credential",
]


# ---------------------------------------------------------------------------
# Credential generation & hashing
# ---------------------------------------------------------------------------


def generate_device_credential() -> tuple[str, str]:
    """Generate a device credential. Returns ``(raw_credential, hash)``.

    The raw credential is shown exactly once — at enrollment or rotation.
    Prefix ``vdk_`` (Voodoo Device Key) distinguishes device credentials
    from user API keys (``vd_live_``).
    """
    raw = f"vdk_{secrets.token_urlsafe(32)}"
    return raw, hash_device_credential(raw)


def hash_device_credential(credential: str) -> str:
    """SHA-256 hash for safe storage."""
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()


def generate_enrollment_key() -> tuple[str, str]:
    """Generate a single-use enrollment key. Returns ``(raw_key, hash)``."""
    raw = f"vde_{secrets.token_urlsafe(24)}"
    return raw, hash_device_credential(raw)


def hash_enrollment_key(key: str) -> str:
    """SHA-256 hash of an enrollment key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _parse_expires(expires_at: str | None) -> datetime | None:
    if expires_at is None:
        return None
    try:
        return datetime.fromisoformat(expires_at)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Enrollment (EDGE §10)
# ---------------------------------------------------------------------------


async def create_enrollment(
    store: DeviceStoreProtocol,
    *,
    device_type: str = "generic",
    device_name: str = "",
    capabilities: list[str] | None = None,
    expires_in_seconds: int = 3600,
) -> str:
    """Create a single-use, short-lived enrollment token.

    Returns the **raw enrollment key** — store it securely; it cannot be
    recovered from the runtime (only its hash is persisted).
    """
    raw_key, key_hash = generate_enrollment_key()
    expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in_seconds)).isoformat()
    enrollment = DeviceEnrollment(
        enrollment_key_hash=key_hash,
        device_type=device_type,
        device_name=device_name,
        capabilities=list(capabilities or []),
        expires_at=expires_at,
    )
    await store.create_enrollment(enrollment)
    return raw_key


async def consume_enrollment(
    store: DeviceStoreProtocol,
    enrollment_key: str,
    *,
    firmware_version: str | None = None,
) -> tuple[Device, str]:
    """Consume an enrollment key and issue device identity + credential.

    Validates: key exists, is PENDING, and not expired. On success the
    enrollment becomes CONSUMED (single-use), a Device entity is created,
    and a device credential is issued. Returns ``(device, raw_credential)``.
    """
    key_hash = hash_enrollment_key(enrollment_key)
    enrollment = await store.find_enrollment_by_hash(key_hash)
    if enrollment is None:
        raise AuthenticationFailedError("Unknown enrollment key")

    expires = _parse_expires(enrollment.expires_at)
    if expires is not None and datetime.now(UTC) > expires:
        raise AuthenticationFailedError("Enrollment key expired")

    # Single-use: only a PENDING enrollment can convert.
    consumed = await store.consume_enrollment(enrollment.enrollment_id)
    if not consumed:
        raise AuthenticationFailedError("Enrollment key already used or revoked")

    device = Device(
        type=enrollment.device_type,
        name=enrollment.device_name or f"{enrollment.device_type}-device",
        capabilities=list(enrollment.capabilities),
        metadata={"firmware_version": firmware_version} if firmware_version else {},
    )
    await store.register_device(device)

    raw_credential, credential_hash = generate_device_credential()
    await store.create_credential(
        DeviceCredential(
            device_id=device.device_id,
            credential_hash=credential_hash,
        )
    )
    return device, raw_credential


async def rotate_device_credential(store: DeviceStoreProtocol, device_id: str) -> str:
    """Rotate a device credential. Returns the new raw credential.

    The old credential is marked ROTATED (no longer valid); the device
    keeps operating with the new one.
    """
    old = await store.get_active_credential(device_id)
    if old is not None:
        await store.revoke_credential(old.credential_id)

    raw, credential_hash = generate_device_credential()
    await store.create_credential(
        DeviceCredential(
            device_id=device_id,
            credential_hash=credential_hash,
        )
    )
    return raw


# ---------------------------------------------------------------------------
# Authentication (EDGE §11)
# ---------------------------------------------------------------------------


async def authenticate_device(
    store: DeviceStoreProtocol,
    credential: str,
    *,
    claimed_device_id: str | None = None,
    transport: TransportKind = TransportKind.HTTP,
) -> tuple[AuthenticatedDeviceContext, DeviceSession]:
    """Authenticate a device credential and establish a session.

    The credential MUST bind to the claimed device — a message claiming
    ``device_id`` without a matching credential is rejected (EDGE §11).

    Returns ``(context, session)``. Raises:
    - ``AuthenticationFailedError`` — unknown/invalid credential
    - ``DeviceRevokedError`` — device has been revoked
    - ``DeviceNotFoundError`` — claimed device does not exist
    """
    credential_hash = hash_device_credential(credential)
    record = await store.find_credential_by_hash(credential_hash)
    if record is None:
        raise AuthenticationFailedError("Invalid device credential")

    # Never trust a claimed device_id without validating the binding.
    if claimed_device_id is not None and claimed_device_id != record.device_id:
        raise AuthenticationFailedError(
            "Credential does not belong to the claimed device"
        )

    device = await store.get_device(record.device_id)
    if device is None:
        raise DeviceNotFoundError(
            f"Credential references missing device '{record.device_id}'"
        )
    if device.status == DeviceStatus.REVOKED:
        raise DeviceRevokedError(f"Device '{device.device_id}' has been revoked")

    await store.mark_credential_used(record.credential_id)

    # Reconnect: invalidate any existing sessions for this device before
    # creating a new one.  The device transitions RECONNECTING → CONNECTED
    # so downstream observers see a clean lifecycle signal (EDGE §30).
    old_session_count = await store.delete_device_sessions(device.device_id)
    if old_session_count > 0:
        await store.update_device_status(device.device_id, DeviceStatus.RECONNECTING)

    session = DeviceSession(
        device_id=device.device_id,
        transport=transport,
        last_seen_at=_iso_now(),
    )
    await store.create_session(session)
    await store.update_device_status(device.device_id, DeviceStatus.CONNECTED)
    await store.update_last_seen(device.device_id)

    context = AuthenticatedDeviceContext(
        device_id=device.device_id,
        device_type=device.type,
        capabilities=list(device.capabilities),
        session_id=session.session_id,
        transport=transport,
        metadata=dict(device.metadata),
    )
    return context, session
