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
- `set_style_adapter(adapter)` — set the active style adapter.
