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
)
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
- Built-in components: `Div`, `Flex`, `Stack`, `Grid`, `Box`, `Container`, `Page`, `Button`, `Card`, `Text`, `Heading`, `Badge`, `Avatar`, `Divider`, `Dialog`, `Modal`, `Form`, `Label`, `Input`, `Textarea`, `Select`, `Option`, `Checkbox`, `Radio`, `Table`, `List`, `ListItem`, `Nav`, `Header`, `Footer`, `Main`, `Section`, `Article`, `A`, `Link`.
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
  `voodoo.scrollToBottom(id)`, `voodoo.onEnter(el, handler)`, plus automatic
  chat behaviors (`setupChatBehaviors`) re-applied after every DOM patch.
- `set_style_adapter(adapter)` — set the active style adapter.
