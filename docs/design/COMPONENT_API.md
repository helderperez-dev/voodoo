# Voodoo Component API

> Status: Sprint 25 foundation
> Principle: **Python expresses intent; Voodoo owns browser mechanics.**

## The quality bar

A Voodoo component is not a thin HTML wrapper. It is a product-level abstraction with coherent behavior, accessibility, styling, reactivity and developer ergonomics.

The common path should read like application intent:

```python
async def deploy(): ...


Button("Deploy", on_click=deploy, loading=deploying.get())
```

Not browser implementation:

```python
Button(
    "Deploy",
    onclick="sendSomething()",
    data_event="deploy",
    class_="...",
)
```

## API laws

1. Python callables are the default event API.
2. Semantic props come before HTML/CSS mechanics.
3. Excellent behavior is the default, not an opt-in preset.
4. Accessibility is generated from component meaning whenever possible.
5. Loading, disabled, error and empty states are first-class.
6. Components compose; they do not require a parallel frontend language.
7. Escape hatches remain available, but they are not the documented happy path.
8. One concept should have one predictable prop name across components.
9. The native Voodoo design system is the reference implementation.
10. Application code should remain understandable without knowing the browser transport.

## Canonical vocabulary

Interaction:

- `on_click`
- `on_change`
- `on_input`
- `on_submit`

State:

- `disabled`
- `loading`
- `checked`
- `open`
- `error`

Appearance:

- `variant`
- `tone`
- `size`
- `density`

Structure:

- `label`
- `description`
- `hint`
- `placeholder`
- `submit`

## Composition examples

### Form field

```python
Field(
    "Email",
    Input(name="email"),
    hint="Used for account notices",
    error=email_error.get(),
    required=True,
)
```

### Form action

```python
Form(
    Field("Device name", Input(name="name")),
    on_submit=enroll_device,
    submit="Enroll",
)
```

`submit="Enroll"` is intentionally semantic. Voodoo owns the browser-specific submit button type and event transport. Applications that need a custom action layout can still compose an explicit `Button(type="submit")` as an escape hatch.

### Switch

```python
Switch(
    "Live updates",
    description="Receive runtime changes immediately",
    checked=live.get(),
    on_change=set_live,
)
```

### Popover

```python
Popover(
    Button("Options", variant="ghost"),
    Stack(
        Text("Runtime actions"),
        Button("Restart", on_click=restart),
    ),
)
```

### Dense operational page

```python
Page(
    RuntimeStatus(...),
    DataTable(...),
    density="compact",
)
```

Density belongs to the page/system context; developers should not restyle each control individually.

## Visual contract

First-party components must follow `DESIGN_CONSTITUTION.md` and `DESIGN_REVIEW_CHECKLIST.md`.

The default visual language prioritizes:

- typography and spacing before containers;
- calm neutral surfaces;
- subtle functional borders;
- restrained radius;
- elevation only when layering is real;
- purposeful status color;
- immediate, quiet feedback;
- excellent light and dark modes;
- compact operational density without visual noise.

## Definition of a finished component

A component is complete only when its API, rendering, keyboard behavior, accessibility, responsive behavior, states, theme behavior and tests are coherent.

A screenshot is not the component.

## Catalog roadmap

Voodoo should grow by interface capability, not by matching another library's
component count. Each phase must be complete across native CSS, Tailwind,
keyboard behavior, accessibility, light/dark themes, and tests.

### Foundation: available

- feedback: `Alert`, `Progress`, `Spinner`, `Skeleton`;
- navigation: `Breadcrumb`;
- grouping: `ButtonGroup`;
- disclosure: `Accordion`;
- content: `Kbd`, `AspectRatio`.

### Interaction kernel: available

The shared browser runtime now provides:

- focus trapping and focus restoration;
- dismissable layers and outside-click handling;
- native top-layer stacking;
- roving keyboard focus for tabs and menus;
- anchored positioning;
- live-region announcements and timed toast dismissal;
- persistent adaptive sidebar state with component-owned mode policies;
- integrated sidebar controls with a separate hidden-state launcher.

It powers `Tabs`, `DropdownMenu`, `Drawer`, modal controls, `Toast`,
`Snackbar`, and adaptive navigation. Building those behaviors once keeps
component APIs consistent and avoids a separate JavaScript implementation in
every primitive.

### Interaction extensions: next

- alert dialog with consequence-aware confirmation;
- toggle and segmented-control groups;
- pagination;
- menu subgroups, checkbox items, and typeahead;
- command palette;
- swipe-to-dismiss notifications on touch devices.

### Advanced inputs

After the interaction kernel:

- `Combobox` and autocomplete;
- `Slider` and range inputs;
- `DatePicker` and calendar;
- `InputGroup` and password input;
- file upload and drop zone;
- checkbox/radio card groups.

### Rich application surfaces

Add only when the underlying use cases demand them:

- command palette;
- data list and description list;
- scroll area and resizable panels;
- carousel;
- charts;
- tree view.

The priority order is intentional: navigation, feedback, forms, and overlays
unlock more real products than decorative or specialized widgets.
