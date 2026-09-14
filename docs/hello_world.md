# Hello World

## What it is

The smallest official Voodoo project starts with `voodoo create`. The generated
app is Store-first: local durable infrastructure lives in
`.voodoo/application.vstore` and requires no external database, queue, or
object server.

## Create the app

```bash
voodoo create hello
cd hello
voodoo dev
```

Open `http://localhost:8000` in your browser.

The generated project contains:

```text
hello/
├── main.py
├── voodoo.toml
├── pyproject.toml
├── app/
└── .voodoo/
    └── application.vstore   # created automatically on first run
```

`main.py` demonstrates persistent `Model` data, durable background work,
reactive UI state, events, and a local mock Agent. The persistent counter is
stored through Voodoo Store, so stopping and starting the process does not
reset the application record.

## Minimal page

If you only want a page, the application can still be tiny:

```python
from voodoo import App, Heading, Text, page

app = App()


@page("/")
def home():
    return Heading("Hello, Voodoo", level=1), Text("Build differently.")


if __name__ == "__main__":
    app.run()
```

No provider configuration is required. Starting the Runtime activates the
default Voodoo Store lifecycle.

## Persistent data

```python
from voodoo import Model


class Visit(Model):
    count: int


async def record_visit() -> Visit:
    visit = await Visit.first()
    if visit is None:
        return await Visit.create(count=1)
    visit.count += 1
    await visit.save()
    return visit
```

With the default configuration this record is stored in
`.voodoo/application.vstore`.

## Common usage

### With a layout

```python
from voodoo import Container, Heading, Text, page


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

## How it works

1. `voodoo dev` discovers `main:app` when the generated `main.py` is present.
2. The App lifespan opens one Runtime-owned `.voodoo/application.vstore`.
3. `Model`, durable queue work, events and canonical Execution reuse that Store.
4. `@page("/")` registers the SSR route.
5. The handler returns Components that Voodoo renders to HTML.
6. On graceful shutdown Runtime-owned adapters close before the Store handle.
7. On restart the same Store is reopened and durable state is recovered.

## External infrastructure

PostgreSQL, SQLite, Redis and S3 remain explicit adapters. Configure one only
when a workload needs it; a fresh app does not silently fall back to those
systems.

## API reference

- `App(app_dir="app")` — application Runtime facade.
- `App.run(host=None, port=None, *, reload=False)` — start the server.
- `page(path)` — decorator registering an HTML route.
- `Model` — Store-first persistent business-data facade.
- `voodoo create <name>` — create the official Store-first project scaffold.
- `voodoo dev` — run the development server with reload support.
