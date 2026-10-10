# Canonical package navigation

This page is the contributor-facing map for Voodoo 3.x. It answers two
questions before a new module is added: which semantic owner should contain it,
and which public import should applications use?

## Public entry points

| Need | Canonical import | Owner |
| --- | --- | --- |
| Application lifecycle and state | `voodoo.App`, `voodoo.state` | `voodoo.core` |
| Durable application data | `voodoo.Model` / `voodoo.data` | `voodoo.data` + RuntimeStore |
| Canonical execution | `voodoo.runtime.Execution*` | `voodoo.runtime.execution` |
| Jobs and scheduling | `voodoo.task`, `voodoo.runtime.scheduling` | Runtime scheduling |
| Events and outbox | `voodoo.events`, `voodoo.runtime.transaction` | Runtime/events |
| UI and design system | `voodoo.ui.*` | `voodoo.ui` |
| Authentication and identity | `voodoo.auth`, `voodoo.runtime.identity` | Auth/Runtime identity |
| Devices and edge state | `voodoo.edge.*` | `voodoo.edge` |
| AI providers and tools | `voodoo.ai.*` | `voodoo.ai` |
| External infrastructure | `voodoo.storage.*`, `voodoo.adapters.*` | Storage/adapters |
| Developer commands | `voodoo.cli` and `voodoo new` | CLI |

## Ownership rules

1. Use the narrowest existing semantic owner; do not add a package-root module
   for convenience.
2. Runtime owns authority, execution semantics, identity projection and
   lifecycle. Store owns durable mechanics and recovery.
3. `voodoo.data` is the application persistence facade; application code must
   not depend on native `voodoo_store` types.
4. Provider SDKs belong behind `voodoo.integrations` or an explicit storage
   adapter and must remain optional from the semantic core.
5. Compatibility facades are temporary, documented and covered by the public
   API compatibility registry. They are not new semantic owners.

## Choosing a location

When a feature crosses domains, place its contract at the semantic boundary
that owns the decision and keep provider-specific work in the adapter layer.
For example, a durable workflow belongs under `voodoo.runtime.workflow` while
its native persistence adapter belongs under Store-backed runtime storage; a
button belongs under `voodoo.ui`, not under a product or application module.

See [repository architecture](repository.md), [architecture governance](governance.md),
and the [public API law](../public-api-3.md) for the rules enforced by CI.
