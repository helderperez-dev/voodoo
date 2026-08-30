# Edge Reliability

> Delivery semantics, idempotency, and failure handling. Voodoo makes
> **no exactly-once claims** — anywhere.

## The model: at-least-once + idempotency (EDGE §28)

Networks redeliver; MQTT QoS 1 redelivers; HTTP retries redeliver. Voodoo
embraces this rather than pretending it away:

> **At-least-once delivery + idempotent messages/effects** is the
> reliability contract of `voodoo-edge/v1`.

Two mechanisms make redelivery harmless:

1. **Stable IDs on every message** — events carry `message_id`; effects
   carry `effect_id`.
2. **Server-side deduplication/compare-and-swap** — duplicates collapse
   to the first result (tested).

## Event idempotency (EDGE §46, tested)

Sending the same `message_id` twice:

- First delivery → processed → `{"status": "accepted", "execution_id": ...}`
- Retry → `{"status": "duplicate"}` — **no second event, no second
  Execution** (exactly one semantic event; asserted in tests).

Protocol retries are therefore safe by default.

## Effect idempotency (EDGE §47–§28, tested)

- Duplicate `submit_effect(effect_id=X)` → single pending delivery
  (INSERT OR IGNORE on the stable id; tested).
- Delivery (HTTP poll or MQTT publish) may repeat — `deliveries` counts
  them; the device must recognize `effect_id` and apply the effect once.
- Only the device's **ACK** transitions delivery state; repeated polls
  between submission and ACK naturally re-present the same effect.

## Unknown delivery state (EDGE §29)

Send fails mid-flight? ACK never arrives? The delivery record stays in a
**non-terminal state** (`pending` / `delivered`) — the runtime asserts
neither success nor failure:

- `delivered` means "we handed it over ≥ once", nothing more.
- Retry policy is explicit and conservative: effects are **re-presented
  until ACKed** (bounded by `max_pending_effects`); nothing auto-retries
  *on the device's behalf*.
- Non-idempotent device commands are the **device's** responsibility to
  guard — the protocol's answer is the stable `effect_id`.

## Offline devices (tested)

- Effects submitted while offline queue in the durable store.
- On reconnect: HTTP `GET /v1/edge/effects` returns them; the MQTT
  session resumes and pending effects flow again.
- The device entity, state, capabilities, and history are untouched by
  disconnects (see [device-lifecycle.md](device-lifecycle.md)).

## What is NOT claimed

- ❌ Exactly-once delivery (MQTT QoS 2 avoided deliberately — it does not
  remove the need for app-level idempotency).
- ❌ Exactly-once *execution* of device-side actions (idempotency keys
  are the contract).
- ❌ Distributed transactions across runtime ↔ device.
- ❌ Bounded-latency guarantees.

## Retry guidance for clients

| Message | Safe to retry? | Key |
|---|---|---|
| AUTH | yes | credential |
| EVENT | yes | `message_id` |
| STATE_SYNC | yes | `state_version` (CAS) |
| EFFECT_ACK | yes* | first ACK wins; later ACKs overwrite ack status only |
| heartbeat | yes | — (telemetry only) |

\* ACK idempotency is per-effect-status; clients should retry ACKs until
they observe the effect leave the pending set.
