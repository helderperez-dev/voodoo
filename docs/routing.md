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

```
app/
  pages/
    index.py        → /
    about.py        → /about
    users/
      [id].py       → /users/{id}
```

Each file defines a `page` function:

```python
# app/pages/about.py
from voodoo import Text


def page():
    return Text("About us")
```

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
- File-based: `app/pages/` directory with `page()` function in each file.
