# Edge Device Lifecycle

> Device states, sessions, and reconnect semantics (EDGE §7, §31, §45).
>
> **Sprint 23.1:** Reconnect semantics hardened — old sessions are
> invalidated on re-auth, device transitions through RECONNECTING → CONNECTED,
> stale gateway contexts are evicted. HTTP is fully stateless (no sessions
> created per request).

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

- **HTTP (Sprint 23.1):** Fully stateless. No sessions are created per
  request. Each request authenticates independently via
  `gateway.authenticate_request()`. Only `/v1/edge/auth` creates a session
  (for explicit session-based flows).
- **MQTT:** One AUTH establishes a session; subsequent envelope payloads carry
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

**Sprint 23.1 reconnect flow:**

1. Device re-authenticates with existing credential.
2. `authenticate_device()` calls `store.delete_device_sessions(device_id)`
   to invalidate any existing sessions.
3. If old sessions existed, device transitions to `RECONNECTING` then
   immediately to `CONNECTED`.
4. Gateway evicts stale `AuthenticatedDeviceContext` for the same
   `device_id` from its in-memory map.
5. New session is created. Pending effects are available for delivery.

Guarantees:

- Reconnection **never duplicates the device entity** (tested).
- Old sessions are **invalidated** on re-auth — no stale session leaks.
- Stale gateway contexts are **evicted** on reconnect.
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
