# Voodoo AI Skills

These are repeatable workflows an AI IDE should follow in Voodoo projects.

## Scaffold a Route

When asked to create a page or route:

1. map the requested URL to `app/.../page.py`
2. export `page(request, ...)`
3. return Voodoo components, not templates
4. use Tailwind classes through `className`

## Extract a Component

When asked to make something reusable:

1. create a small Python function
2. give it clean typed arguments
3. return `voodoo.components`
4. keep styling override-friendly

## Add Persistence

When asked to store or load data:

1. prefer `aiosqlite`
2. store data in `.data/voodoo.db`
3. keep reads and writes async
4. keep the first implementation simple

## Debug Navigation

When navigation is broken:

1. verify route file placement
2. verify path naming
3. verify `A(..., onClick="voodoo.navigate(...)")`

## Debug WebSocket / Cookie Issues

When large-cookie or websocket issues appear:

1. verify `WEBSOCKETS_MAX_LINE_LENGTH="8388608"`
2. verify `http="h11"`
3. verify the dev entrypoint preserves the websocket tuning
