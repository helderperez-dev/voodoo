# ESP32 Reference Implementation — Sprint 24

> **Target release:** `2.7.0` · **Status:** planned · **Protocol:** `voodoo-edge/v1`

Sprint 24 is the first physical proof of Voodoo's agency-and-embodiment model.

The objective is deliberately concrete: **one Voodoo execution must cross the software/physical boundary, cause a physical effect on a real ESP32, receive an acknowledgement/observation, and close the loop back into Runtime state.**

This sprint does not introduce a second execution architecture for embedded devices. It proves that the existing Runtime is sufficient.

## Acceptance vertical slice

```text
ESP32 button
    ↓ EVENT
Voodoo Edge transport
    ↓
DeviceGateway
    ↓
Intent / Execution
    ↓
Capability authorization
    ↓
Effect
    ↓
ESP32 LED
    ↓
EFFECT_ACK + state observation
    ↓
Runtime state
```

A model/Agent may be inserted into the decision path as an optional demonstration:

```text
button → EVENT → Execution → Agent/Policy → Effect → LED → ACK/state
```

AI is not required to prove protocol correctness. The same physical loop must work with deterministic Compute so the Edge architecture never becomes dependent on an LLM provider.

## Why this matters

A remotely controlled LED is not the goal. The goal is proving these invariants on real hardware:

- the device has stable runtime identity;
- the device can authenticate without embedding server authority;
- physical observations enter Voodoo as Events/State;
- meaningful device-triggered work becomes an Execution;
- an Effect is attributable to an Intent and authorized capability;
- physical effects are delivered at least once but applied idempotently;
- acknowledgement is correlated to the effect;
- reconnect/retry does not create uncontrolled duplicate action;
- state returns to the Runtime after action;
- the Runtime remains the execution source of truth.

This is the minimum useful definition of an embodied Voodoo participant.

## Reference target

The first supported reference target is a conventional ESP32-class board with:

- Wi-Fi;
- one digital input (push button);
- one digital output (LED; onboard LED where available is acceptable);
- enough non-volatile storage to retain device identity, credential, last acknowledged effect ids, and local state metadata.

The implementation should remain portable enough to evolve toward ESP32-CAM and other ESP32 variants, but Sprint 24 must optimize for clarity and reliability before hardware breadth.

## Firmware implementation model

The reference client should be a small library plus an example application, not a monolithic demo sketch.

Suggested structure:

```text
examples/edge_esp32/
├── README.md
├── platformio.ini
├── include/
│   └── voodoo_edge_config.example.h
├── lib/
│   └── VoodooEdge/
│       ├── VoodooEdge.h
│       ├── VoodooEdge.cpp
│       ├── protocol.h
│       ├── transport.h
│       ├── mqtt_transport.h
│       ├── identity.h
│       ├── state.h
│       └── effect_log.h
└── src/
    └── main.cpp
```

PlatformIO is the preferred reference build because it gives reproducible dependencies and CI-friendly compilation. The library source should remain Arduino-compatible so a user can copy/install it for Arduino IDE projects without adopting a second protocol implementation.

If repository boundaries later justify a standalone `voodoo-edge` embedded SDK repository, the reference code can move without changing protocol semantics.

## Required firmware capabilities

### 1. Device identity

The client must retain a stable device identity after enrollment and reboot.

Persist locally:

```text
device_id
credential (vdk_...)
protocol_version
last known state_version
small bounded set of processed effect ids
```

The raw device credential belongs only on the device/configuration boundary. It must never be logged by the reference implementation.

### 2. Enrollment

The reference flow must support bootstrap from a single-use `vde_...` enrollment key into the long-lived `vdk_...` device credential.

Development UX should be understandable from a fresh machine:

```text
1. Start Voodoo Runtime with Edge enabled.
2. Create an enrollment from the Runtime/admin side.
3. Flash/provision ESP32 with Wi-Fi + enrollment key.
4. Device enrolls once.
5. Device stores device_id + vdk_ credential.
6. Enrollment key is discarded.
7. Future boots use the device credential.
```

A production provisioning mechanism is outside Sprint 24. The reference must not pretend a compile-time secret is a production provisioning strategy.

### 3. Connection lifecycle

The client must implement an explicit connection state machine rather than scattering reconnect logic through callbacks.

Recommended local states:

```text
UNPROVISIONED
CONNECTING_WIFI
CONNECTING_TRANSPORT
AUTHENTICATING
CONNECTED
RECONNECTING
REVOKED
```

A disconnect must not erase durable identity. A reconnect must establish a fresh Runtime session according to `voodoo-edge/v1` semantics.

### 4. HELLO and AUTH

After transport connection, the client identifies its protocol/client/firmware information and authenticates before publishing protected device messages.

No application EVENT, STATE_SYNC, or effect acknowledgement should be sent before the session is authenticated when using a session-oriented transport such as MQTT.

### 5. Heartbeat

Heartbeat reports liveness/presence. It is **not** meaningful work and must not create an Execution.

The heartbeat interval should be configurable and tolerant of temporary transport loss.

### 6. Event publication

The button example emits a namespaced event such as:

```text
button.pressed
```

Each publication needs a unique/stable `message_id` for idempotency across redelivery.

Example semantic payload:

```json
{
  "pin": 0,
  "pressed": true,
  "sequence": 42
}
```

The firmware should separate hardware sampling/debouncing from protocol publication.

### 7. Effect reception

The LED example accepts a narrow physical effect such as:

```text
led.set
```

with a payload conceptually equivalent to:

```json
{
  "on": true
}
```

The reference implementation must never expose arbitrary code execution, shell execution, or generic "run command" semantics on the ESP32. A device advertises and implements specific physical capabilities.

### 8. Effect idempotency

`effect_id` is the idempotency key for physical delivery.

Before applying an effect:

```text
if effect_id already processed:
    do not actuate again
    replay acknowledgement/current state
else:
    validate capability + payload
    apply physical action
    persist bounded processed marker
    acknowledge
```

The processed-effect log must be bounded for microcontroller storage. The exact retention strategy may use a small ring/LRU set; it only needs to cover the practical redelivery window documented by the Runtime.

### 9. EFFECT_ACK

The device acknowledges success or failure using the protocol message associated with the exact `effect_id`.

Acknowledgement means the device attempted/applied the requested capability according to its local implementation. It must not be confused with mere MQTT packet delivery.

### 10. State synchronization

After a physical action, the client should report the resulting device state, for example:

```json
{
  "led": true,
  "button": false
}
```

`state_version` must follow Runtime reconciliation rules. A stale writer must not silently overwrite newer canonical state.

### 11. Capability declaration

The reference device should explicitly advertise what it can observe or actuate, for example:

```text
button.read
led.write
```

The Runtime remains responsible for authorization. Device capability declaration describes what the hardware participant supports; it is not itself a grant of authority to an agent.

## MQTT reference transport

MQTT is the preferred physical reference transport for Sprint 24 because it naturally supports long-lived device connectivity and at-least-once delivery.

Topology:

```text
ESP32
  │ MQTT
  ▼
External broker (Mosquitto for local development)
  │ MQTT
  ▼
Voodoo Edge MQTT transport
  │
  ▼
DeviceGateway → ExecutionEngine
```

Voodoo is not an MQTT broker. A local broker is an external transport dependency, just as PostgreSQL or Redis can be external infrastructure in other deployment shapes.

The HTTP transport remains useful for conformance, provisioning experiments, and constrained clients. Both transports must preserve the same Edge semantics.

## Runtime-side example

The application side should make the physical relationship explicit rather than hiding it in transport callbacks.

Conceptually:

```python
@mesh.on("device.button.pressed")
async def handle_button(event):
    # deterministic policy for base acceptance path
    await devices.effect(
        event.device_id,
        "led.set",
        {"on": True},
        capability="led.write",
    )
```

The exact public API must be derived from the actual Voodoo implementation. **Do not invent `devices.effect` merely to match this documentation.** If the current public API differs, Sprint 24 should use it or deliberately introduce the smallest coherent public abstraction with contract tests and documentation.

An optional AI example can replace the deterministic policy with an Agent while leaving the execution/effect/device path unchanged.

## Failure-path acceptance matrix

Sprint 24 is incomplete until the physical/reference client handles the failure paths that define real autonomy.

| Scenario | Required behavior |
|---|---|
| Duplicate EVENT publish | Runtime idempotency prevents duplicate semantic execution where the same message id is replayed |
| Duplicate EFFECT delivery | ESP32 does not actuate twice; acknowledgement can be replayed |
| Wi-Fi loss | Client reconnects without losing identity or processed-effect state |
| Broker loss | Client enters reconnect state and eventually re-authenticates |
| Runtime restart | Device establishes a new valid session and resumes participation |
| Stale `state_version` | Conflict is surfaced/reconciled; no blind overwrite |
| Revoked credential | Device cannot continue authenticated action; enters a clear revoked/provisioning error state |
| Wrong device topic/identity | Message is rejected at Runtime boundary |
| Malformed effect payload | Device rejects locally and returns failure acknowledgement without unsafe actuation |
| Reset during effect delivery | On reboot/redelivery, persisted effect id prevents duplicate physical action |

Simulator parity must remain green. The real ESP32 reference is an additional conformance participant, not an alternative behavior.

## Development workflow

A developer should be able to reproduce the first physical loop with a short sequence similar to:

```bash
# Terminal 1 — external local MQTT broker
just mqtt-up

# Terminal 2 — Voodoo app/runtime
voodoo dev

# Terminal 3 — build/flash/monitor the ESP32 reference
pio run -t upload
pio device monitor
```

Exact commands and configuration must be verified against the final implementation before release.

The Runtime's Edge configuration should remain explicit:

```toml
[edge]
enabled = true
http_enabled = true
mqtt_enabled = true
```

## Sprint 24 scope

- [ ] Official ESP32 reference client/library.
- [ ] Reproducible PlatformIO build and Arduino-compatible source layout.
- [ ] Wi-Fi lifecycle.
- [ ] MQTT reference transport.
- [ ] Enrollment (`vde_` → `vdk_`) and persistent device identity.
- [ ] HELLO/AUTH lifecycle.
- [ ] Heartbeat/presence.
- [ ] Namespaced EVENT publication with stable message ids.
- [ ] EFFECT reception and validation.
- [ ] Bounded persistent effect-id deduplication.
- [ ] EFFECT_ACK success/failure.
- [ ] State synchronization/version handling.
- [ ] Capability declaration.
- [ ] Reconnect/session invalidation behavior.
- [ ] Runtime-side deterministic button → LED example.
- [ ] Optional Agent-driven variant using the same physical effect path.
- [ ] Simulator/reference semantic-parity tests.
- [ ] Failure tests for duplicate event/effect, reconnect, broker/runtime outage, stale state, revocation, wrong identity/topic, malformed effect and reset during delivery.
- [ ] Mac/Linux local quickstart with Mosquitto + Runtime + ESP32.

## Explicit non-goals

Sprint 24 does **not** include:

- an LLM running on the ESP32;
- a second ExecutionEngine on the device;
- generic arbitrary remote code execution;
- a robotics/navigation abstraction;
- SLAM;
- fleet-management SaaS;
- OTA firmware management;
- exactly-once transport claims;
- offline independent agent reasoning on the device;
- cellular/4G-specific transport;
- production certificate manufacturing/provisioning infrastructure.

Those may be justified later, but none are required to prove embodiment.

## Definition of Done

Sprint 24 is complete when all of the following are true:

1. The normal Voodoo quality gate is green.
2. Existing Edge simulator/conformance tests remain green.
3. The ESP32 reference compiles reproducibly.
4. A real ESP32 can enroll/authenticate and survive reboot/reconnect.
5. Pressing its physical button produces a Voodoo Event that enters the Runtime.
6. That event causes a normal Voodoo Execution.
7. The Execution produces an authorized `led.set` effect.
8. The physical LED changes state.
9. The device acknowledges the exact effect and reports/reconciles state.
10. Replaying the same effect cannot cause a duplicate physical actuation.
11. The full loop is documented from a fresh development machine.

At that point Voodoo has its first real body.
