# Voodoo Components

Voodoo UI is built in Python with `voodoo.components`.

## Common Imports

```python
from voodoo.components import (
    Div,
    Text,
    Heading,
    Button,
    A,
    Input,
    Form,
    Nav,
    Header,
    Footer,
    Main,
    Section,
    Article,
    Aside,
    Figure,
    FigCaption,
    Time,
    Address,
    Img,
    Paragraph,
)
```

## Component Style

- children are passed positionally
- attributes are passed as keyword arguments
- use `className`, not `class`

Example:

```python
from voodoo.components import Button, Div, Heading, Text


def Hero():
    return Div(
        Heading("Hello, Voodoo!", level=1, className="text-5xl font-bold"),
        Text("Build your UI in Python.", className="text-zinc-400"),
        Button("Get Started", className="mt-6 rounded-xl px-4 py-2"),
        className="px-8 py-16",
    )
```

## Semantic HTML & SEO

For structure and SEO optimization, Voodoo provides native semantic HTML5 components. Use these instead of generic `Div`s when establishing page hierarchy:

```python
from voodoo.components import Main, Header, Footer, Section, Article, Nav


def BlogLayout():
    return Main(Header(Nav(...)), Section(Article(...)), Footer(...))
```

The `Img` component also enforces accessibility by requiring an `alt` attribute and raising a Python warning if omitted.

## Reusable Components

Prefer simple Python functions over class-heavy abstractions.

```python
from voodoo.components import Div, Heading, Text


def StatCard(title: str, value: str):
    return Div(
        Heading(title, level=3, className="text-sm uppercase tracking-wide"),
        Text(value, className="text-3xl font-semibold"),
        className="rounded-2xl border border-white/10 p-4",
    )
```

## Design Guidance

- use strong hierarchy
- favor restraint and clarity
- avoid generic AI-looking layouts
