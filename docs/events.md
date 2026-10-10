# Events

## What it is

Events connect browser interactions to Python callables. Callable bindings are
opaque and owned by the browser session that rendered them.

## Minimal example

```python
from voodoo import state
from voodoo.ui import Button

count = state(0)


async def increment():
    count.update(lambda value: value + 1)


button = Button("Increment", on_click=increment)
```

Voodoo emits a semantic `data-vd-event-*` binding; no inline handler is needed.

## Common usage

### Form input event

```python
async def update_name(value):
    name.set(value)
```

### Reset event

```python
async def reset():
    count.set(0)
```

## How it works

1. HTTP rendering creates or resumes an opaque HttpOnly UI session.
2. Callable handlers receive opaque IDs stored only in that session registry.
3. The WebSocket validates origin, session ownership, message size and rate.
4. Dispatch resolves the binding only inside the caller's session.
5. Reactive patches are sent only to connections belonging to that session.

Changing user identity rotates the UI session. Disconnected sessions retain a
short reconnect grace period, then release bindings, state and render tasks.

## Advanced

### Registering events programmatically

```python
from voodoo.ui.events import register_event

register_event("custom_event", my_handler)
```

Named handlers are an application-level compatibility surface. Prefer passing
callables directly to components because callable ownership is session-scoped.

### WebSocket manager

The `WebSocketManager` targets the current event/render session. The historical
method names remain for compatibility but do not fan out globally:

```python
from voodoo.ui.events import ws_manager

await ws_manager.broadcast_patch("element-id", "<div>New content</div>")
await ws_manager.broadcast_append("list-id", "<li>New item</li>")
```

## API reference

- `event(func)` — compatibility decorator for an application-level named handler.
- `register_event(name, handler)` — register a handler programmatically.
- `ws_manager` — singleton `WebSocketManager` for connection management.
- `ws_manager.broadcast_patch(element_id, html)` — patch the current UI session.
- `ws_manager.broadcast_append(element_id, html)` — append in the current UI session.
