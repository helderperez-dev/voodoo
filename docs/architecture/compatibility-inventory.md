# Compatibility inventory

This is the maintained inventory for compatibility surfaces in the 3.x
Framework. It complements the [repository migration map](repository-migration.md)
with an explicit disposition and review date. New compatibility code must be
added here in the same change.

| Surface | Disposition | Owner | Review / removal condition |
| --- | --- | --- | --- |
| `voodoo.components` | Keep as a thin facade | `voodoo.ui` | Reconsider at the next major version after migration telemetry is available |
| `voodoo.core.state` and `voodoo.core.render` | Keep as import facades | `voodoo.ui` | Remove only in a declared major-version migration |
| `voodoo.telemetry` | Keep as compatibility aliases | `voodoo.observability` | Remove after a major version and documented import migration |
| `voodoo.mcp` | Keep as public compatibility imports | `voodoo.integrations.mcp` | Remove only with a major-version migration |
| `voodoo.mesh` | Keep application-facing transport surface | `voodoo.runtime.distributed` for authority | Split/remove only after a separately specified distributed profile |
| `voodoo.workers` | Keep application-facing compatibility surface | `voodoo.runtime.scheduling` | Remove after a major migration and scheduler API replacement |
| `voodoo.tools` | Keep import compatibility | `voodoo.ai.tools` | Remove after a major migration |
| `voodoo.agents` | Keep semantic participant registry | `voodoo.agents` | Not a compatibility shim; change requires architecture review |
| `voodoo.data.BaseModel` / SQL adapters | Keep explicit legacy adapter | `voodoo.data` and `voodoo.storage` | No new framework features; remove only after Store-first migration evidence |
| `voodoo.yaml` configuration | Keep parser compatibility | `voodoo.config` | Prefer `voodoo.toml`; remove only in a major version |
| package-root facades | Freeze existing documented imports | Owning canonical domain | No new exports without public API manifest review |

## Rules

- A compatibility surface delegates to one canonical owner and must not create
  a second lifecycle, execution, persistence, or observability authority.
- Compatibility adapters are explicit at call sites; they are not selected by
  hidden fallback when a native Store path is available.
- New code imports canonical owners. Compatibility imports are covered by a
  focused regression test and documented with their migration direction.
- Removal requires a deprecation entry, a migration note, a major-version
  decision, and a passing public API manifest update.

**Inventory baseline:** 2026-10-06. **Next review:** 2027-01-06 or before the
next major-version release, whichever comes first.
