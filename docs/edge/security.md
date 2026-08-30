# Edge Security

> What is guaranteed, what is not, and how device trust works. This
> document makes no claims beyond what the implementation provides.

## Identity (EDGE §8)

- Every device gets a stable, globally-unique Voodoo identity:
  `device_id = device_<24-hex>`, with the entity reference
  `device:<device_id>` participating in the normal Entity model.
- **MAC addresses are metadata only** — never the canonical identity.

## Credentials (EDGE §9)

Device credentials are **separate from user/admin API keys**:

| | User API key | Device credential |
|---|---|---|
| Prefix | `vd_live_` | `vdk_` (Voodoo Device Key) |
| Storage | SHA-256 hash | SHA-256 hash |
| Presentation | `X-API-Key` / `Authorization` | `X-Device-Credential` / `Authorization: Device` / AUTH message |
| Scope | user account | exactly one device |

Guarantees & rules:

- Only the SHA-256 **hash** is stored — the raw credential is returned
  exactly once (enrollment/rotation) and **cannot be recovered**.
- Raw credentials are **never logged**, never emitted in mesh events,
  telemetry, error bodies, or device state. (Verified by test: the
  observability test asserts the credential absent from all captured
  events.)
- Rotation marks the old credential invalid and issues a new one —
  `rotate_device_credential()`.
- Expiration: the model carries `expires_at`; enforcement of lifetime
  expiry is **not yet automatic** (documented limitation).

## Enrollment (EDGE §10)

Single-use, short-lived tokens (`vde_...`, default 1 hour):

```
Runtime creates enrollment (raw key shown once)
   → device presents key
   → runtime validates (exists, PENDING, unexpired)
   → single-use consumption (PENDING → CONSUMED)
   → device identity + vdk_ credential issued
```

- Reuse of a consumed key → `AUTHENTICATION_FAILED`.
- Revocation: `revoke_enrollment()` blocks pending tokens.

## Authentication (EDGE §11)

**The runtime never trusts a bare `device_id`.** Every device-originated
request resolves to an `AuthenticatedDeviceContext` by validating the
credential hash **and** its binding to the claimed device:

- credential unknown/revoked → `AUTHENTICATION_FAILED`
- credential ↔ device_id mismatch → `AUTHENTICATION_FAILED`
- device REVOKED (with any credential) → `DEVICE_REVOKED`
- revoked device → all its credentials cascade-revoked → `401`

## Authorization (EDGE §12–§13)

- **Registration ≠ authorization.** A device *advertising* `motor.control`
  does not receive it; the runtime stores the canonical advertised set,
  and **operators grant** capabilities via enrollment configuration.
- Effect submission is **rejected at the runtime boundary** if the target
  device lacks the required capability (`AUTHORIZATION_FAILED`,
  `INVALID_CAPABILITY` path) — enforcement does not rely on the device
  honoring anything (EDGE §50, proven by test).
- **Device isolation:** sessions cannot act for another device
  (session↔device binding validated per message); devices may not ack or
  list another device's effects (`AUTHORIZATION_FAILED`, proven by test).

## Transport security

- **HTTP:** run behind TLS at your ingress (standard deployment concern).
- **MQTT:** `tls = true` supported (8883). Production must not run
  plaintext MQTT; local dev may (`just mqtt-up`, localhost, no auth).
- Credentials in transit rely on transport encryption — Voodoo does not
  add its own payload encryption layer.

## Replay & idempotency

- Duplicate events (same `message_id`) are collapsed — protocol retries
  are safe (EDGE §46, tested).
- Duplicate effect submissions are no-ops on `effect_id` (EDGE §47/§28,
  tested).
- **Not provided:** time-window anti-replay of distinct message_ids,
  per-message signatures, or mTLS device identity. These are candidates
  for future protocol versions.

## Revocation semantics (EDGE §49)

`revoke_device()` is immediate and cascading:

1. Device status → `REVOKED` (terminal: can never authenticate again).
2. All ACTIVE credentials for the device → REVOKED.
3. Live gateway sessions are dropped.

## Known limitations (explicit)

- Enrollment-admin endpoint should sit behind user auth middleware in
  production deployments (it is open in edge-only test apps).
- Credential lifetime expiry is modeled but not hard-enforced.
- No per-tenant device scoping yet (single-runtime scope).
- No rate limiting specific to edge endpoints beyond the global
  `RateLimitMiddleware` (resource limits in `EdgeConfig` bound payload
  sizes; per-device rate limiting is future work).
