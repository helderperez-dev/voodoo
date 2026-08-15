# Voodoo State

Voodoo is not a React clone and should not be modeled as one.

## Preferred State Patterns

- derive UI from request + server state
- use forms and POST handlers for mutations
- persist important state in SQLite or another data store
- introduce websocket behavior only when the UX truly needs it

## Example Mutation Flow

```python
from voodoo.components import Button, Div, Form, Input, Text

count = 0


async def page(request):
    global count

    if request.method == "POST":
        form_data = await request.form()
        if form_data.get("action") == "increment":
            count += 1

    return Div(
        Text(f"Count: {count}"),
        Form(
            Input(type="hidden", name="action", value="increment"),
            Button("Increment", type="submit"),
            action="/",
            method="POST",
        ),
    )
```

## Guidance

- keep handlers explicit
- avoid fake client-state APIs
- prefer boring server-driven flows first
