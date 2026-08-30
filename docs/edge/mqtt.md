# Edge MQTT Transport

> MQTT binding for `voodoo-edge/v1`. Requires the optional extra
> `pip install "voodoo-framework[edge]"` (paho-mqtt ≥ 2.0 — mature,
> actively maintained, integrates with asyncio without a second event-loop
> model, EDGE §69).

## Topic namespace

Versioned and per-device (EDGE §35):

| Topic | Direction | Carries |
|---|---|---|
| `voodoo/v1/devices/{device_id}/events` | device → runtime | EVENT messages |
| `voodoo/v1/devices/{device_id}/state` | device → runtime | STATE_SYNC messages |
| `voodoo/v1/devices/{device_id}/ack` | device → runtime | EFFECT_ACK messages |
| `voodoo/v1/devices/{device_id}/heartbeat` | device → runtime | HEARTBEAT messages |
| `voodoo/v1/devices/{device_id}/auth` | device → runtime | AUTH messages |
| `voodoo/v1/devices/{device_id}/effects` | runtime → device | EFFECT messages |

Payloads are the **same JSON envelopes** as HTTP — semantic equivalence is
guaranteed by shared gateway handling and proven by contract tests
(`tests/contracts/test_edge_protocol.py`).

## Flow

1. The runtime subscribes to `voodoo/v1/devices/+/+` (all device inboxes).
2. A device enrolls over HTTP (identity bootstrap), then connects to MQTT.
3. The device publishes AUTH to its `auth` topic once — the response
   establishes a `session_id`.
4. Subsequent device → runtime payloads include `"session_id"` inside the
   envelope payload; the gateway validates the session binds to the same
   `device_id`.
5. The runtime publishes EFFECTs to the device's `effects` topic.

## QoS policy (EDGE §37)

**QoS 1 (at-least-once) on all topics.**

Rationale: QoS 1 + application-level idempotency (`message_id` for events,
`effect_id` for effects) gives safe redelivery with simple client logic.
MQTT QoS 2 (exactly-once) is deliberately **not** used — it adds overhead
and still doesn't remove the need for application idempotency (duplicates
can occur across reconnects regardless). **Voodoo never claims exactly-once
delivery on any transport.**

## Retained messages

- **effects**: not retained — pending effects persist in the runtime store
  and are re-delivered on poll/next session. Retaining could replay stale
  commands after reconnection.
- **state**: not retained; the runtime holds canonical state.

## Session behavior

- MQTT `clean_session=True` recommended for devices. Voodoo device sessions
  live **in the runtime** (versioned, observable), not in broker session
  state (EDGE §31).
- Offline devices: effects queue in the durable store; reconnection (HTTP
  poll or next MQTT session) delivers them.

## Broker configuration

Never hard-coded — configured via `voodoo.toml` or environment (EDGE §39):

```toml
[edge]
enabled = true
mqtt_enabled = true

[edge.mqtt]
broker_url = "localhost"     # MQTT_BROKER_URL
port = 1883                  # MQTT_PORT (8883 for TLS)
tls = false                  # MQTT_TLS — REQUIRED in production
username = ""                # MQTT_USERNAME (broker auth)
password = ""                # MQTT_PASSWORD
client_id = "voodoo-runtime" # MQTT_CLIENT_ID
keepalive = 60
qos = 1
```

## TLS (EDGE §38)

- Set `tls = true` (port 8883 by convention) — the client uses the system
  CA bundle; custom certs can be layered via paho's `tls_set()`.
- Architecture permits: TLS, authenticated broker, and per-device
  credentials. **Production must never require plaintext MQTT.**
- Local development may use an explicitly configured insecure broker:

```bash
just mqtt-up   # Mosquitto, no auth, localhost only
```

## Python API

```python
from voodoo.edge import DeviceGateway, SQLiteDeviceStore, EdgeMQTTTransport
from voodoo.runtime import engine
from voodoo.edge.mqtt import topic_for

gateway = DeviceGateway(SQLiteDeviceStore("data/devices.db"), engine)
transport = EdgeMQTTTransport(
    gateway,
    broker_url="localhost",
    port=1883,
    username=None,  # broker credentials, not device credentials
    password=None,
)
await transport.start()  # subscribes to voodoo/v1/devices/+/+

await transport.publish_effect(  # runtime → device
    "device_01j...",
    {
        "effect_id": "e1",
        "execution_id": "x1",
        "capability": "relay.fan.control",
        "payload": {"state": "on"},
    },
)
await transport.stop()
```

Reconnect behavior: paho's network loop auto-reconnects; the transport
resubscribes on reconnect (`on_connect`). Device-side reconnect semantics
are documented in [device-lifecycle.md](device-lifecycle.md).
