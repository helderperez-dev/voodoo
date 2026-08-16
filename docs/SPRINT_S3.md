# Sprint 3 — Reactive State & Events

> Implementation tracking for S3. Derived from IMPLEMENTATION_PLAN.md §2.3–2.4.
> **Status**: Active (next sprint)

---

## Goal

Deliver `state()` reactive primitive and `@event` decorator so a developer
can build a live-updating UI with **zero JS**.

### Canonical example (acceptance test)

```python
from voodoo import App, page, state, event, Button, Text, Stack

count = state(0)


@event
async def increment(element_id, value):
    count.set(count.get() + 1)


@page("/")
def home():
    return Stack(
        Text(f"Count: {count.get()}"),
        Button("Increment", on_click="increment"),
    )
```

---

## Workstreams

### S3-1: `state()` reactive primitive
- [ ] `State` class: `get()`, `set()`, `update()`, `subscribe()`
- [ ] `state(initial)` factory function
- [ ] ContextVar-scoped to request (future: session/app)
- [ ] On `set()`/`update()`: notify subscribers with new value
- [ ] **File**: `voodoo/core/state.py` (new)

### S3-2: `@event` decorator
- [ ] `@event` auto-registers handler via `register_event`
- [ ] Handler sig: `async def handler(element_id: str, value: Any) -> None`
- [ ] Decorator returns original function (transparent)
- [ ] **File**: `voodoo/core/events.py` (extend)

### S3-3: Reactive rendering pipeline
- [ ] State change inside event handler → page re-render → WS patch
- [ ] `StateRenderer` binds state cells to page render functions
- [ ] On `state.set()`: re-run page function → render → `ws_manager.broadcast_patch`
- [ ] MVP: full subtree re-render, swap outerHTML (no diffing)
- [ ] **Files**: `voodoo/core/state.py`, `voodoo/core/routing.py`, `voodoo/core/render.py`

### S3-4: Client.js enhancement
- [ ] Reconnection backoff (exponential, capped at 5s)
- [ ] Reuse existing `patch` message type (no client change for state)
- [ ] **File**: `voodoo/client.js`

### S3-5: Exports & contract
- [ ] Export `state`, `event`, `State` from `voodoo/__init__.py`
- [ ] Update `__all__` and contract test
- [ ] **Files**: `voodoo/__init__.py`, `voodoo/core/__init__.py`, `tests/test_contract_api.py`

### S3-6: Tests
- [ ] `tests/test_state.py`: get/set/update/subscribe, unsubscribe, ContextVar
- [ ] `tests/test_events.py`: @event registration, dispatch, handler invocation
- [ ] `tests/test_reactive.py`: counter app — state→re-render→patch
- [ ] Full suite green; ruff clean; commit

---

## File Changes

| File | Action | Description |
|---|---|---|
| `voodoo/core/state.py` | NEW | State class, state() factory, StateRenderer |
| `voodoo/core/events.py` | MODIFY | Add @event decorator |
| `voodoo/core/__init__.py` | MODIFY | Export state, event |
| `voodoo/core/routing.py` | MODIFY | Track page functions for re-render |
| `voodoo/core/render.py` | MODIFY | Support re-render + patch broadcast |
| `voodoo/__init__.py` | MODIFY | Export state, event, State |
| `voodoo/client.js` | MODIFY | Reconnection backoff |
| `tests/test_state.py` | NEW | State primitive tests |
| `tests/test_events.py` | NEW | @event decorator tests |
| `tests/test_reactive.py` | NEW | Counter app integration test |
| `tests/test_contract_api.py` | MODIFY | Add state, event, State to __all__ |

---

## Exit Criteria

- [ ] Counter app works: state + Button → live updates, zero JS
- [ ] `@event` registers handlers transparently
- [ ] `state()` supports get/set/update/subscribe
- [ ] State change triggers re-render and WS patch
- [ ] 193+ tests passing; ruff clean; committed (no version bump)

---

## Non-Goals

- No virtual DOM / diffing (full subtree re-render)
- No per-client targeting (broadcast to all connections)
- No client-side state (server is source of truth)
- No session/app-scoped state (page-scoped only)
- No dependency tracking (explicit via page function closure)
