# Voodoo Mesh

The Voodoo Mesh is a native real-time network built into the framework that bridges WebSockets, internal event-driven architecture, and Model Context Protocol (MCP) tooling into a single coherent system.

## Architecture

The `MeshNetwork` (`voodoo.mesh`) acts as a central hub for real-time events. It allows:
1. Exposing backend Python functions to connected clients and AI tools.
2. Broadcasting events to all connected clients (browsers).
3. Handling bidirectional real-time communication via WebSockets (`/_voodoo_ws`).

## Exposing Functions

Use the `@mesh.expose()` decorator to expose a function. By doing this, Voodoo automatically:
- Allows the web client to invoke it via JSON-RPC.
- Auto-bridges the function to MCP, allowing AI IDEs (like Cursor, Trae) to call the function natively.

```python
from voodoo.mesh import mesh

@mesh.expose("get_server_time")
def get_time():
    """Returns the current server time."""
    from datetime import datetime
    return datetime.now().isoformat()
```

## Subscribing to Events

Use the `@mesh.on("event_name")` decorator to listen to mesh broadcasts locally:

```python
from voodoo.mesh import mesh

@mesh.on("user_signup")
async def handle_signup(payload):
    print(f"New user registered: {payload['email']}")
```

## Broadcasting Events

To push an event to all connected WebSocket clients (like a notification system or live-updating feed) and trigger local handlers:

```python
from voodoo.mesh import mesh

async def process_payment():
    # ... logic ...
    await mesh.broadcast("payment_success", {"amount": 50, "currency": "USD"})
```

## AI Native

Because `mesh.expose` automatically wires into `voodoo.mcp`, any function you expose on the Mesh is immediately available as a Tool to MCP-compatible AI clients. This makes Voodoo uniquely suited for building AI-first platforms where the IDE or autonomous agents interact directly with the app's internal logic.
