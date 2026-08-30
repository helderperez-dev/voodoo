# Edge State Synchronization

> Versioned device state with stale rejection (EDGE §22–§24).

## Model

Device state uses the **standard Voodoo State semantics** — there is no
separate `DeviceState` abstraction. The device's reported state and its
monotonic `state_version` live on the Device entity; every accepted
update bumps the stored version atoms via compare-and-swap.

```json
{
  "type": "state_sync",
  "payload": {"state": {"temperature": 31.4, "fan": true}, "state_version": 42}
}
```

## Version rules (EDGE §23, tested)

| Incoming vs stored | Result |
|---|---|
| `incoming > stored` | ✅ accepted — state + version updated |
| `incoming == stored` | ✅ accepted — idempotent protocol retry (no change) |
| `incoming < stored` | ❌ `409 INVALID_STATE_VERSION` — stale state **never** silently overwrites newer state |

Conflict response includes machine-readable context:

```json
{"error": {"code": "INVALID_STATE_VERSION",
           "detail": {"incoming": 41, "current": 42}}}
```

## Source of truth — runtime-authoritative (explicit, EDGE §24)

Sprint 23 implements a **runtime-authoritative** model:

- **Device → Runtime (STATE_SYNC):** the runtime accepts device reports
  subject to version monotonicity. This makes device-side retries safe
  and prevents rollback of runtime knowledge.
- **Runtime → Device:** the runtime's stored `state_version` is returned
  in heartbeat/heartbeat responses and AUTH; a device that finds itself
  behind (its version < runtime's) must **reconcile by adopting the
  runtime state**:

```
device state_version = 41
runtime state_version = 42
        ↓ heartbeat/auth reveals 42
        ↓ device pulls/derives runtime state  (reconciliation)
device state_version = 42          → subsequent syncs accepted
```

A device forcing its stale state forward gets `INVALID_STATE_VERSION`
until it adopts version 42 — by design, the runtime never regresses.

## Where state changes come from

Device reports and Executions both mutate device state:

- **STATE_SYNC** — device telemetry applying the CAS rules above.
- **Effects** — an execution's effect payload (`{"state": "on"}`) is a
  device command, not a direct state write; the device's *next* sync
  reports the resulting state at a higher version.

This keeps one canonical store, one version counter, and one rule set.

## Persistence

State lives in the device store (`devices.state`, `devices.state_version`)
— SQLite by default, the same durability path as every runtime record.
Conditional (`WHERE state_version < ?`) updates make stale rejection
atomic under concurrency.
