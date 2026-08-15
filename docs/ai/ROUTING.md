# Voodoo Routing

Voodoo uses file-based routing from the `app/` directory.

## Route Mapping

- `app/page.py` -> `/`
- `app/about/page.py` -> `/about`
- `app/dashboard/settings/page.py` -> `/dashboard/settings`

## Dynamic Segments

Use bracket folders for path parameters.

- `app/users/[id]/page.py` -> `/users/:id`

Example:

```python
from voodoo.components import Div, Text


async def page(request, id: str):
    return Div(Text(f"User: {id}"))
```

## Internal Links

For internal navigation, use the Voodoo `A` component with `voodoo.navigate()`.

```python
from voodoo.components import A


A("Open settings", href="/settings", onClick="voodoo.navigate('/settings')")
```

Do not treat Voodoo like a traditional multi-page app where plain anchors are always enough.
