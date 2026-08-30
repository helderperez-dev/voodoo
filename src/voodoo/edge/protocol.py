"""Voodoo Edge Protocol v1 — transport-independent message schemas (EDGE §14–§16, §54).

The protocol is a stable external contract (``voodoo-edge/v1``) consumable
by non-Python clients (ESP32 C++). Messages are flat, JSON-friendly, and
use only protocol-level primitives — string, integer, number, boolean,
array, object, timestamp, identifier (EDGE §55).

The same logical message produces the same runtime behavior over HTTP
and MQTT (EDGE §36). Transports carry these envelopes verbatim.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from voodoo.edge.errors import InvalidMessageError, InvalidProtocolVersionError

__all__ = [
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "EdgeMessageType",
    "EffectAckStatus",
    "EdgeMessage",
    "HelloPayload",
    "AuthPayload",
    "EventPayload",
    "StateSyncPayload",
    "EffectPayload",
    "EffectAckPayload",
    "HeartbeatPayload",
    "make_message",
    "encode_message",
    "decode_message",
    "validate_protocol_version",
]


# ---------------------------------------------------------------------------
# Protocol identity
# ---------------------------------------------------------------------------

PROTOCOL_NAME = "voodoo-edge"
PROTOCOL_VERSION = "1"
SUPPORTED_PROTOCOL_VERSIONS = ("1",)

_EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


# ---------------------------------------------------------------------------
# Message types (EDGE §16)
# ---------------------------------------------------------------------------


class EdgeMessageType(StrEnum):
    """The seven v1 message types."""

    HELLO = "hello"
    AUTH = "auth"
    STATE_SYNC = "state_sync"
    EVENT = "event"
    EFFECT = "effect"
    EFFECT_ACK = "effect_ack"
    HEARTBEAT = "heartbeat"


class EffectAckStatus(StrEnum):
    """Acknowledgement statuses (EDGE §27) — consistent with Voodoo
    lifecycle vocabulary (accepted ≈ authorized, completed ≈ succeeded)."""

    ACCEPTED = "accepted"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_message_id() -> str:
    return f"msg_{uuid4().hex[:20]}"


# ---------------------------------------------------------------------------
# Payload schemas — one per message type
# ---------------------------------------------------------------------------


class HelloPayload(BaseModel):
    """Device announcement (EDGE §17). device → runtime."""

    device_id: str = ""
    device_type: str = "generic"
    protocol_version: str = PROTOCOL_VERSION
    capabilities: list[str] = Field(default_factory=list)
    firmware_version: str | None = None


class AuthPayload(BaseModel):
    """Credential presentation (EDGE §18). device → runtime."""

    device_id: str = ""
    credential: str
    protocol_version: str = PROTOCOL_VERSION


class EventPayload(BaseModel):
    """Device event publication (EDGE §19). device → runtime."""

    event_name: str
    event_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        if not _EVENT_NAME_RE.match(v):
            raise ValueError(
                f"event_name '{v}' must be dot-namespaced lowercase "
                "(e.g. 'temperature.changed')"
            )
        return v


class StateSyncPayload(BaseModel):
    """State report with monotonic version (EDGE §22). device → runtime."""

    state: dict[str, Any] = Field(default_factory=dict)
    state_version: int = Field(ge=0)


class EffectPayload(BaseModel):
    """Effect targeting a device (EDGE §25). runtime → device."""

    effect_id: str
    execution_id: str
    device_id: str
    capability: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EffectAckPayload(BaseModel):
    """Acknowledgement of a received effect (EDGE §27). device → runtime."""

    effect_id: str
    execution_id: str = ""
    status: EffectAckStatus
    error: str | None = None


class HeartbeatPayload(BaseModel):
    """Liveness signal (EDGE §30). device → runtime. Never triggers
    an Execution — updates telemetry only."""

    state_version: int | None = Field(default=None, ge=0)
    uptime_seconds: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Canonical envelope (EDGE §15)
# ---------------------------------------------------------------------------


class EdgeMessage(BaseModel):
    """The canonical transport-independent message envelope.

    Every field is a protocol-level primitive. HTTP requests carry the
    envelope as the JSON body; MQTT carries it as the topic payload.
    """

    version: str = PROTOCOL_VERSION
    type: EdgeMessageType
    message_id: str = Field(default_factory=_new_message_id)
    device_id: str = ""
    timestamp: str = Field(default_factory=_now_iso)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    trace_id: str | None = None

    @field_validator("version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ValueError(f"Unsupported protocol version '{v}'")
        return v

    def typed_payload(self) -> BaseModel:
        """Return the payload validated against this message type's schema."""
        model = PAYLOAD_FOR_TYPE[self.type]
        try:
            return model.model_validate(self.payload)
        except Exception as e:  # noqa: BLE001 — normalize into EdgeError
            raise InvalidMessageError(
                f"Invalid payload for '{self.type.value}' message: {e}"
            ) from e


PAYLOAD_FOR_TYPE: dict[EdgeMessageType, type[BaseModel]] = {
    EdgeMessageType.HELLO: HelloPayload,
    EdgeMessageType.AUTH: AuthPayload,
    EdgeMessageType.EVENT: EventPayload,
    EdgeMessageType.STATE_SYNC: StateSyncPayload,
    EdgeMessageType.EFFECT: EffectPayload,
    EdgeMessageType.EFFECT_ACK: EffectAckPayload,
    EdgeMessageType.HEARTBEAT: HeartbeatPayload,
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_protocol_version(version: str) -> None:
    """Raise ``InvalidProtocolVersionError`` for unsupported versions."""
    if version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise InvalidProtocolVersionError(
            f"Protocol version '{version}' is not supported; "
            f"supported: {', '.join(SUPPORTED_PROTOCOL_VERSIONS)}",
            detail={"supported": list(SUPPORTED_PROTOCOL_VERSIONS)},
        )


def make_message(
    type_: EdgeMessageType | str,
    *,
    device_id: str = "",
    payload: dict[str, Any] | None = None,
    message_id: str | None = None,
    correlation_id: str | None = None,
    trace_id: str | None = None,
) -> EdgeMessage:
    """Build a canonical envelope (runtime → device responses)."""
    if isinstance(type_, str):
        type_ = EdgeMessageType(type_)
    return EdgeMessage(
        type=type_,
        device_id=device_id,
        payload=payload or {},
        message_id=message_id or _new_message_id(),
        correlation_id=correlation_id,
        trace_id=trace_id,
    )


def encode_message(message: EdgeMessage) -> str:
    """Serialize an envelope to a JSON wire string."""
    return message.model_dump_json()


def decode_message(data: str | bytes | dict[str, Any]) -> EdgeMessage:
    """Decode and validate an incoming envelope.

    Raises ``InvalidMessageError`` for malformed JSON or schema
    violations, and ``InvalidProtocolVersionError`` for bad versions —
    no external input reaches runtime objects unvalidated (EDGE §53).
    """
    if isinstance(data, (str, bytes)):
        try:
            raw = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise InvalidMessageError(f"Malformed JSON: {e}") from e
    else:
        raw = data
    if not isinstance(raw, dict):
        raise InvalidMessageError("Message must be a JSON object")
    try:
        return EdgeMessage.model_validate(raw)
    except Exception as e:  # noqa: BLE001 — normalize into EdgeError
        msg = str(e)
        if "Unsupported protocol version" in msg:
            raise InvalidProtocolVersionError(
                f"Unsupported protocol version: {msg}"
            ) from e
        raise InvalidMessageError(f"Invalid message: {msg}") from e
