# Events

## What it is

Events connect browser interactions (clicks, input changes) to Python handlers. The `@event` decorator registers an async handler that the WebSocket transport dispatches to.

## Minimal example

```python
from voodoo import event, state

count = state(0)


@event
async def increment(element_id, value):
    count.set(count.get() + value)
```

The browser triggers this with:

```html
<button onclick="vd.event('increment', 'counter-btn', 5)">+5</button>
```

## Common usage

### Form input event

```python
@event
async def update_name(element_id, value):
    name.set(value)
```

### Reset event

```python
@event
async def reset(element_id, value):
    count.set(0)
```

## How it works

1. The browser sends a WebSocket message: `{"type": "event", "event": "increment", "id": "btn-1", "value": 5}`.
2. The WebSocket endpoint looks up the handler by name in the `event_handlers` registry.
3. The handler runs: `await handler(element_id, value)`.
4. If the handler mutates state, the `StateRenderer` re-renders and broadcasts a DOM patch.

## Advanced

### Registering events programmatically

```python
from voodoo.core.events import register_event

register_event("custom_event", my_handler)
```

### WebSocket manager

The `WebSocketManager` handles connections and broadcasts:

```python
from voodoo.core.events import ws_manager

await ws_manager.broadcast_patch("element-id", "<div>New content</div>")
await ws_manager.broadcast_append("list-id", "<li>New item</li>")
```

## API reference

- `event(func)` — decorator registering an async event handler by function name.
- `register_event(name, handler)` — register a handler programmatically.
- `ws_manager` — singleton `WebSocketManager` for connection management.
- `ws_manager.broadcast_patch(element_id, html)` — send a DOM patch to all clients.
- `ws_manager.broadcast_append(element_id, html)` — append HTML to all clients.
