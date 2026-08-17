# Reactive State

## What it is

`state(initial)` creates an observable value cell. Read with `get()`, update with `set()` / `update()`, and subscribe to changes with `subscribe()`. When a state cell changes inside an event handler, Voodoo re-renders the page and broadcasts a DOM patch over WebSocket — you write zero JS.

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
from voodoo import page, state, Div, Text, Button

counter = state(0)


@page("/")
def counter_page():
    return Div(
        Text(f"Count: {counter.get()}"),
        Button("Increment", onclick="vd.event('increment', 'counter')"),
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

### StateRenderer

The `StateRenderer` binds state cells to page functions and re-renders on change:

```python
from voodoo.ui.state import StateRenderer

renderer = StateRenderer()
renderer.bind("element-id", my_page_func, [count])
```

When `count` changes, call `renderer.rerender("element-id")` to broadcast a DOM patch.

### WebSocket patches

When the browser sends an event (e.g. button click), the server-side event handler mutates state, and Voodoo broadcasts a `patch` message over WebSocket. The client swaps the element's `outerHTML`.

## API reference

- `state(initial=None) -> State` — create a reactive cell.
- `State.get()` — read the current value.
- `State.set(value)` — set a new value and notify subscribers.
- `State.update(fn)` — apply `fn` to the current value.
- `State.subscribe(fn) -> unsubscribe` — register a callback.
- `StateRenderer` — binds state cells to page functions for re-rendering.
