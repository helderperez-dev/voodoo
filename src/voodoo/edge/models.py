"""Edge device models — identity, credentials, enrollment, sessions (Sprint 23).

A Device is a first-class Voodoo Entity: it holds identity, capabilities,
state, and participates in Executions exactly like agents, workers, and
humans. There is no DeviceExecutionEngine — device-triggered work flows
through the standard ExecutionEngine (EDGE §6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "DeviceStatus",
    "CredentialStatus",
    "EnrollmentStatus",
    "TransportKind",
    "Device",
    "DeviceCredential",
    "DeviceEnrollment",
    "DeviceSession",
    "AuthenticatedDeviceContext",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeviceStatus(StrEnum):
    """Connection-aware device lifecycle (EDGE §7).

    Connection status is tracked separately from entity validity: a
    REVOKED device can never authenticate again, while a DISCONNECTED
    device remains a valid entity.
    """

    REGISTERED = "registered"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    REVOKED = "revoked"


class CredentialStatus(StrEnum):
    """Lifecycle of a device credential."""

    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"


class EnrollmentStatus(StrEnum):
    """Lifecycle of a device enrollment token."""

    PENDING = "pending"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class TransportKind(StrEnum):
    """Edge transport types (EDGE §33)."""

    HTTP = "http"
    MQTT = "mqtt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _new_device_id() -> str:
    """Device IDs use the ``device_`` prefix + UUID (EDGE §8)."""
    return f"device_{uuid4().hex[:24]}"


# ---------------------------------------------------------------------------
# Device — first-class Entity
# ---------------------------------------------------------------------------


@dataclass
class Device:
    """A Device is an Entity with identity, state, and capabilities.

    Parameters
    ----------
    device_id:
        Globally unique identifier (``device_<hex>``). Auto-generated if
        not provided. MAC addresses live in ``metadata`` — never as the
        canonical identity (EDGE §8).
    entity_id:
        Entity reference (``device:<device_id>``) linking the device
        into the general Entity model.
    type:
        Device type (``"esp32"``, ``"rpi"``, ``"robot"``...).
    name:
        Human-readable display name.
    capabilities:
        Canonical capability names this device advertises (EDGE §13).
        Registration is separate from authorization — declaring
        ``relay.control`` does not grant it.
    state:
        Last reported device state (reported via STATE_SYNC).
    state_version:
        Monotonic state version — stale writes are rejected (EDGE §23).
    status:
        Connection-aware lifecycle status.
    metadata:
        Arbitrary key-value metadata (firmware, MAC, location...).
    """

    device_id: str = field(default_factory=_new_device_id)
    entity_id: str = ""
    type: str = "generic"
    name: str = ""
    capabilities: list[str] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    state_version: int = 0
    status: DeviceStatus = DeviceStatus.REGISTERED
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_iso_now)
    updated_at: str = field(default_factory=_iso_now)
    last_seen_at: str | None = None

    def __post_init__(self) -> None:
        if not self.entity_id:
            self.entity_id = f"device:{self.device_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain, JSON-safe dict."""
        return {
            "device_id": self.device_id,
            "entity_id": self.entity_id,
            "type": self.type,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "state": dict(self.state),
            "state_version": self.state_version,
            "status": self.status.value,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_seen_at": self.last_seen_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Device:
        """Deserialize from a plain dict."""
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "status" in kwargs and isinstance(kwargs["status"], str):
            kwargs["status"] = DeviceStatus(kwargs["status"])
        return cls(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Device credential
# ---------------------------------------------------------------------------


@dataclass
class DeviceCredential:
    """A device-specific credential (EDGE §9).

    Only the SHA-256 hash is persisted — the raw credential is returned
    exactly once at enrollment/rotation and is never logged, stored in
    telemetry, or exposed through device state.
    """

    credential_id: str = field(default_factory=lambda: f"cred_{uuid4().hex[:20]}")
    device_id: str = ""
    credential_hash: str = ""
    status: CredentialStatus = CredentialStatus.ACTIVE
    created_at: str = field(default_factory=_iso_now)
    expires_at: str | None = None
    revoked_at: str | None = None
    last_used_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "credential_id": self.credential_id,
            "device_id": self.device_id,
            "credential_hash": self.credential_hash,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "last_used_at": self.last_used_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceCredential:
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "status" in kwargs and isinstance(kwargs["status"], str):
            kwargs["status"] = CredentialStatus(kwargs["status"])
        return cls(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


@dataclass
class DeviceEnrollment:
    """A single-use, short-lived enrollment token (EDGE §10).

    Flow: the Runtime creates an enrollment (returning the raw key once),
    an external device presents the key, the runtime consumes it and
    issues a device identity + long-lived device credential.
    """

    enrollment_id: str = field(default_factory=lambda: f"enr_{uuid4().hex[:20]}")
    enrollment_key_hash: str = ""
    device_type: str = "generic"
    device_name: str = ""
    capabilities: list[str] = field(default_factory=list)
    status: EnrollmentStatus = EnrollmentStatus.PENDING
    created_at: str = field(default_factory=_iso_now)
    expires_at: str | None = None
    consumed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enrollment_id": self.enrollment_id,
            "enrollment_key_hash": self.enrollment_key_hash,
            "device_type": self.device_type,
            "device_name": self.device_name,
            "capabilities": list(self.capabilities),
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "consumed_at": self.consumed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceEnrollment:
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "status" in kwargs and isinstance(kwargs["status"], str):
            kwargs["status"] = EnrollmentStatus(kwargs["status"])
        return cls(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Device session — transport state, NOT an Entity/Execution (EDGE §31)
# ---------------------------------------------------------------------------


@dataclass
class DeviceSession:
    """Lightweight transport session for a connected device."""

    session_id: str = field(default_factory=lambda: f"sess_{uuid4().hex[:20]}")
    device_id: str = ""
    transport: TransportKind = TransportKind.HTTP
    connected_at: str = field(default_factory=_iso_now)
    last_seen_at: str = field(default_factory=_iso_now)
    protocol_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "device_id": self.device_id,
            "transport": self.transport.value,
            "connected_at": self.connected_at,
            "last_seen_at": self.last_seen_at,
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceSession:
        kwargs = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "transport" in kwargs and isinstance(kwargs["transport"], str):
            kwargs["transport"] = TransportKind(kwargs["transport"])
        return cls(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Authenticated device context (EDGE §11)
# ---------------------------------------------------------------------------


@dataclass
class AuthenticatedDeviceContext:
    """Result of device authentication — attached to every device request.

    A device_id from a message body is never trusted on its own; the
    credential must validate AND bind to that exact device.
    """

    device_id: str
    device_type: str = "generic"
    capabilities: list[str] = field(default_factory=list)
    session_id: str = ""
    transport: TransportKind = TransportKind.HTTP
    authenticated_at: str = field(default_factory=_iso_now)
    metadata: dict[str, Any] = field(default_factory=dict)
