# Changelog

## 1.1.0 — 2026-08-16

### Scaffold revision — progressive complexity

- **Minimal scaffold**: `voodoo new` now produces only `app/page.py`, `voodoo.toml`, `pyproject.toml`. No `main.py`, `.env`, placeholder directories, or infrastructure files.
- **`voodoo ai init`**: New CLI command for opt-in AI development context. Replaces automatic AI asset generation during `voodoo new`. Supports `--ide` flag (trae, cursor, windsurf, vscode, all).
- **`voodoo dev` auto-discovery**: When no `main.py` exists, `voodoo dev` uses `voodoo.core:app` (lazy ASGI app). `main:app` still supported for backward compatibility.

### Lazy runtime

- **Lazy database**: SQLite initializes on first `get_db()` call, not at startup. Default path changed from `.data/voodoo.db` to `.voodoo/state/data.db`.
- **Lazy storage**: No storage directories created unless storage is used. Conditional `/storage` mount only if directory exists.
- **Lazy workers**: Worker subsystem starts only if workers are registered.
- **Conditional `public/` mount**: Static assets mounted only if `public/` directory exists.

### Configuration

- **`voodoo.toml`**: Added TOML config support (preferred for new projects). YAML compatibility preserved. Precedence: `voodoo.toml` > `voodoo.yaml` > env vars > defaults.

### Architectural primitives

- **`voodoo.primitives` package**: Eight fundamental computational primitives — State, Capability, Intent, Effect, TimeSpec, ComputeSpec, Resource, Constraint.
- **Execution model**: STATE → INTENT → CAPABILITY → COMPUTE → EFFECT → STATE, with TIME + CONSTRAINTS surrounding the lifecycle and RESOURCE determining execution.
- **AI as Compute**: AI is one class of Compute, not a separate subsystem. `ComputeSpec.reasoning(provider="openai", model="gpt-4o")`.
- **Capability-based security**: Explicit, composable, revocable, delegatable permissions. `Capability.timed("payment.execute", expires_in=600)`.
- **59 new tests** for all primitives and their composition.

### CLI

- `voodoo new` — minimal scaffold (no `--ide` flag, no AI sync)
- `voodoo ai init [--ide <ide>]` — opt-in AI context
- `voodoo dev` — auto-discovers app
- `voodoo routes` — auto-discovers app
- `voodoo doctor` — updated AI kit hint to `voodoo ai init`

### Backward compatibility

- Existing projects with `main.py`, `app/pages/`, `.data/`, `storage/`, `voodoo.yaml` continue to work.
- `create_app()` and `App` preserved.
- All existing features (agents, MCP, mesh, workers, auth, security, SEO, telemetry, components, state, CLI generation) preserved.

---

## 1.0.0 — 2026-08-15

First stable release of Voodoo — the AI-native application framework for Python.

### Core Runtime
- `App` central facade wrapping the ASGI/Starlette machinery with `app.run()` dev server
- `@page(path)` decorator for SSR routes with path params and type coercion
- `api` namespace (`api.get/post/put/delete/patch`) for JSON endpoints
- Error hierarchy: `VoodooError` tree covering all subsystems
- Env-driven configuration (`VOODOO_ENV`, `VOODOO_DEBUG`, `DATABASE_URL`, provider keys)

### Reactive State & Events
- `state()` reactive primitive: `get()`, `set()`, `update()`, `subscribe()`
- `@event` decorator: auto-registers async handlers for browser events
- `StateRenderer`: re-renders page functions and broadcasts DOM patches over WebSocket
- `client.js`: minimal browser runtime with exponential backoff reconnection
- Zero-JS developer experience: state changes trigger live UI updates

### UI Component System
- Single `Component` base: child flattening, attribute pipeline, HTML escaping
- Semantic props: `variant`, `size`, `tone` on components
- Accessibility defaults baked in (roles, aria, semantic HTML)
- `StyleAdapter` boundary: Tailwind isolated in `adapters/tailwind`
- `Theme` semantic tokens translated to CSS variables / Tailwind config
- VoodooCSS adapter: framework CSS with `--vd-*` tokens
- Custom CSS via `styles.css` convention and `class_` escape hatch

### Data & Workers
- `Model` CRUD facade: `create()`, `get()`, `all()`, `save()`, `delete()`
- Built on Pydantic + aiosqlite with `on_insert`/`on_update` hooks
- Storage backend boundary designed for future PostgreSQL adapter
- `@task` worker decorator: retries with backoff, timeout, telemetry spans
- Queue integration with Mesh events (`@mesh.on` → `@task` chain)
- Single-process scope; distributed backend boundary named

### Auth & Security
- JWT auth with proper expiry, `nbf` validation, constant-time comparison
- Session cookies: `HttpOnly`, `SameSite=lax`, `Secure` in production
- CSRF double-submit cookie with M2M exemption
- CORS with `Vary: Origin` and disallowed-origin suppression
- Rate limiting with client isolation
- Security headers: CSP, HSTS, X-Frame-Options, Permissions-Policy
- PBKDF2-HMAC-SHA256 password hashing (600K iterations, OWASP standard)
- Route guards: `login_required`, `requires_role`, `requires_permission`
- Production error handling: no stack/secret/path leakage

### Tools & Providers
- `@tool` decorator → `ToolSpec` with schemas from typing, permissions, source metadata
- `ToolRegistry`: single source of truth for all tools
- One tool definition serves: Python calls, Agent runs, MCP consumers, Mesh exposure
- `LLMProvider` interface: `complete()`, `stream()`, token/cost accounting
- Providers: OpenAI, Anthropic, Gemini, Ollama (optional extras, lazy imports)
- `MockProvider` for deterministic CI testing (no network)
- `model="provider:model"` resolution

### Agent
- `Agent(model=..., tools=[...])` with execution loop: prompt → model → tool calls → final
- `run()` returns `AgentRun` record: run_id, model, provider, timings, tokens, cost, tool calls, status
- `stream()` yields normalized events: `text | tool_started | tool_finished | thinking | error | completed`
- Lifecycle states: created → configured → running → (tool_call ⇄ thinking) → completed | error
- Explicit `context={...}` parameter (context ≠ memory ≠ database)
- Agent lifecycle publishes namespaced Mesh events

### Mesh
- `mesh.emit()` / `mesh.on()` / `mesh.expose()` — three verbs
- Event envelope: id, timestamp, source, correlation_id
- Namespaced event names enforced (`agent.started`, not `started`)
- `expose` = explicit remote capability with permission awareness
- Local event ≠ remote event boundary documented

### MCP
- MCP layer consumes `ToolRegistry` (no separate `@mcp_tool`)
- Schema generation from `ToolSpec` type hints
- SSE endpoint with JSON-RPC protocol
- `MCPClient` for external tool consumption

### Telemetry
- `trace` decorator with span recording
- Correlation IDs via `ContextVar` propagated: request → mesh → worker → agent → tool → db
- AI telemetry: per-run records with model, provider, latency, tokens, cost, tool calls
- Tool call telemetry with error tracking
- Unified summary API for DevTools/doctor consumption

### CLI
- `voodoo new my_app` — scaffolding with file-based pages structure
- `voodoo dev` — dev server with startup banner
- `voodoo routes` — list registered routes
- `voodoo doctor` — health checks across all subsystems
- `voodoo version` — print version
- File-based pages: `pages/index.py`, `pages/about.py`, `pages/users/[id].py`

### Quality
- 381 tests: contract, unit, integration, security, performance
- Public API pinned by contract test (semver 1.0)
- Ruff lint clean, mypy configured
- Deterministic mock LLM provider for CI (no network)
- 16 documentation pages following the page formula
- 5 example apps including the AI SaaS killer demo
- Clean install: `uv tool install voodoo-framework` → `voodoo new` → `voodoo dev`

### Packaging
- Optional extras: `voodoo[ai]`, `voodoo[mcp]`, `voodoo[dev]`
- Core install stays lean (providers lazy-imported)
- Package data includes `client.js`

---

## 1.0.22 — Pre-release baseline

Initial baseline audit and working repository state before the 1.0 implementation plan.
