# Voodoo Edge — Overview

> **Protocol:** `voodoo-edge/v1` · **Sprint 23** · **Status:** Runtime edge-ready; ESP32 client not yet implemented.

## What is Voodoo Edge?

Voodoo Edge is the **external device boundary** of the Voodoo Runtime. It lets
physical and distributed participants — ESP32s, Raspberry Pis, robots,
industrial controllers, browser runtimes — act as **first-class Voodoo
Entities** in the same durable execution model as software agents, workers,
and humans.

Edge is **not** a second runtime:

- **Voodoo Runtime** = the authoritative execution system (ExecutionEngine, Intent, Capability, Effect).
- **Voodoo Edge** = the versioned protocol + gateway through which devices participate.
- **Voodoo Edge ≠ ExecutionEngine.** Device-triggered work enters the standard
  engine; there is no `DeviceExecutionEngine`.

## Why does it exist?

Software, humans, and physical devices converge on one model:

```
Device → Event → Voodoo Runtime → Execution → Effect → Device
```

A temperature sensor's `temperature.changed` event can trigger an Intent, run
as a normal Execution (with actor `device:<id>`), and produce an Effect
(`relay.fan.control`) delivered back to the device — with capability checks,
durable records, traceability, and idempotency at every step.

## Architecture

```
                    VOODOO RUNTIME
                          │
         ┌────────────────┼────────────────┐
         │                │                │
       Agents          Workers         Devices
         │                │                │
         └────────────────┼────────────────┘
                          │
                    ExecutionEngine
                          │
                       Effects
                          │
                   Device Gateway
                          │
                 ┌────────┴────────┐
                 │                 │
                HTTP              MQTT
                 │                 │
                 └────────┬────────┘
                          │
                     Voodoo Edge
                          │
                       Device
```

## What runs where?

| Concern | Runtime | Device |
|---|---|---|
| Identity & credentials | Issues & stores (hashed) | Holds raw credential |
| Authentication | Validates | Presents credential |
| Capability authorization | Enforces | Advertises capabilities |
| Executions | Runs & records | — |
| Effects | Produces & tracks delivery | Receives & idempotently applies |
| State | Canonical store (versioned) | Reports state |
| Events | Ingests & routes | Emits |

## Transports

- **HTTP** — REST endpoints under `/v1/edge/*`. Easy to test with curl.
- **MQTT** — versioned topic namespace `voodoo/v1/devices/{device_id}/...`. Requires the optional `voodoo[edge]` extra (paho-mqtt).

Both carry the **same message envelopes** and produce **identical runtime
behavior** — proven by shared contract tests (`tests/contracts/test_edge_protocol.py`).

## Enabling Edge

Edge is **disabled by default** — applications that don't enable it pay zero
overhead (no broker, no gateway, no device tables).

```toml
# voodoo.toml
[edge]
enabled = true
http_enabled = true
mqtt_enabled = false
```

```bash
# MQTT support (optional)
pip install "voodoo-framework[edge]"

# Local broker for development
just mqtt-up
```

## Documentation map

| Document | Contents |
|---|---|
| [protocol.md](protocol.md) | All v1 message types, envelope, validation |
| [http.md](http.md) | Endpoints, auth headers, curl examples |
| [mqtt.md](mqtt.md) | Topics, QoS, TLS, broker configuration |
| [security.md](security.md) | Enrollment, credentials, revocation, guarantees |
| [device-lifecycle.md](device-lifecycle.md) | Device states, sessions, reconnect |
| [state-synchronization.md](state-synchronization.md) | Versioning, stale rejection, reconciliation |
| [reliability.md](reliability.md) | At-least-once delivery, idempotency |
| [device-simulator.md](device-simulator.md) | The protocol-faithful test client |

## Next phase

Sprint 24 will implement `voodoo-edge-esp32` — the C++ reference client
consuming this protocol. Sprint 23 delivers the protocol, gateway,
simulator, and documentation that client will target.
