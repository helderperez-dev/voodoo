# Voodoo Architecture

Voodoo is a Python-first web framework built on Starlette and Uvicorn.

The important mental model is:

- routes are files
- UI is Python
- rendering and navigation are framework-driven
- persistence is usually local SQLite unless the app chooses something else

## Standard Project Layout

```text
project/
├── app/
│   └── page.py
├── .data/
├── main.py
└── pyproject.toml
```

## Core Responsibilities

- `main.py`: creates and runs the app
- `app/`: contains routes, pages, and route-local logic
- `.data/`: stores local files such as `voodoo.db`

## Important Framework Behavior

- internal Voodoo API routes are mounted automatically
- the framework expects Python modules, not template files
- websocket and dev-server behavior matter more than in a plain CRUD app

## Good Architectural Defaults

- keep route files thin
- move reusable UI into small Python component functions
- isolate database code into helper functions when a page grows
- keep Voodoo-specific conventions intact before introducing abstractions
