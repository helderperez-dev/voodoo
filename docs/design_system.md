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
| On-color | `--vd-color-on-*` | `on-primary`, `on-secondary` (text/icons on a solid fill, per mode) |
| Spacing | `--vd-space-*` | `xs`, `sm`, `md`, `lg`, `xl`, `xxl`, `xxxl` |
| Radius | `--vd-radius-*` | `sm`, `md`, `lg`, `xl`, `xxl`, `full` |
| Shadow | `--vd-shadow-*` | `sm`, `md`, `lg` |
| Motion | `--vd-motion-*` | `fast`, `normal`, `slow` |
| Breakpoints | `--vd-breakpoint-*` | `sm`, `md`, `lg`, `xl` (mobile-first) |
| Code | `--vd-code-*` | `background`, `surface`, `border`, `text`, `comment`, `keyword`, `function`, `string`, `live` |
| Typography | `--vd-text-*`, `--vd-leading-*`, `--vd-weight-*`, `--vd-font-*` | size scale, line heights, weights, font families (incl. `--vd-font-display`) |

Derived accent tokens (`--vd-color-secondary-soft`, `-line`, `-glow`,
`--vd-color-border-soft`) are computed with `color-mix` at use time, so they
track light/dark automatically without re-defining them per mode.

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
radius, discreet shadows, and excellent dark mode. The `primary` action color
inverts per mode — near-black in light mode, near-white in dark mode — while the
indigo `secondary` token drives links, focus rings, and accents so interactive
elements stay visible in every theme.

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

## Chrome components

Beyond the primitive components (`Button`, `Card`, `Input`, …), Voodoo ships a
page-level **chrome** tier for building navigation, heroes, and marketing/landing
sections without hand-rolled CSS:

| Component | Purpose |
|---|---|
| `Navbar` / `NavLink` | Sticky, backdrop-blurred top bar and its links (`active` state) |
| `Brand` | Wordmark/link set in the display face |
| `ThemeToggle` | Button that flips `.dark` and persists the choice in a cookie |
| `Hero` / `PageHero` | Landing hero vs. compact interior-page hero |
| `Eyebrow` / `Chip` | Small uppercase accent label / compact status pill |
| `CodeBlock` | Syntax-ready `<pre><code>` (HTML-escaped, uses `--vd-code-*`) |
| `Stats` / `Stat` | Responsive metric row with big display values |
| `CTABand` | Full-width call-to-action band on the accent tint |
| `BackLink` / `LinkArrow` | Muted back link / accent link with animated arrow |
| `FeatureCard` | Elevated card that lifts on hover |

All of these render semantic `vd-*` classes and require no CSS of their own;
`generate_component_css()` supplies the rules (including motion keyframes and a
`prefers-reduced-motion` guard).

## Themes as modules (presets)

A **theme preset** is a portable, shareable theme package: a JSON-only
`theme.json` (the same shape `Theme.model_dump()` produces) plus an optional
sibling `custom.css`. The project root stays minimal — no `styles.css` in the
root; custom CSS lives in an organized `.voodoo/theme/` folder.

Resolution order (first match wins):

1. An explicit path or URL (`App(theme="path/to/theme.json")`).
2. The project preset at `.voodoo/theme/theme.json`.
3. A built-in preset (`default`, `ember-paper`).
4. A user-installed preset at `~/.voodoo/themes/<name>/theme.json`.
5. A PyPI package named `voodoo-theme-<name>` exposing `theme.json`.

```toml
# voodoo.toml
[theme]
preset = "ember-paper"   # name | path | URL
mode = "dark"            # dark | light | system
```

Use the CLI to manage presets:

```bash
voodoo theme list                 # discover available presets
voodoo theme use ember-paper      # snapshot into .voodoo/theme/
voodoo theme init                 # snapshot current + scaffold custom.css
voodoo theme install my-theme     # pip install voodoo-theme-my-theme
```

A preset's `custom.css` is injected *after* the framework CSS, so it can add
theme-specific chrome (fonts, glow, terminal styling) the token set does not
model. For font loading, self-host or `@import` the faces from `custom.css` —
built-ins stay zero-network by referencing faces by name with system fallbacks.

### Built-in presets

- **`default`** — the stock, minimalist Apple × Linear × Vercel × Raycast look.
- **`ember-paper`** — warm paper surfaces, an ember accent (`#E8A33D` dark /
  `#B45309` light), and editorial type (Fraunces display, Schibsted Grotesk
  body, IBM Plex Mono) with a soft `--vd-glow` halo token.

## Inline custom CSS

Use `css={}` for one-off inline overrides on individual components (the token
system is the preferred path; this is the escape hatch):

```python
Div(Text("Centered"), css={"text_align": "center", "margin_top": "20px"})
```
