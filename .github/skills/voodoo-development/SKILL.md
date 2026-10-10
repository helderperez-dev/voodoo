---
name: voodoo-development
description: Build applications with Voodoo using the intended Model, Runtime, Store, Events, Jobs, Objects, agents, UI, and execution patterns. Use for Voodoo application features, architecture decisions, data models, durable workflows, background work, events, object storage, and autonomous application behavior.
---

# Voodoo Development

Use Voodoo as an integrated application runtime, not as a collection of unrelated libraries.

## Core rules

1. Runtime owns semantics and authority.
2. Store owns durable mechanics.
3. AI is Compute, not a second Runtime.
4. Effect is not Observation.
5. Prefer local-first defaults.
6. One Runtime process owns one Store writer.
7. Prefer native Store primitives over KV emulation.
8. Python typing expresses data semantics.
9. `field()` expresses persistence metadata.
10. `relation()` expresses relationships and lifecycle policy.
11. Add infrastructure only when the application requires it.
12. UI state is session-scoped by default; opt into application scope explicitly.
13. WebSocket events and patches must be targeted to an authenticated UI session.
14. Treat generated projects from `voodoo new` as the canonical scaffold; keep aliases thin.

Before modeling data, read [model.md](references/model.md).
Before choosing persistence/messaging, read [store.md](references/store.md).
Before agents/effects/orchestration, read [runtime.md](references/runtime.md).
Review [anti-patterns.md](references/anti-patterns.md) before introducing new abstractions.

## Preferred Model style

```python
from voodoo import Model
from voodoo.data import field

class Customer(Model):
    email: str = field(unique=True)
    score: int = field(index=True)
    nickname: str | None
```

Semantics:

- Model technical identity defaults to UUIDv7.
- `T | None` expresses optionality.
- indexes are explicit opt-in.
- `field(unique=True)` implies a unique native index.
- simple defaults use normal Python assignment or `field(default=...)`.
- dynamic defaults use `field(default_factory=...)`.
- validation is separate from persistence metadata.
- backend-specific SQL types do not belong in normal Model declarations.

## Durable primitive selection

Use the native primitive that matches the job:

- Models / Collections: domain records.
- Jobs / Queue: durable background work.
- Topics / Streams: durable messaging and ordered flows.
- Objects: blobs and content-addressed object data.
- Outbox: durable publication intent.
- RPC: Store-native request/response mechanics.
- Workflow/HITL: workflow state, signals, timers, history and human checkpoints.
- CDC: committed change observation.

Do not implement a native Store domain as an ad-hoc KV encoding.

## UI and scaffold safety

Use `state(..., scope="application")` only for intentionally shared data. Never
put tenant, user, or browser-specific values in application-scoped state. Event
bindings created during rendering belong to the current browser session and
must not be reused across sessions.

For new applications, use `voodoo new --no-install` and inspect the generated
`app/` routes. The package-owned scaffold is the compatibility contract for the
CLI and external template repository; avoid introducing a second inline
template implementation.
