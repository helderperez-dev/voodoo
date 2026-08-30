"""Edge protocol tests — Phase 2: schemas, encoding, validation (Sprint 23)."""

from __future__ import annotations

import json

import pytest

from voodoo.edge.errors import (
    InvalidMessageError,
    InvalidProtocolVersionError,
    error_response,
)
from voodoo.edge.protocol import (
    PROTOCOL_VERSION,
    EdgeMessage,
    EdgeMessageType,
    EffectAckStatus,
    decode_message,
    encode_message,
    make_message,
    validate_protocol_version,
)

# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class TestEdgeMessage:
    def test_defaults(self):
        msg = EdgeMessage(type=EdgeMessageType.HEARTBEAT)
        assert msg.version == PROTOCOL_VERSION
        assert msg.message_id.startswith("msg_")
        assert msg.timestamp
        assert msg.payload == {}

    def test_encode_decode_roundtrip(self):
        msg = make_message(
            EdgeMessageType.EVENT,
            device_id="device_123",
            payload={
                "event_name": "temperature.changed",
                "event_payload": {"value": 31.4},
            },
            correlation_id="corr_1",
            trace_id="trace_9",
        )
        wire = encode_message(msg)
        assert isinstance(wire, str)
        restored = decode_message(wire)
        assert restored.type is EdgeMessageType.EVENT
        assert restored.device_id == "device_123"
        assert restored.payload["event_name"] == "temperature.changed"
        assert restored.correlation_id == "corr_1"
        assert restored.trace_id == "trace_9"

    def test_decode_from_dict(self):
        raw = {
            "version": "1",
            "type": "heartbeat",
            "message_id": "msg_x",
            "device_id": "device_1",
            "payload": {"uptime_seconds": 5},
        }
        msg = decode_message(raw)
        assert msg.type is EdgeMessageType.HEARTBEAT

    def test_unknown_version_rejected(self):
        raw = json.dumps({"version": "99", "type": "heartbeat", "payload": {}})
        with pytest.raises(InvalidProtocolVersionError):
            decode_message(raw)

    def test_malformed_json_rejected(self):
        with pytest.raises(InvalidMessageError):
            decode_message("{not json")

    def test_non_object_rejected(self):
        with pytest.raises(InvalidMessageError):
            decode_message("[1, 2, 3]")

    def test_unknown_type_rejected(self):
        raw = json.dumps({"version": "1", "type": "goodbye", "payload": {}})
        with pytest.raises(InvalidMessageError):
            decode_message(raw)


# ---------------------------------------------------------------------------
# Typed payloads
# ---------------------------------------------------------------------------


class TestPayloads:
    def test_hello_payload(self):
        msg = make_message(
            EdgeMessageType.HELLO,
            payload={
                "device_id": "device_1",
                "device_type": "esp32",
                "protocol_version": "1",
                "capabilities": ["relay.control"],
                "firmware_version": "1.2.3",
            },
        )
        payload = msg.typed_payload()
        assert payload.device_type == "esp32"
        assert payload.firmware_version == "1.2.3"

    def test_event_payload_requires_valid_name(self):
        msg = make_message(
            EdgeMessageType.EVENT,
            payload={"event_name": "BAD NAME", "event_payload": {}},
        )
        with pytest.raises(InvalidMessageError):
            msg.typed_payload()

    def test_state_sync_requires_non_negative_version(self):
        msg = make_message(
            EdgeMessageType.STATE_SYNC,
            payload={"state": {}, "state_version": -1},
        )
        with pytest.raises(InvalidMessageError):
            msg.typed_payload()

    def test_effect_ack_statuses(self):
        assert {s.value for s in EffectAckStatus} == {
            "accepted",
            "completed",
            "failed",
            "rejected",
        }

    def test_invalid_payload_shape(self):
        msg = make_message(
            EdgeMessageType.EFFECT_ACK,
            payload={"effect_id": "e1"},  # missing status
        )
        with pytest.raises(InvalidMessageError):
            msg.typed_payload()


# ---------------------------------------------------------------------------
# Validation & error model
# ---------------------------------------------------------------------------


class TestValidation:
    def test_validate_protocol_version_ok(self):
        validate_protocol_version("1")

    def test_validate_protocol_version_rejects(self):
        with pytest.raises(InvalidProtocolVersionError):
            validate_protocol_version("2")

    def test_error_response_shape(self):
        err = InvalidProtocolVersionError("bad", detail={"supported": ["1"]})
        body = error_response(err)
        assert body["error"]["code"] == "INVALID_PROTOCOL_VERSION"
        assert body["error"]["detail"] == {"supported": ["1"]}
