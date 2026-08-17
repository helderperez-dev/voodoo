# Routing

## What it is

Voodoo provides two routing mechanisms: decorator-based (`@page`) and file-based (convention). Both produce SSR HTML routes.

## Minimal example

```python
from voodoo import page, Text


@page("/")
def home():
    return Text("Home page")


@page("/about")
def about():
    return Text("About page")
```

## Common usage

### Dynamic routes

```python
@page("/users/{id}")
async def user_profile(id: int):
    return Text(f"User #{id}")
```

Path parameters are injected by name and coerced to the annotation type.

### Async handlers

```python
@page("/dashboard")
async def dashboard():
    data = await fetch_stats()
    return Card(Text(f"Visitors: {data['visitors']}"))
```

### Request injection

```python
from starlette.requests import Request


@page("/profile")
async def profile(request: Request):
    user = request.state.user
    return Text(f"Hello {user.username}")
```

### User injection

```python
@page("/settings")
async def settings(user):
    return Text(f"Settings for {user.email}")
```

### File-based routing

Voodoo's default scaffold uses **folder-based routing**: each directory under `app/` that contains a `page.py` file maps to a route based on its path. `voodoo dev` auto-discovers the app without requiring a `main.py` entrypoint.

```
app/
  page.py              → /
  about/
    page.py            → /about
  users/
    [id]/
      page.py          → /users/{id}
```

Each `page.py` defines a `page` function (the file convention), optionally accepting `request` and typed path parameters:

```python
# app/about/page.py
from voodoo import Page, Text
from voodoo.seo import SEO


def page(request):
    return SEO(title="About"), Page(Text("About us"))
```

Bracket folders (`[id]`) create dynamic segments; the parameter is injected by name and coerced to its annotation:

```python
# app/users/[id]/page.py
from voodoo import Text


def page(request, id: int):
    return Text(f"User #{id}")
```

For projects that prefer one file per page, the `app/pages/` directory is also supported for backward compatibility. When present, each file maps to a route based on its path:

```
app/
  pages/
    index.py        → /
    about.py        → /about
    users/
      [id].py       → /users/{id}
```

> **Note:** Folder-based routing (`app/<segment>/page.py`) is the scaffold default. `app/pages/` (plural, file-per-page) is supported but not the scaffold default. The `@page` decorator remains available for explicit, imperative registration (e.g. inside a `main.py`).

## Advanced

### Returning SEO metadata

```python
from voodoo.seo import SEO


@page("/")
def home():
    seo = SEO(title="My App", description="Best app ever")
    return seo, Text("Welcome")
```

### Returning raw responses

If a handler returns a Starlette `Response`, it is passed through untouched.

## API reference

- `page(path)` — decorator registering a GET HTML route.
- `page_registry` — global registry of `@page` routes.
- `call_page(func, request)` — invoke a page handler (used internally).
- Folder-based routing: `app/<segment>/page.py` files, each defining a `page(request, ...)` function (the scaffold default). `app/pages/` (file-per-page) is supported for backward compatibility.
