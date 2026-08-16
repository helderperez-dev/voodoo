# Voodoo Sprints — Master Index

> All sprint tracking documents. Each file contains the goal, workstreams,
> file changes, and exit criteria for that sprint.
>
> **Rule**: commit per sprint, no version bump until S9 (release).

---

## Completed

| Sprint | Focus | Commit | Status |
|---|---|---|---|
| S0 | Baseline audit & benchmarks | `0e7f821` | Done |
| S1 | Core runtime (App, @page, errors, config) | `2790682` | Done |
| S2 | UI Component System (StyleAdapter, library, theme) | `bb92e3a` | Done |
| DS | Design System (VoodooCSS, --vd-* tokens, Stack/Box/Link) | `6c393db` | Done |
| S3 | Reactive State & Events | — | Done |
| S4 | Data & Workers | — | Done |
| S5 | Auth Hardening & CLI | — | Done |
| S6 | Tools & Providers | — | Done |
| S7 | Agent, Mesh & MCP | — | Done |
| S8 | Quality & Docs | — | Done |
| S9 | Freeze & Release (1.0.0) | — | Done |

---

## Sprint Flow

```
S0 (Baseline) ──> S1 (Core) ──> S2 (UI) ──> DS (Design System)
                                              │
                                              v
                                    S3 (State & Events)
                                              │
                              ┌───────────────┴───────────────┐
                              v                               v
                    S4 (Data & Workers)              S6 (Tools & Providers)
                              │                               │
                              v                               v
                    S5 (Auth & CLI)                  S7 (Agent & Mesh)
                              │                               │
                              └───────────┬───────────────────┘
                                          v
                                S8 (Quality & Docs)
                                          │
                                          v
                                  S9 (Freeze & Release)
```

S4+S5 and S6+S7 can partially parallelize once S3 exits.
