# Voodoo Rules

These are the highest-priority rules for AI-generated code in Voodoo projects.

## Non-Negotiables

1. Build UI with `voodoo.components`.
2. Prefer `async def` for handlers, database work, and network I/O.
3. Use file-based routing inside `app/`.
4. Use `A` plus `voodoo.navigate()` for internal links.
5. Keep project data in `.data/`.
6. Use `aiosqlite` and `.data/voodoo.db` by default.

## Internal Navigation

Do not fall back to plain anchor behavior for internal navigation.

```python
from voodoo.components import A

A("Dashboard", href="/dashboard", onClick="voodoo.navigate('/dashboard')")
```

## Styling

- Use Tailwind utility classes through `className`
- Prefer premium, minimal layouts with clear hierarchy
- Avoid noisy dashboards, filler cards, and over-explained UI

## Project Shape

- `app/` holds routes and app-facing code
- `.data/` holds local data files such as SQLite
- `main.py` boots `create_app()`

## Runtime Constraints

If the app touches large cookies, analytics scripts, or websocket-heavy flows:

- set `WEBSOCKETS_MAX_LINE_LENGTH="8388608"`
- keep Uvicorn on `http="h11"`
- keep the large incomplete-event size setting in development entrypoints

## AI Behavior

When generating code:

- prefer small composable functions
- avoid importing patterns from unrelated frameworks unless clearly needed
- keep code readable before clever
