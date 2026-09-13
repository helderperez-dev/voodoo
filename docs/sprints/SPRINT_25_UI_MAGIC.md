# Sprint 25 — Voodoo UI Magic

> Status: WIP
> Theme: Python expresses intent; Voodoo owns browser mechanics.
> Purpose: Make Voodoo application development feel unusually elegant while the default visual result remains exceptionally polished.

## Product thesis

Voodoo UI must hide incidental browser complexity without hiding application meaning.

A developer should write Python that describes **what the interface is and what should happen**. Voodoo should decide how events are transported, how state invalidates rendered regions, how DOM patches are applied, how navigation preserves context, how accessibility metadata is emitted, and how the design system creates a coherent visual result.

The target feeling is:

> **Write almost nothing. Get something excellent. Change state. The interface simply responds.**

This sprint treats developer experience, interaction behavior and visual design as one system.

Canonical example:

```python
count = state(0)

async def increment():
    count += 1

@page("/")
def home():
    return Page(
        Stack(
            Heading("Counter"),
            Text(count),
            Button("Increment", on_click=increment),
        )
    )
```

There must be:

- no event-name string;
- no inline JavaScript;
- no manual DOM id wiring;
- no manual rerender call;
- no page reload;
- no hand-written CSS required for a professional result.

## Architectural laws

1. **Python callables are the event API.** String event names remain compatibility-only.
2. **No inline JavaScript in component output.** Components emit semantic `data-vd-*` bindings; the Voodoo client runtime uses delegated listeners.
3. **State invalidates UI automatically.** Dependencies are discovered during rendering and re-discovered after every rerender.
4. **Navigation is soft by default.** Internal links update history and replace the relevant page region without a browser reload.
5. **The DOM is an implementation detail.** Developers should not need element IDs for ordinary interactions.
6. **Reactivity preserves context.** Focus, selection, scroll and transient input state should survive safe patches where possible.
7. **Design Constitution is executable guidance.** Components must use semantic tokens, restrained hierarchy, complete states, accessibility and responsive behavior.
8. **Defaults are the product.** Advanced customization is possible, but common interfaces should look finished with very little code.
9. **Progressive complexity.** Simple usage stays simple; escape hatches exist behind explicit APIs.
10. **One component model.** Do not create a parallel frontend framework beside `Component`.

## Current gaps found in code

- `Button(on_click=...)` accepts a string and renders an inline `onclick` JavaScript expression.
- `@event` registers handlers by function name in a global string-keyed registry.
- Browser event transport exposes `vd.event("name", ...)` directly.
- `navigate()` calls `window.location.reload()`.
- State rerendering patches a complete subtree and does not re-track conditional dependencies after each render.
- WebSocket patches are broadcast globally instead of being designed around UI/session ownership.
- Event payloads expose browser transport details (`element_id`, `value`) in ordinary handler signatures.
- Components have inconsistent interaction APIs and incomplete state semantics.
- The library contains useful primitives, but it does not yet fully implement the component layering and behavioral completeness required by `docs/design/DESIGN_CONSTITUTION.md`.

## 25.1 — Callable event bindings

### Goal

Make direct Python callables the primary interaction API.

### Target API

```python
async def save():
    ...

Button("Save", on_click=save)
```

Payload-aware handlers:

```python
async def search(value: str):
    ...

Input(on_change=search)
```

Optional event-object handlers:

```python
async def inspect(event: UIEvent):
    print(event.value, event.element_id, event.meta)
```

### Implementation

- Add opaque event binding IDs managed by Voodoo.
- Register callables by binding identity, not public function name.
- Components render `data-vd-event-*` attributes instead of inline JS.
- Add delegated browser event handling for click/input/change/submit/keydown.
- Add signature-aware Python dispatch for zero-arg, value-arg and `UIEvent` handlers.
- Keep `@event` and string names temporarily for compatibility, but mark as legacy path.
- Prevent accidental handler collisions between same-named functions.
- Never serialize Python function names as the public browser contract when a callable is supplied.

### Acceptance

```python
Button("Run", on_click=run)
```

renders no `onclick=` attribute and invokes `run` over the Voodoo transport.

## 25.2 — Reactive render graph

### Goal

Make state changes feel immediate and require no reload or manual binding.

### Implementation

- Re-track state reads on every rerender.
- Rebind dependencies atomically after render.
- Deduplicate rerenders occurring in the same event-loop tick.
- Avoid rerender storms when multiple State cells change in one handler.
- Introduce explicit reactive regions so Voodoo can patch smaller subtrees than `root`.
- Preserve backward-compatible page-level automatic tracking.
- Add safe batching API internally; ordinary developers should not need it.
- Add tests for conditional dependencies:
  - render reads A;
  - state changes render branch;
  - new render reads B;
  - later B updates rerender while stale A no longer does.

## 25.3 — Context-preserving DOM patching

### Goal

Patches should feel like state changes, not page replacement.

### Implementation

- Keep stable root nodes.
- Preserve focused element when identity remains available.
- Preserve text selection/caret where safe.
- Preserve scroll position by default; support explicit auto-scroll regions.
- Re-run delegated behavior after patches without component-specific wiring.
- Add motion hooks using restrained design-system transitions.
- Respect `prefers-reduced-motion`.

## 25.4 — Soft navigation

### Goal

Internal navigation should not reload the page.

### Implementation

- Intercept same-origin Voodoo links.
- Fetch/render target page through a Voodoo partial-page contract.
- Patch the root/content region.
- `history.pushState` and `popstate` support.
- Preserve ordinary browser semantics for modifier-click, target, download and external URLs.
- Update title and relevant SEO document metadata on navigation.
- Expose Python-side `navigate()` / redirect abstraction where useful.
- Full reload remains an explicit escape hatch.

## 25.5 — Component API normalization

### Goal

Make component code read like a small, coherent language.

### Rules

- Prefer semantic props over HTML/browser mechanics.
- Consistent naming: `on_click`, `on_change`, `on_submit`, `disabled`, `loading`, `tone`, `variant`, `size`.
- `loading=True` should produce correct disabled/aria behavior and visual feedback without custom code.
- Components with actions should have accessible defaults.
- Common composition should require fewer wrappers.
- Avoid props that only mirror CSS implementation when a semantic concept exists.

### Core primitive audit

- Button
- Input
- Textarea
- Select
- Checkbox
- Radio
- Switch (add)
- Text
- Heading
- Stack
- Grid
- Divider
- Dialog
- Popover (add/complete)
- Tooltip (add/complete)
- Form
- Link

## 25.6 — Voodoo Design System 2

### Goal

Align component implementation with the Design Constitution, not merely the current CSS.

### Visual principles

- calm precision;
- typography/spacing before borders;
- low-cardification layouts;
- neutral surfaces doing most structural work;
- purposeful color;
- compact but comfortable type scale;
- small consistent radius scale;
- elevation only for actual layering;
- subtle motion explaining cause/effect;
- excellent light and dark modes.

### Work

- Audit token scale: color, typography, spacing, radius, border, shadow, motion, focus.
- Remove arbitrary values from first-party components where semantic tokens exist.
- Normalize sizes across controls.
- Normalize focus rings and keyboard states.
- Normalize loading/error/success/disabled states.
- Ensure responsive touch targets.
- Add density support (`comfortable`, `compact`) for operational products.
- Make branded themes possible without forking components.

## 25.7 — Product components

Implement/rework reusable Layer 2 components from the constitution:

- StatusBadge
- Metric
- EmptyState
- DataTable
- Timeline
- EventRow
- ActivityFeed
- InspectorPanel / Drawer
- LogViewer
- CommandBar
- ResourcePicker
- Skeleton
- Toast / inline feedback

Every component requires behavior, state, accessibility and responsive tests, not only snapshot appearance.

## 25.8 — Voodoo system components

Create Layer 3 components that make Voodoo operational systems visibly distinct:

- RuntimeStatus
- AgentStatus
- DeviceStatus / DeviceCard
- ExecutionStatus / ExecutionTimeline
- ApprovalCard
- WorldEntityInspector
- ObservationFeed
- CapabilityList
- PolicyDecision
- EdgeNode
- TelemetryPanel

These components must consume canonical runtime concepts rather than invent UI-only copies of runtime state.

## 25.9 — Delight, docs and acceptance app

### Goal

Prove that Voodoo feels magical in real application code.

Build a small first-party acceptance application demonstrating:

- callable Python events;
- reactive local state;
- async handlers;
- forms;
- soft navigation;
- loading/error/success feedback;
- dialog/inspector behavior;
- live runtime data;
- responsive layout;
- light/dark mode;
- zero custom JS;
- near-zero custom CSS.

### Final quality bar

A reviewer should be able to look at the Python source and immediately understand the interface.

The rendered application should look intentionally designed without requiring visual repair by the application developer.

## Definition of Done

Sprint 25 is complete when all of the following are true:

- Python callables are the documented default event API.
- First-party interactive components emit no inline event JavaScript.
- State mutations cause automatic UI updates without page reloads.
- Reactive dependencies are correct after conditional rerenders.
- Internal navigation is soft and browser-history-correct.
- Core components conform to the Design Review Checklist.
- Light/dark modes and keyboard interaction are verified.
- Product/system component layers have a coherent first implementation.
- An acceptance app demonstrates the complete experience with minimal Python.
- Existing string event APIs remain temporarily compatible or have an explicit migration path.
- CI, type checks and relevant interaction tests are green.

## North-star developer experience

The API should converge toward code that feels inevitable:

```python
from voodoo import App, page, state
from voodoo.ui import Button, Heading, Page, Stack, Text

app = App()
count = state(0)

async def increment():
    count.set(count.get() + 1)

@page("/")
def home():
    return Page(
        Stack(
            Heading("Voodoo"),
            Text(f"Count: {count.get()}"),
            Button("Increment", on_click=increment),
        )
    )

app.run()
```

Voodoo owns the WebSocket event ID, payload transport, dependency tracking, rerender scheduling, DOM patch, focus restoration, styling, accessibility and interaction feedback.

That invisible machinery is the product.
