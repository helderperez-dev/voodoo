# Voodoo AI Kit

This folder is the canonical AI context for Voodoo projects.

Any AI IDE working on a Voodoo app should read these files in order:

1. `RULES.md`
2. `ARCHITECTURE.md`
3. `ROUTING.md`
4. `COMPONENTS.md`
5. `STATE.md`
6. `DATABASE.md`
7. `SKILLS.md`

The goal is simple:

- keep Voodoo apps consistent
- make AI-generated code production-usable
- prevent generic patterns that fight the framework
- make Trae, Cursor, Windsurf, and other assistants converge on the same conventions

When in doubt:

- prefer simple Python functions over abstraction-heavy patterns
- prefer `voodoo.components` over raw HTML strings
- prefer `async def` for handlers and I/O
- prefer local project conventions over generic framework habits from React, Flask, or Django
