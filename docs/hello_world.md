# Hello World

## What it is

The minimal Voodoo app — a single page that renders "Hello, World!" in the browser.

## Minimal example

```python
from voodoo import App, page, Text

app = App()


@page("/")
def home():
    return Text("Hello, World!")


if __name__ == "__main__":
    app.run()
```

Save as `main.py` and run:

```bash
python main.py
```

Or use the CLI:

```bash
voodoo dev
```

Open `http://localhost:8000` in your browser.

## Common usage

### With a layout

```python
from voodoo import App, page, Container, Heading, Text

app = App()


@page("/")
def home():
    return Container(
        Heading("Welcome", level=1),
        Text("Hello, World!"),
    )


if __name__ == "__main__":
    app.run()
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

## How it works

1. `App()` creates the application runtime (lazy — routes register before first request).
2. `@page("/")` registers an SSR HTML route.
3. The handler returns a `Component` (or string) that Voodoo renders to HTML.
4. `app.run()` starts the uvicorn dev server with the Voodoo startup banner.

## API reference

- `App(app_dir="app", *, theme=None)` — application runtime facade.
- `App.run(host=None, port=None, *, reload=False)` — start the dev server.
- `App.use(plugin)` — register a plugin callable.
- `page(path)` — decorator registering a GET HTML route.
