"""Voodoo Edge — external device boundary for the Voodoo Runtime (Sprint 23).

Physical and distributed devices (ESP32, Raspberry Pi, robots, industrial
controllers) participate as first-class Voodoo Entities through the
versioned ``voodoo-edge/v1`` protocol over HTTP and MQTT transports.

There is **no** DeviceExecutionEngine: device-triggered work enters the
standard ExecutionEngine, device events use the standard event system,
and device state uses standard State semantics.

    from voodoo.edge import DeviceGateway, SQLiteDeviceStore

    store = SQLiteDeviceStore("data/devices.db")
    gateway = DeviceGateway(store, engine)
"""

from __future__ import annotations

from voodoo.edge.auth import (
    authenticate_device,
    consume_enrollment,
    create_enrollment,
    generate_device_credential,
    hash_device_credential,
    rotate_device_credential,
)
from voodoo.edge.errors import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    DeviceNotFoundError,
    DeviceRevokedError,
    DuplicateMessageError,
    EdgeError,
    EffectExpiredError,
    EffectNotFoundError,
    InvalidCapabilityError,
    InvalidMessageError,
    InvalidProtocolVersionError,
    InvalidStateVersionError,
    TransportError,
    error_response,
)
from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import (
    AuthenticatedDeviceContext,
    CredentialStatus,
    Device,
    DeviceCredential,
    DeviceEnrollment,
    DeviceSession,
    DeviceStatus,
    EnrollmentStatus,
    TransportKind,
)
from voodoo.edge.protocol import (
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    EdgeMessage,
    EdgeMessageType,
    EffectAckStatus,
    decode_message,
    encode_message,
    make_message,
)
from voodoo.edge.store import (
    DeviceStoreProtocol,
    EffectDelivery,
    InMemoryDeviceStore,
    SQLiteDeviceStore,
)

__all__ = [
    # Protocol identity
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    # Models
    "Device",
    "DeviceStatus",
    "DeviceCredential",
    "CredentialStatus",
    "DeviceEnrollment",
    "EnrollmentStatus",
    "DeviceSession",
    "AuthenticatedDeviceContext",
    "TransportKind",
    # Protocol
    "EdgeMessage",
    "EdgeMessageType",
    "EffectAckStatus",
    "make_message",
    "encode_message",
    "decode_message",
    # Store
    "DeviceStoreProtocol",
    "InMemoryDeviceStore",
    "SQLiteDeviceStore",
    "EffectDelivery",
    # Auth
    "authenticate_device",
    "consume_enrollment",
    "create_enrollment",
    "generate_device_credential",
    "hash_device_credential",
    "rotate_device_credential",
    # Gateway
    "DeviceGateway",
    # Errors
    "EdgeError",
    "error_response",
    "AuthenticationFailedError",
    "AuthorizationFailedError",
    "DeviceNotFoundError",
    "DeviceRevokedError",
    "DuplicateMessageError",
    "EffectExpiredError",
    "EffectNotFoundError",
    "InvalidCapabilityError",
    "InvalidMessageError",
    "InvalidProtocolVersionError",
    "InvalidStateVersionError",
    "TransportError",
]
