# Components

## What it is

Voodoo uses a React-like component system in pure Python. Components are Python classes that render to HTML. No templates, no JSX, no separate markup files.

## Minimal example

```python
from voodoo import Div, Text, Button

card = Div(Text("Hello"), Button("Click me", onclick="doSomething()"))
print(card.render())
# <div>Hello<button onclick="doSomething()">Click me</button></div>
```

## Common usage

### Layout components

```python
from voodoo import Container, Flex, Stack, Grid

layout = Container(
    Flex(Heading("Title"), Text("Body")),
    Stack(Text("Item 1"), Text("Item 2")),
)
```

Layout is expressed through semantic props, not utility classes:

| Component | Props |
|---|---|
| `Flex` | `direction`, `justify`, `items`, `wrap`, `gap` |
| `Grid` | `cols`, `gap` |
| `Container` | `size`, `centered` |
| `Page` | `size`, `pad` |
| `Stack` | `gap` (vertical `Flex`) |

```python
from voodoo import Flex, Grid, Page, Stack

ui = Page(
    Stack(
        Grid("a", "b", "c", cols="3", gap="md"),
        Flex("left", "right", direction="row", justify="between", gap="sm"),
        gap="lg",
    )
)
```

See [Design System](./design_system.md) for the full token, theme, and adapter
reference.

### Cards and content

```python
from voodoo import Card, Heading, Text, Badge

profile = Card(
    Heading("Ada Lovelace", level=2),
    Badge("Admin"),
    Text("ada@example.com"),
    variant="elevated",
    padding="xl",
)
```

Cards support `default`, `elevated`, `outline`, `ghost`, and `interactive`
variants with `none`, `sm`, `md`, `lg`, or `xl` padding. Every component also
accepts token-based `color`, `background`, and `border_color` props such as
`background="violet-950"`; see [Design System](./design_system.md#color-palette).

### Interface foundations

Common feedback, navigation, disclosure, and content patterns are available
without custom CSS:

```python
from voodoo import (
    Accordion,
    AccordionItem,
    Alert,
    Breadcrumb,
    BreadcrumbItem,
    Button,
    ButtonGroup,
    Kbd,
    Progress,
    Spinner,
)

page_tools = ButtonGroup(
    Button("List", variant="outline"),
    Button("Grid", variant="outline"),
    label="View",
)

navigation = Breadcrumb(
    BreadcrumbItem("Projects", "/projects"),
    BreadcrumbItem("Voodoo", "/projects/voodoo"),
    BreadcrumbItem("Settings"),
)

status = Alert(
    "The new configuration is active.",
    title="Deployment complete",
    tone="success",
)

details = Accordion(
    AccordionItem("Runtime", "Execution and worker settings", open=True),
    AccordionItem("Security", "Authentication and access policies"),
    variant="contained",
)

loading = Progress(72, label="Deployment progress", tone="success")
shortcut = Kbd("Cmd+K")
```

`Alert` supports `soft`, `outline`, and `solid` variants with semantic tones.
`Progress` can be determinate or indeterminate. `Accordion` uses native
`details`/`summary` elements, preserving keyboard behavior without application
JavaScript.

### Adaptive application UI

Voodoo includes the interaction patterns needed by desktop, mobile, and
installable PWA interfaces:

```python
from voodoo import (
    AppShell,
    BottomNav,
    BottomNavItem,
    Button,
    Drawer,
    DropdownMenu,
    Icon,
    MenuItem,
    Sidebar,
    SidebarItem,
    Snackbar,
    Tab,
    Tabs,
    ToastRegion,
)

sidebar = Sidebar(
    SidebarItem("Home", href="/", icon=Icon("home"), active=True),
    SidebarItem("Settings", href="/settings", icon=Icon("settings")),
    brand="Acme",
    logo="A",
    brand_href="/",
    brand_label="Acme home",
    mode="expanded",
    modes=("expanded", "rail"),
    mobile_mode="hidden",
    dismiss_mode="hidden",
)

shell = AppShell(
    Main("Application content"),
    sidebar=sidebar,
    content_padding="lg",
    bottom_nav=BottomNav(
        BottomNavItem("Home", "/", icon=Icon("home"), active=True),
        BottomNavItem("Settings", "/settings", icon=Icon("settings")),
    ),
)

account_menu = DropdownMenu(
    Button("Account", variant="ghost"),
    MenuItem("Profile", href="/profile"),
    MenuItem("Sign out", on_select=sign_out, destructive=True),
)

mobile_filters = Drawer(
    Button("Filters", variant="outline"),
    filter_form,
    title="Filters",
    side="bottom",
)

content = Tabs(
    Tab("overview", "Overview", overview),
    Tab("activity", "Activity", activity),
)

notifications = ToastRegion(
    Snackbar("Changes saved", action=Button("Undo", on_click=undo))
)
```

Sidebars support `expanded`, `rail`, and `hidden` modes. Their behavior belongs
to the `Sidebar` itself: `modes` defines the toggle cycle, `mobile_mode`
defines its compact-viewport starting state, and `dismiss_mode` defines where
the mobile backdrop returns it. The default toggle cycle is
`("expanded", "rail")`, so compacting the sidebar does not unexpectedly hide
it on the next click. Include `"hidden"` explicitly when full closing is part
of the product design.

`AppShell` automatically renders a compact `V.` / `Voodoo` placeholder brand,
uses a directional chevron for the desktop expand/collapse action, and exposes
a separate hamburger launcher only while the sidebar is fully hidden. In
expanded mode the chevron sits in the sidebar header; in rail mode it moves to
the bottom so branding and primary destinations remain uninterrupted.
Customize the lockup with `brand=` and `logo=`, make it navigable with
`brand_href=`, and provide an explicit accessible name with `brand_label=`
when the visual brand is a custom component. Pass both `brand` and `logo` as
`None` to remove the lockup. Set `sidebar_toggle=False` to disable the
generated controls. Modes are persisted independently for mobile and desktop.
Below `768px`, `BottomNav` becomes visible with safe-area padding.

`AppShell` also owns the default content gutter. `content_padding="lg"` uses a
responsive 16–24px inset so page headings and controls do not touch the
sidebar divider or viewport edges. Use `"none"` for intentionally edge-to-edge
surfaces such as maps, canvases, and full-bleed dashboards; `"sm"`, `"md"`,
and `"xl"` provide the other standard token-based options.

Drawers use native modal dialogs with focus restoration, Escape handling,
backdrop dismissal, and reduced-motion-aware transitions. Dropdown menus use
native popovers with anchored placement and Arrow/Home/End keyboard navigation.
Tabs implement linked ARIA states and roving keyboard focus.

Client-side code may also show transient feedback without constructing markup:

```javascript
voodoo.toast("Deployment complete", {title: "Ready", tone: "success"});
voodoo.snackbar("Connection restored");
```

### Forms

```python
from voodoo import Form, Input, Label, Button

login = Form(
    Label("Email", Input(type="email", name="email")),
    Label("Password", Input(type="password", name="password")),
    Button("Login", type="submit"),
)
```

### Chrome (page-level)

Ready-made building blocks for navigation, heroes, and landing sections — no
custom CSS required:

```python
from voodoo import (
    Navbar,
    NavLink,
    Brand,
    ThemeToggle,
    Hero,
    Eyebrow,
    Heading,
    Text,
    CodeBlock,
    Stats,
    Stat,
    CTABand,
    Button,
)

page = Hero(
    Eyebrow("Voodoo 1.0"),
    Heading("Ship fast", level=1, size="display"),
    Text("A programmable runtime for adaptive applications."),
    CodeBlock("pip install voodoo-framework", language="bash"),
    Stats(Stat("99.99%", "Uptime"), Stat("12ms", "Latency")),
    Navbar(
        Brand("Voodoo"),
        NavLink("Docs", href="/docs", active=True),
        ThemeToggle(),
    ),
)
```

| Component | Purpose |
|---|---|
| `Navbar` / `NavLink` | Sticky blurred top bar + links (`active`) |
| `Brand` | Wordmark link in the display face |
| `ThemeToggle` | Flips `.dark`, persists via cookie |
| `Hero` / `PageHero` | Landing vs. interior hero |
| `Eyebrow` / `Chip` | Uppercase accent label / status pill |
| `CodeBlock` | Escaped `<pre><code>` using `--vd-code-*` tokens |
| `Stats` / `Stat` | Responsive metric row |
| `CTABand` | Full-width accent call-to-action |
| `BackLink` / `LinkArrow` | Muted back link / accent arrow link |
| `FeatureCard` | Elevated card that lifts on hover |

### Custom components

```python
from voodoo import Component, Div, Text


class UserCard(Component):
    tag = "div"

    def __init__(self, name, email):
        super().__init__(Text(name), Text(email))


# Use it
card = UserCard("Ada", "ada@example.com")
print(card.render())
```

## Advanced

### Styling with `css={}`

```python
Div(Text("Centered"), css={"text_align": "center", "margin_top": "20px"})
```

### Semantic tone

```python
Text("Success!", tone="success")
Text("Warning!", tone="warning")
Text("Danger!", tone="danger")
```

### Style adapters

Voodoo supports pluggable style adapters. `VoodooCSSAdapter` is the default CSS adapter; `TailwindAdapter` ships out of the box as an alternative:

```python
from voodoo import set_style_adapter, VoodooCSSAdapter, TailwindAdapter

# Default
set_style_adapter(VoodooCSSAdapter())

# Or use Tailwind
set_style_adapter(TailwindAdapter())
```

## API reference

- `Component` — base class for all UI elements.
- `Component.render()` — serialize to HTML.
- Built-in components: `AppShell`, `Div`, `Flex`, `Stack`, `Grid`, `Box`, `Container`, `Page`, `Sidebar`, `SidebarItem`, `SidebarToggle`, `BottomNav`, `BottomNavItem`, `Button`, `ButtonGroup`, `Card`, `Text`, `Heading`, `Badge`, `Avatar`, `Divider`, `Alert`, `Progress`, `Spinner`, `Breadcrumb`, `BreadcrumbItem`, `Accordion`, `AccordionItem`, `Kbd`, `AspectRatio`, `Dialog`, `Modal`, `ModalTrigger`, `ModalClose`, `Drawer`, `DropdownMenu`, `MenuItem`, `MenuSeparator`, `Tabs`, `Tab`, `ToastRegion`, `Toast`, `Snackbar`, `Form`, `Label`, `Input`, `Textarea`, `Select`, `Option`, `Checkbox`, `Radio`, `Table`, `List`, `ListItem`, `Nav`, `Header`, `Footer`, `Main`, `Section`, `Article`, `A`, `Link`.
- Chrome components: `Navbar`, `NavLink`, `Brand`, `ThemeToggle`, `Hero`, `PageHero`, `Eyebrow`, `Chip`, `CodeBlock`, `Stats`, `Stat`, `CTABand`, `BackLink`, `FeatureCard`, `LinkArrow`.
- Semantic HTML: `Nav`, `Header`, `Footer`, `Main`, `Section`, `Article`, `Aside`, `Figure`, `FigCaption`, `Address`, `Paragraph`, `Time`, `Img`.
- Icons & Markdown:
  - `Icon(name, size="md", label=None)` — curated inline-SVG icons
    (`send`, `user`, `bot`, `plus`, `trash`, `check`, `x`, `search`, `menu`,
    `sidebar`, `settings`, `refresh`, `copy`, `edit`, `chevron-right/left/down`,
    `arrow-right`, `loader`, `sparkles`, `message`, `paperclip`, `stop`,
    `sun`, `moon`, `eye`); stroke-based, `currentColor`, sized via `size`
    (`sm|md|lg|xl`); unknown names render a placeholder dot (never raise).
  - `Markdown(source)` — safe, dependency-free Markdown → HTML (headings,
    `**bold**` / `*italic*` / `` `code` ``, fenced blocks, lists, blockquotes,
    http(s)-only links; **all raw HTML is escaped**).
- Chat primitives:
  - `MessageList(*messages)` — scrollable transcript; auto-scrolls on patch
    (via the client SDK).
  - `ChatMessage(*children, role="user")` — a chat bubble; `role` ∈
    `user | assistant | system | tool` selects the `vd-chat-message--{role}`
    styling.
  - `StreamingText(content, done=False)` — live-streaming text with an
    animated caret (hidden when `done=True`).
  - `Composer(on_send="evt", placeholder="…", disabled=False)` — chat input
    bar: auto-growing textarea + send button; Enter sends, Shift+Enter
    newlines (wired by the client SDK — zero hand-written JS).
  - `Sidebar(*children)` — app sidebar shell styled by `vd-sidebar`.
- Client JS SDK (`static/client.js`, auto-included): `voodoo.navigate(path)`,
  `voodoo.scrollToBottom(id)`, `voodoo.toast(message, options)`,
  `voodoo.snackbar(message, options)`, plus automatic interaction and chat
  behaviors re-applied after every DOM patch.
- `set_style_adapter(adapter)` — set the active style adapter.
