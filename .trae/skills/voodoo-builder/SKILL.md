---
name: "voodoo-builder"
description: "Builds and refactors Voodoo apps. Invoke when creating routes, components, data flows, or debugging Voodoo-specific behavior."
---

# Voodoo Builder

Use this skill when working on a Voodoo Framework application.

Before major changes, read these local files if they exist:

1. `.voodoo/ai/README.md`
2. `.voodoo/ai/RULES.md`
3. `.voodoo/ai/ARCHITECTURE.md`
4. `.voodoo/ai/ROUTING.md`
5. `.voodoo/ai/COMPONENTS.md`
6. `.voodoo/ai/STATE.md`
7. `.voodoo/ai/DATABASE.md`
8. `.voodoo/ai/SKILLS.md`

## Core Voodoo Expectations

- build UI with `voodoo.components`
- prefer `async def`
- keep routing file-based in `app/`
- use `A` plus `voodoo.navigate()` for internal navigation
- keep persistent local data in `.data/`
- use `aiosqlite` by default unless the project clearly chose something else

## Development Guardrails

- preserve websocket large-cookie settings
- prefer simple Python functions over over-engineered abstractions
- make generated code feel native to Voodoo, not pasted from another framework
