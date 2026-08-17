# Hello World

## What it is

The minimal Voodoo app — a single page that renders "Hello, Voodoo!" in the browser.

## Minimal example

```bash
voodoo new hello
cd hello
voodoo dev
```

The scaffolded `app/page.py`:

```python
from voodoo import page, Div, Heading, Text


@page("/")
def home():
    return Div(
        Heading("Hello, Voodoo", level=1),
        Text("Build differently."),
    )
```

Open `http://localhost:8000` in your browser.

That's the entire application. No `main.py`, no configuration, no infrastructure setup.

## Common usage

### With a layout

```python
from voodoo import page, Container, Heading, Text


@page("/")
def home():
    return Container(
        Heading("Welcome", level=1),
        Text("Hello, World!"),
    )
```

### Async handler

```python
@page("/")
async def home():
    result = await fetch_data()
    return Text(f"Data: {result}")
```

### With dynamic routes

```python
@page("/users/{id}")
async def user_profile(id: int):
    return Text(f"User #{id}")
```

### Using the App class (optional)

For advanced use cases, you can create a `main.py`:

```python
from voodoo import App, page, Text


@page("/")
def home():
    return Text("Hello, World!")


if __name__ == "__main__":
    app = App()
    app.run()
```

This is an optional escape hatch. The canonical experience is `voodoo dev` with `app/page.py`.

## How it works

1. `voodoo dev` discovers the app (uses `voodoo.core:app` when no `main.py` exists).
2. `@page("/")` registers an SSR HTML route.
3. The handler returns a `Component` that Voodoo renders to HTML.
4. The Starlette app is built lazily on first request.

## API reference

- `page(path)` — decorator registering a GET HTML route.
- `App(app_dir="app")` — application runtime facade (optional, for advanced use cases).
- `App.run(host=None, port=None, *, reload=False)` — start the dev server.
