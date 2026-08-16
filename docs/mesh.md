# Mesh

## What it is

Voodoo Mesh is the unified realtime event bus. Local events fire immediately on in-process handlers; remote events serialize over WebSocket with a JSON-RPC 2.0 envelope. All event names must be namespaced (e.g. `"agent.started"`, not `"started"`).

## Minimal example

```python
from voodoo.mesh import mesh


# Register a handler
@mesh.on("lead.created")
async def on_lead_created(payload):
    print(f"New lead: {payload['name']}")


# Emit an event
await mesh.emit("lead.created", {"name": "Ada"})
# prints: New lead: Ada
```

## Common usage

### Broadcasting events

```python
await mesh.broadcast("agent.started", {"run_id": "abc123"})
await mesh.emit("agent.completed", {"status": "ok"})
```

`emit` is an alias for `broadcast`.

### Exposing functions

```python
@mesh.expose(name="lookup_order")
async def lookup_order(order_id: int) -> dict:
    """Look up an order."""
    return {"id": order_id, "status": "shipped"}
```

Exposed functions are callable by connected mesh nodes via JSON-RPC and auto-bridged to MCP.

### Stacking with @task

```python
from voodoo.workers import task


@mesh.on("lead.created")
@task(retries=3, timeout=10)
async def sync_crm(payload):
    await crm_api.sync(payload)
```

When the event fires, the task runs with retries, timeout, and a telemetry span.

## How it works

- **Local boundary**: handlers fire in-process with zero latency and no serialization.
- **Remote boundary**: events are wrapped in a standard envelope (`id`, `ts`, `source`, `correlation_id`, `event`, `payload`) and sent to connected WebSocket nodes.
- The `correlation_id` is automatically pulled from the telemetry `trace_id_var`.

## Advanced

### Event envelope

```python
from voodoo.mesh import _make_envelope

envelope = _make_envelope("agent.started", {"run_id": "abc"})
# {"id": "...", "ts": 1234.5, "source": "voodoo",
#  "correlation_id": "...", "event": "agent.started", "payload": {...}}
```

### WebSocket endpoint

The mesh WebSocket endpoint is available at `/voodoo/mesh/ws`. Connected nodes can:
- Call exposed functions (`method: "call"`)
- Forward events (`method: "event"`)

### MeshClient

```python
from voodoo.mesh import mesh

client = await mesh.connect("ws://other-node:8000/voodoo/mesh/ws")
result = await client.call("lookup_order", order_id=42)
```

## API reference

- `mesh` — the global `MeshNetwork` singleton.
- `mesh.on(event)` — decorator to register a handler (event must be namespaced).
- `mesh.broadcast(event, payload)` / `mesh.emit(event, payload)` — broadcast to local + remote.
- `mesh.expose(name=None)` — decorator to expose a function for remote calls + MCP.
- `mesh.connect(endpoint_url)` — connect to a remote mesh node.
- `MeshClient` — client for calling remote mesh functions.
