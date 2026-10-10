# Reactive State

## What it is

`state(initial)` creates an observable value cell. Interactive state is isolated
per browser session by default. Read with `get()`, update with `set()` /
`update()`, and let Voodoo target the resulting DOM patch to that session.

## Minimal example

```python
from voodoo import state

count = state(0)

count.get()  # 0
count.set(5)
count.get()  # 5
count.update(lambda x: x + 1)
count.get()  # 6
```

## Common usage

### In a page

```python
from voodoo import page, state
from voodoo.ui import Button, Stack, Text

counter = state(0)


@page("/")
def counter_page():
    async def increment():
        counter.update(lambda value: value + 1)

    return Stack(
        Text(f"Count: {counter.get()}"),
        Button("Increment", on_click=increment),
    )
```

### With subscriptions

```python
count = state(0)


def on_change(value):
    print(f"Count changed to {value}")


unsubscribe = count.subscribe(on_change)
count.set(10)  # prints: Count changed to 10
unsubscribe()
count.set(20)  # no output
```

## Advanced

### StateRenderer — the reactive loop

The `StateRenderer` binds state cells to page functions. When you pass
`cells`, each cell's `set()`/`update()` **automatically schedules** a
re-render of that binding (no explicit `rerender()` call needed in your
event handlers) — the "zero JS" reactive loop:

```python
from voodoo.ui.state import StateRenderer, state

count = state(0)
renderer = StateRenderer()
renderer.bind("element-id", my_page_func, cells=[count])

# Inside any @event handler:
count.set(count.get() + 1)  # → page re-rendered → patch broadcast over WS
```

`unbind(element_id)` removes the binding and unsubscribes the cells. Without
`cells`, you keep manual control: call `renderer.rerender(element_id)` to
re-render and broadcast a DOM patch.

### State scopes

Session isolation is the safe default:

```python
draft = state("")  # each browser session sees its own value
```

Use application scope only when every session should deliberately observe the
same value:

```python
service_status = state("healthy", scope="application")
```

Session values, subscriptions, render bindings and callable handlers are
released after the final WebSocket disconnect and idle grace period.

### WebSocket patches

When a browser event mutates state, Voodoo targets the `patch` message to the
owning UI session. It is never implicitly broadcast to other users.

## API reference

- `state(initial=None, *, scope="session") -> State` — create isolated state;
  pass `scope="application"` for deliberate process-wide sharing.
- `State.get()` — read the current value.
- `State.set(value)` — set a new value and notify subscribers.
- `State.update(fn)` — apply `fn` to the current value.
- `State.subscribe(fn) -> unsubscribe` — register a callback.
- `StateRenderer` — binds state cells to page functions for re-rendering.
