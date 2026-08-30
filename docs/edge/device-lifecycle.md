# Edge Device Lifecycle

> Device states, sessions, and reconnect semantics (EDGE §7, §31, §45).

## Two orthogonal lifecycles

**Entity validity** (is this device a valid Voodoo Entity?) is separate
from **connection status** (is it talking to us right now?). A
disconnected device remains a full entity with state, capabilities, and
history.

```
REGISTERED ──► CONNECTED ◄──► DISCONNECTED
                   │                │
                   │           RECONNECTING
                   ▼
               REVOKED  (terminal — can never authenticate)
```

| State | Meaning |
|---|---|
| `REGISTERED` | Enrolled; has identity + credential. Never connected yet. |
| `AUTHENTICATING` | Presenting a credential (transient). |
| `CONNECTED` | Authenticated session active. |
| `DISCONNECTED` | Session ended; **entity remains valid** and can reconnect. |
| `RECONNECTING` | Device-side flag while re-establishing a session. |
| `REVOKED` | Terminal. Credentials cascade-revoked; authentication impossible. |

A device cycles CONNECTED ⇄ DISCONNECTED freely. REVOKED is one-way.

## Enrollment → first connection

```
POST /v1/edge/enrollments      (runtime operator)
   └─ enrollment_key vde_...   (single-use, ~1h)

POST /v1/edge/enroll           (device)
   ├─ device_id device_...
   └─ credential vdk_...       (shown exactly once)

POST /v1/edge/auth             (device, each HTTP request re-presents
   └─ AuthenticatedDeviceContext + DeviceSession
```

## Sessions (EDGE §31)

A session is **transport/runtime connection state — not an Entity, not an
Execution**:

```
DeviceSession: session_id · device_id · transport · connected_at ·
               last_seen_at · protocol_version
```

- HTTP: credential validated per request; each validation creates a fresh
  session record (lightweight — no per-request DB transaction beyond the
  session insert).
- MQTT: one AUTH establishes a session; subsequent envelope payloads carry
  `"session_id"`, which the gateway **re-binds to the same device** on
  every message. A session can never act for a different device.

## Heartbeat (EDGE §30)

Heartbeats update `last_seen_at` and session health. They **never create
Executions** — heartbeat is telemetry, not compute.

## Reconnect (EDGE §45, tested)

```
connected ──► event ──► disconnect ──► [runtime keeps the entity,
      state, capabilities, pending effects] ──► reconnect
      ──► same device_id (NO duplicate entity) ──► state sync resumes
```

Guarantees:

- Reconnection **never duplicates the device entity** (tested).
- Pending effects queued while offline are delivered after reconnect
  (HTTP poll / next MQTT session).
- State synchronization resumes with the stored `state_version`; a device
  re-reporting an older version gets `INVALID_STATE_VERSION` and must
  re-sync (see [state-synchronization.md](state-synchronization.md)).

## Revocation (EDGE §49, tested)

`revoke_device()` → status REVOKED + all credentials revoked + live
sessions dropped. Any later authentication attempt fails with
`AUTHENTICATION_FAILED` (cascade-revoked credential) — and even a
hypothetically-active credential fails with `DEVICE_REVOKED` status
enforcement (defense in depth, tested).

## Operator surface

```python
from voodoo.edge import DeviceGateway

await gateway.revoke_device("device_01j...")  # terminal
await gateway.disconnect("sess_...")  # graceful session end
devices = await gateway.store.list_devices()  # inventory
```
