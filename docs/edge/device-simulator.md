# Edge Device Simulator

> A protocol-faithful virtual device — the template for the future ESP32
> client (Sprint 24). It speaks **only** `voodoo-edge/v1` through real
> transports; it never calls internal runtime APIs (EDGE §41).

## Why it exists

Before any C++ firmware exists, the simulator:

- exercises the protocol end-to-end the way a physical device will;
- drives the acceptance tests (`tests/test_edge_http.py::TestHTTPEndToEnd`);
- doubles as living documentation of intended client behavior (EDGE §57).

## Quick start

```python
import asyncio
from voodoo.edge.simulator import DeviceSimulator, HTTPSimulatorTransport


async def main():
    # dialogue with HTTP transport
    sim = DeviceSimulator(HTTPSimulatorTransport("http://localhost:8000"))

    await sim.enroll(enrollment_key, firmware_version="1.0.0")  # once
    await sim.connect(
        device_type="esp32",
        capabilities=["sensor.temperature.read", "relay.fan.control"],
    )

    await sim.send_state({"temperature": 31.4, "fan": False}, 1)
    await sim.send_event("temperature.changed", {"value": 31.4})
    await sim.heartbeat()

    effects = await sim.fetch_effects()  # poll pending effects
    for effect in effects:
        await sim.ack_effect(effect["effect_id"], "completed")

    await sim.disconnect()


asyncio.run(main())
```

## Transport options

### HTTPSimulatorTransport

```python
HTTPSimulatorTransport(base_url="http://localhost:8000")
HTTPSimulatorTransport("http://testserver", app=starlette_app)  # in-process (tests)
```

Passing `app=` routes all traffic over ASGI — no sockets, ideal for CI.

### MQTTSimulatorTransport

```python
from voodoo.edge.simulator import MQTTSimulatorTransport

transport = MQTTSimulatorTransport(device_id, broker="localhost", port=1883)
sim = DeviceSimulator(transport)
# enrollment still happens over HTTP (identity bootstrap), then:
await sim.connect(...)  # AUTH over MQTT
effects = (
    await sim.fetch_effects()
)  # subscribed topic pushes (EdgeMQTTTransport publishes)
```

Requires the `[edge]` extra and a local broker (`just mqtt-up`).

## Intended ESP32 API (design target, EDGE §57)

The simulator's lifecycle maps 1:1 to the planned C++ surface:

```cpp
VoodooEdge device;
device.begin(config);                     // enroll + connect
device.state("temperature", temperature); // send_state
device.emit("temperature.changed");       // send_event
device.onEffect("relay.fan.control", handler);
device.loop();                            // heartbeat + effect pump + acks
```

| C++ (future) | Simulator (today) |
|---|---|
| `begin(config)` | `enroll()` + `connect()` |
| `state(k, v)` | `send_state(dict, version)` |
| `emit(name)` | `send_event(name, payload)` |
| `onEffect(cap, h)` | `fetch_effects()` + `ack_effect()` |
| `loop()` | `heartbeat()` + effect polling |

## Testing patterns

The E2E acceptance test (EDGE §42) is the canonical example:

```python
sim.enroll → sim.connect → sim.send_state → sim.send_event
   → gateway.submit_effect → sim.fetch_effects → sim.ack_effect
   → delivery.status == "completed"
```

Reconnect testing: `disconnect()` then `connect()` again — the entity,
state, and pending effects survive (see device-lifecycle.md).

## Failure injection (Sprint 23.1)

The simulator includes methods for adversarial testing — simulating buggy
or malicious client behavior:

| Method | What it does |
|---|---|
| `send_duplicate_event(name, payload)` | Sends the same event twice with the same `message_id` |
| `send_state(state, version)` | Sends state with a specific version (use low version for stale test) |
| `send_wrong_device_id()` | Sends a message claiming to be from a different device |
| `send_invalid_credential()` | Sends a request with a garbage credential |
| `reconnect()` | Disconnects and re-authenticates (tests reconnect lifecycle) |

These are used in `tests/test_edge_e2e.py` and `tests/test_edge_security.py`
to verify that the gateway correctly handles adversarial scenarios.
