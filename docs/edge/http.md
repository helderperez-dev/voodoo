# Edge HTTP Transport

> REST endpoints under `/v1/edge/*`. Easy to exercise with curl and
> integration tests — the reference transport.
>
> **Sprint 23.1:** HTTP is fully **stateless** — no persistent sessions are
> created per request. Each request authenticates independently via the
> `X-Device-Credential` header. Only `/v1/edge/auth` creates a session (for
> explicit session-based flows).

## Authentication

Device credentials travel per-request in headers (separate from user auth):

```
X-Device-Credential: vdk_...
```

or

```
Authorization: Device vdk_...
```

Missing/invalid credentials on protected endpoints → `401` with
`AUTHENTICATION_FAILED`. Revoked devices → `401` (credential cascade-revoked).

**Stateless per-request auth:** Each HTTP request authenticates independently
via `gateway.authenticate_request()`. No session is created or stored. This
eliminates session leaks under high HTTP load.

## Endpoints

### POST /v1/edge/enrollments — issue an enrollment key

Runtime-operator endpoint. **Protected by admin token** when
`edge.enrollment_auth_required = True` (default). Pass the admin token in
the `X-Admin-Token` header:

```bash
curl -X POST http://localhost:8000/v1/edge/enrollments \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: <enrollment_admin_token>" \
  -d '{"device_type": "esp32", "capabilities": ["relay.fan.control"]}'
# → {"enrollment_key": "vde_..."}   (single-use, ~1h TTL)
```

Set `edge.enrollment_auth_required = false` in config to disable the guard
(for local development only).

### POST /v1/edge/enroll — consume the key

```bash
curl -X POST http://localhost:8000/v1/edge/enroll \
  -H "Content-Type: application/json" \
  -d '{"enrollment_key": "vde_...", "firmware_version": "1.0.0"}'
```

Response (**credential shown exactly once**):

```json
{
  "device_id": "device_01j...",
  "entity_id": "device:device_01j...",
  "device_type": "esp32",
  "name": "esp32-device",
  "credential": "vdk_..."
}
```

Errors: `401 AUTHENTICATION_FAILED` (unknown/expired/reused key).

### POST /v1/edge/auth — establish a session

```bash
curl -X POST http://localhost:8000/v1/edge/auth \
  -H "Content-Type: application/json" \
  -d '{"credential": "vdk_..."}'
```

Response envelope:

```json
{
  "type": "auth",
  "payload": {"session_id": "sess_...", "device_id": "device_...", "capabilities": [...]}
}
```

### POST /v1/edge/hello — announce capabilities

```bash
curl -X POST http://localhost:8000/v1/edge/hello \
  -H "X-Device-Credential: vdk_..." \
  -H "Content-Type: application/json" \
  -d '{"device_type": "esp32", "capabilities": ["display.write"]}'
```

### POST /v1/edge/events — publish an event

```bash
curl -X POST http://localhost:8000/v1/edge/events \
  -H "X-Device-Credential: vdk_..." \
  -H "Content-Type: application/json" \
  -d '{"event_name": "temperature.changed", "event_payload": {"value": 31.4}, "message_id": "msg_..."}'
```

Response includes the created execution id when the event triggers one:

```json
{"payload": {"status": "accepted", "event_name": "temperature.changed", "execution_id": "exec_..."}}
```

**Idempotency:** Include a `message_id` in the request body to enable
client-driven idempotency. The HTTP transport extracts it and passes it to
the protocol envelope. Duplicate `message_id` retries replay the original
response: `{"payload": {"status": "duplicate", ...}}` (200).

### POST /v1/edge/state — sync state

```bash
curl -X POST http://localhost:8000/v1/edge/state \
  -H "X-Device-Credential: vdk_..." \
  -H "Content-Type: application/json" \
  -d '{"state": {"temperature": 31.4}, "state_version": 42}'
```

Stale version → `409 INVALID_STATE_VERSION` with
`detail: {"incoming": 41, "current": 42}`.

### POST /v1/edge/heartbeat

```bash
curl -X POST http://localhost:8000/v1/edge/heartbeat \
  -H "X-Device-Credential: vdk_..." \
  -H "Content-Type: application/json" \
  -d '{"uptime_seconds": 42}'
# → {"payload": {"status": "ok", "state_version": 42}}
```

### GET /v1/edge/effects — poll pending effects

```bash
curl http://localhost:8000/v1/edge/effects \
  -H "X-Device-Credential: vdk_..."
```

```json
{
  "effects": [
    {
      "type": "effect",
      "effect_id": "effect_...",
      "execution_id": "exec_...",
      "device_id": "device_...",
      "capability": "relay.fan.control",
      "payload": {"state": "on"},
      "status": "delivered"
    }
  ]
}
```

Polling marks effects as delivered; each effect appears until acked
(delivery is at-least-once — treat `effect_id` as the idempotency key).

### POST /v1/edge/effects/{effect_id}/ack — acknowledge

```bash
curl -X POST http://localhost:8000/v1/edge/effects/effect_.../ack \
  -H "X-Device-Credential: vdk_..." \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

Statuses: `accepted` | `completed` | `failed` | `rejected`.
Unknown effect → `404 EFFECT_NOT_FOUND`; another device's effect → `403`.

## Status-code map

| Code | Error code |
|---|---|
| 400 | `INVALID_MESSAGE`, `INVALID_PROTOCOL_VERSION` |
| 401 | `AUTHENTICATION_FAILED` |
| 403 | `AUTHORIZATION_FAILED`, `DEVICE_REVOKED`, `INVALID_CAPABILITY` |
| 404 | `DEVICE_NOT_FOUND`, `EFFECT_NOT_FOUND` |
| 409 | `INVALID_STATE_VERSION` |
| 410 | `EFFECT_EXPIRED` |
| 502 | `TRANSPORT_ERROR` |

## Retry semantics

- All device → runtime messages are idempotent by `message_id` (events) or
  natural compare-and-swap (state) — retry freely on timeout.
- Effect polling is safe to repeat; only ACK transitions state.
- The runtime never assumes a delivered-then-acked effect "exactly once" —
  see [reliability.md](reliability.md).
