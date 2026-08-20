# Design System

Voodoo ships a complete design system out of the box: design tokens, a theme
engine, a default semantic CSS adapter, and a library of polished components.
New apps look professional with **zero configuration** — no CSS files, no
utility classes, no build step.

## Architecture

```
                    VOODOO DESIGN SYSTEM
                             │
                ┌────────────┴────────────┐
                │                         │
           Design Tokens             Components
                │                         │
       ┌────────┼────────┐        ┌───────┼────────┐
       │        │        │        │       │        │
     Color   Type     Spacing   Button   Card    Input
       │        │        │        │       │        │
       └────────┴────────┴────────┴───────┴────────┘
                             │
                       Theme Engine
                             │
              ┌──────────────┼──────────────┐
              │              │              │
          Voodoo CSS      Tailwind       Custom CSS
```

The key principle: **components do not know that Tailwind exists.** Components
declare *semantic* intent (`variant`, `size`, `tone`, `level`), and a style
adapter resolves that intent to concrete class names.

## Design tokens

Every value is expressed as a `--vd-*` CSS custom property. Changing a token
re-styles every component instantly, at runtime, without re-rendering HTML.

| Group | Prefix | Examples |
|---|---|---|
| Color | `--vd-color-*` | `primary`, `secondary`, `background`, `surface`, `text`, `text-muted`, `border`, `success`, `warning`, `danger` |
| Spacing | `--vd-space-*` | `xs`, `sm`, `md`, `lg`, `xl`, `xxl`, `xxxl` |
| Radius | `--vd-radius-*` | `sm`, `md`, `lg`, `xl` |
| Shadow | `--vd-shadow-*` | `sm`, `md`, `lg` |
| Motion | `--vd-motion-*` | `fast`, `normal`, `slow` |
| Typography | `--vd-text-*`, `--vd-leading-*`, `--vd-weight-*`, `--vd-font-*` | size scale, line heights, weights, font families |

### Theming your app

Use `create_theme` for simple overrides, or build a full `Theme` model:

```python
from voodoo import App, create_theme

app = App(
    theme=create_theme(
        primary="#635BFF",
        secondary="#00D4AA",
        font="Inter",
        radius="lg",
        mode="dark",  # dark | light | system
    )
)
```

The default theme is minimalist and modern (Apple × Linear × Vercel × Raycast
aesthetic): generous whitespace, clean typography, subtle borders, moderate
radius, discreet shadows, and excellent dark mode.

## Style adapters

| Adapter | Class names | When to use |
|---|---|---|
| `VoodooCSSAdapter` | Semantic `vd-*` (e.g. `vd-button--primary`) | **Default.** Zero-config, no external CDN. |
| `TailwindAdapter` | Tailwind utility classes | Opt-in, when you already use Tailwind. |
| `NoopAdapter` | Bare element names | Minimal output, custom CSS only. |

```python
from voodoo import set_style_adapter, TailwindAdapter

set_style_adapter(TailwindAdapter())
```

`VoodooCSSAdapter` generates its stylesheet automatically via
`generate_component_css(theme)` and injects it into every page — you never
write CSS for built-in components.

## Layout primitives

Layout is first-class. Components express structure without utility classes:

| Component | Props | Output |
|---|---|---|
| `Flex` | `direction`, `justify`, `items`, `wrap`, `gap` | `vd-flex--col`, `vd-flex--justify-center`, … |
| `Grid` | `cols`, `gap` | `vd-grid--cols-3`, `vd-grid--gap-md` |
| `Container` | `size`, `centered` | `vd-container--xl`, `vd-container--centered` |
| `Page` | `size`, `pad` | `vd-page--lg`, `vd-page--pad` |
| `Stack` | `gap` | Vertical flex (`vd-flex--col`) with semantic gap |

```python
from voodoo import Page, Stack, Grid, Card, Badge, Heading

ui = Page(
    Stack(
        Heading("Features", level=1),
        Grid(
            Card(Stack(Badge("A"), Heading("One", level=3), gap="sm")),
            Card(Stack(Badge("B"), Heading("Two", level=3), gap="sm")),
            Card(Stack(Badge("C"), Heading("Three", level=3), gap="sm")),
            cols="3",
            gap="md",
        ),
        gap="lg",
    )
)
```

### Gap scale

Named gaps (`xs`…`xxxl`) resolve through the spacing tokens. Numeric gaps
(`gap="4"`) use a 4px base (`calc(0.25rem * 4)`), matching Tailwind's scale:

```python
Stack(gap="md")  # var(--vd-space-md)
Flex(gap="4")  # calc(0.25rem * 4) = 16px
Grid(cols="2", gap="6")  # calc(0.25rem * 6) = 24px
```

## Theme mode (dark / light / system)

`Theme.mode` accepts `"dark"`, `"light"`, or `"system"` (default `"dark"`).
The resolved mode is applied to the `<html class="...">` element, and an inline
script runs *before* the stylesheet to prevent a flash of the wrong theme:

1. Read the persisted `voodoo_theme` cookie (if any).
2. Fall back to `Theme.mode`.
3. Resolve `"system"` via `prefers-color-scheme`.
4. Toggle the `.dark` class on `<html>`.

The client runtime exposes `voodoo.setTheme(mode)` to switch themes at runtime
and persist the choice in the `voodoo_theme` cookie:

```javascript
voodoo.setTheme("light");
```

`to_css_variables()` emits `:root` (light values) and `.dark` (dark values), so
toggling `.dark` re-themes every component without a re-render.

## Custom CSS

Drop a `styles.css` file in your project root to layer custom CSS on top of the
theme (loaded by convention, next to the app directory). Use `css={}` for
inline overrides on individual components:

```python
Div(Text("Centered"), css={"text_align": "center", "margin_top": "20px"})
```
