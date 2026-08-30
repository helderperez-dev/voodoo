# Voodoo Edge Protocol v1

> Transport-independent message contract. HTTP and MQTT carry these
> envelopes verbatim; the runtime behavior is identical either way.

## Protocol identity

- **Name:** `voodoo-edge`
- **Version:** `1` (`voodoo-edge/v1`)
- **Wire format:** JSON (UTF-8)
- **Compatibility:** additive within v1; breaking changes require v2.
  V1 clients must never be silently broken.

The protocol uses only protocol-level primitives (string, integer, number,
boolean, array, object, ISO-8601 timestamps, opaque identifiers) — no
Python-specific types, no ORM structures — so a C++ ESP32 client can
consume it (EDGE §55).

## Message envelope

Every message is a flat JSON object:

```json
{
  "version": "1",
  "type": "event",
  "message_id": "msg_abc123",
  "device_id": "device_01j...",
  "timestamp": "2026-08-29T12:00:00+00:00",
  "payload": {},
  "correlation_id": null,
  "trace_id": null
}
```

| Field | Type | Required | Purpose |
|---|---|---|---|
| `version` | string | ✅ | Protocol version. Must be `"1"`. |
| `type` | string | ✅ | Message type (see below). |
| `message_id` | string | ✅ | Stable id — deduplication key for retries. |
| `device_id` | string | contextual | Sender device. Validated against the credential. |
| `timestamp` | string | ✅ | ISO-8601 UTC. |
| `payload` | object | ✅ | Type-specific body (validated per type). |
| `correlation_id` | string | optional | Links a response to its request. |
| `trace_id` | string | optional | Propagates observability across the flow. |

## Message types (v1)

### HELLO — device announces itself

**Direction:** device → runtime.

```json
{
  "type": "hello",
  "payload": {
    "device_id": "device_01j...",
    "device_type": "esp32",
    "protocol_version": "1",
    "capabilities": ["sensor.temperature.read", "relay.fan.control"],
    "firmware_version": "1.2.3"
  }
}
```

- **Validation:** authenticated context required.
- **Effect:** merges announced capabilities into the device's canonical set.
- **Idempotent:** yes — repeated HELLOs merge, never duplicate.

### AUTH — establish a session

**Direction:** device → runtime.

```json
{
  "type": "auth",
  "payload": {
    "device_id": "device_01j...",
    "credential": "vdk_...",
    "protocol_version": "1"
  }
}
```

- **Validation:** credential must exist, be ACTIVE, and bind to `device_id`
  (a claimed id without a matching credential is rejected).
- **Rejections** (machine-readable `AUTHENTICATION_FAILED`,
  `DEVICE_REVOKED`, `INVALID_PROTOCOL_VERSION`): invalid credential,
  expired credential, revoked device, unknown device, unsupported protocol.
- **Result:** a `session_id` the device includes in subsequent MQTT
  payloads. HTTP re-presents the credential header per request instead.

### STATE_SYNC — report versioned state

**Direction:** device → runtime.

```json
{
  "type": "state_sync",
  "payload": {
    "state": {"temperature": 31.4, "fan": true, "battery": 82},
    "state_version": 42
  }
}
```

- **Validation:** `state_version ≥ 0`; must be ≥ the stored version.
- **Idempotency:** equal version = accepted retry; lower version =
  `INVALID_STATE_VERSION` (stale state never overwrites newer).
- See [state-synchronization.md](state-synchronization.md).

### EVENT — publish a device event

**Direction:** device → runtime.

```json
{
  "type": "event",
  "payload": {
    "event_name": "temperature.changed",
    "event_payload": {"value": 31.4},
    "message_id": "msg_retry_safe"
  }
}
```

- **Validation:** `event_name` must be dot-namespaced lowercase
  (`temperature.changed`, `motion.detected`).
- **Idempotency:** duplicate `message_id` returns `{"status": "duplicate"}`
  without re-processing (protocol retries are safe).
- **Routing:** telemetry events (heartbeat) update state only; semantic
  events create an Intent `device:<event_name>` executed by the
  ExecutionEngine with actor `device:<device_id>`.

### EFFECT — runtime commands the device

**Direction:** runtime → device.

```json
{
  "type": "effect",
  "payload": {
    "effect_id": "effect_01j...",
    "execution_id": "exec_01j...",
    "device_id": "device_01j...",
    "capability": "relay.fan.control",
    "payload": {"state": "on"}
  }
}
```

- The runtime only submits effects whose capability the device advertises
  (enforced at the runtime boundary, EDGE §50).
- Delivered at-least-once; devices must treat `effect_id` as the
  idempotency key.

### EFFECT_ACK — device acknowledges

**Direction:** device → runtime.

```json
{
  "type": "effect_ack",
  "payload": {
    "effect_id": "effect_01j...",
    "execution_id": "exec_01j...",
    "status": "completed",
    "error": null
  }
}
```

- **Statuses:** `accepted` | `completed` | `failed` | `rejected`.
- Devices may only ack their own effects — cross-device acks are
  `AUTHORIZATION_FAILED`.

### HEARTBEAT — liveness

**Direction:** device → runtime.

```json
{
  "type": "heartbeat",
  "payload": {"state_version": 42, "uptime_seconds": 3600}
}
```

- Updates `last_seen_at` and session health.
- **Never creates an Execution** (EDGE §30).

## Error model

Errors use stable machine-readable codes (see the full table in
[http.md](http.md)):

```
AUTHENTICATION_FAILED | AUTHORIZATION_FAILED | DEVICE_NOT_FOUND
DEVICE_REVOKED | INVALID_MESSAGE | INVALID_PROTOCOL_VERSION
INVALID_CAPABILITY | INVALID_STATE_VERSION | DUPLICATE_MESSAGE
EFFECT_NOT_FOUND | EFFECT_EXPIRED | TRANSPORT_ERROR
```

Error bodies never contain credentials or authentication internals:

```json
{"error": {"code": "INVALID_STATE_VERSION", "message": "...", "detail": {...}}}
```

## Future message types (NOT in v1)

`GOODBYE`, `CAPABILITY_UPDATE`, `ERROR`, `COMMAND`, `CONFIG_UPDATE` —
reserved names; v1 implementations must reject them cleanly.
