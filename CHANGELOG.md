# Changelog

## 1.4.0 — 2026-08-17

### Durable Task Queue (Sprint 2 — tasks survive restarts)

- **`VoodooQueue` protocol** (`voodoo.storage.queue`) — backend-neutral durable
  task queue: `enqueue`, `claim`, `heartbeat`, `complete`, `fail`, `release`,
  `release_expired`, `retry`, `list`, `stats` with declarative
  `QueueCapabilities` (durability, delivery semantics, visibility timeout,
  delayed delivery, priority, transactions).
- **`SQLiteQueue`** — the default durable provider: `tasks` table (migration
  0002) with atomic `UPDATE … RETURNING` claim (concurrent workers never claim
  the same task), lease-based visibility timeout, exponential backoff retries,
  priority ordering, delayed delivery, and `idempotency_key` deduplication for
  at-least-once semantics. Reclaims expired leases from dead workers.
- **`MemoryQueue`** — the ephemeral in-process provider, selected via
  `VOODOO_QUEUE_PROVIDER=memory`. Preserves the legacy `asyncio.Queue` behavior
  for non-critical work.
- **Workers reworked** — `workers/queue.py` now polls/claims from the durable
  queue instead of draining an `asyncio.Queue`; a background reaper reclaims
  expired leases. `@task`/`@queue`/`enqueue`/`start_workers`/`stop_workers`
  public API unchanged.
- **`voodoo.tasks` CLI** — `voodoo tasks list` (with stats), `voodoo tasks
  retry <id>`.
- **Queue contract test suite** (`tests/contracts/test_queue.py`) —
  `QueueContractTests` portability mixin (enqueue/claim/complete, fail/retry,
  release, idempotency, priority, delayed delivery, heartbeat, lease expiry,
  concurrent claims) run against both Memory and SQLite providers (43 tests).

## 1.3.0 — 2026-08-17

### Storage Core & Migrations (Sprint 1 — durable runtime foundation)

- **`VoodooDatabase` protocol** (`voodoo.storage.database`) — backend-neutral
  database capability: connection lifecycle, migration runner, transaction
  helper, query primitives, and declarative `DatabaseCapabilities`
  (transactions, migrations, native JSON, concurrent writers). The adapter
  boundary for the future PostgreSQL backend.
- **`SQLiteDatabase`** — the default embedded backend, now with WAL
  journaling on file-backed databases, `busy_timeout`, and an ordered
  idempotent migration runner tracked in a `schema_migrations` ledger.
  Migrations support static statements, async functions, and re-runnable
  idempotent steps; duplicate versions are rejected.
- **User-model DDL is now migration 0001** (`user_model_baseline`) —
  registered by `voodoo.data`, re-runs its `CREATE TABLE IF NOT EXISTS` DDL
  on every `init_db` so late-imported models keep working. Existing
  databases upgrade in place: the first run records the baseline without
  touching existing tables.
- **`voodoo.storage` is now a package** — `StorageManager` moved to
  `voodoo.storage.manager` with import-compatible re-exports
  (`from voodoo.storage import storage` unchanged).
- **Database contract test suite** (`tests/contracts/test_database.py`) —
  `DatabaseContractTests` portability mixin (ledger tracking, idempotent
  migrations, write/read roundtrip, transaction commit/rollback, reconnect
  durability, capability declaration). Every future adapter must pass it
  unchanged.

## 1.2.0 — 2026-08-17

### Unified Runtime Engine — every participant runs through one execution system

Voodoo now has a single `ExecutionEngine` that produces an `Execution` record (with `execution_id`, `trace_id`, `status`, `effects`, `state`, `cost`, `error`, `parent_execution_id`) for every meaningful operation. All nine participant types — HTTP, Agent, Tool, MCP, Worker, Task, Workflow, Human approval, Event handler — are now integrated.

### Human-in-the-Loop (HITL)

- **`ask_human()`** — humans as compute participants. Raises `ApprovalRequired`, execution enters `waiting` state.
- **`engine.approve(id)` / `engine.deny(id)`** — resume or fail a waiting execution as a child execution (shared trace, `parent_execution_id` link).
- **`Task(human=True, approval_capability=...)`** — human tasks inside workflows.
- **`voodoo inspect approvals`** — CLI command to list pending/decided approvals.
- **`voodoo recover`** — CLI command to reload unfinished executions from the persistence store after a restart.

### Durable Persistence & Recovery

- **`JSONFileExecutionStore`** — append-only JSONL store, corrupt-line tolerant.
- **`Engine.use_store(store)`** — attach a persistence backend.
- **Checkpointing** — executions persisted on terminal states + `waiting` (approval) + mid-workflow (per-task in sequential/parallel strategies).
- **`Engine.recover()`** — reloads unfinished executions (created/planned/authorized/running/waiting) and rebuilds pending approval records.

### Planner (Phase 12)

- **`Planner`** — deterministic capability → compute participant resolution. Registers agents, tools, workers, humans as `ComputeParticipant` with declared capabilities.
- **`Plan`** — strategy + per-capability step assignment with fallbacks and approval flags.
- **`voodoo inspect plan <intent> --requires cap1,cap2`** — debug surface showing the planner's decisions.

### Adaptive Runtime (Phase 13)

- **`AdaptiveSupervisor`** — supervisor loop with explicit decisions: `continue | retry | delegate | fallback | wait | request_approval | fail`.
- **Resource budget steering** — `SupervisorConfig.budget` accumulates per-step cost/tokens/latency and stops when exhausted.
- **Constraint → retry hook** — `ConstraintEnforcer.retry_hint(intent=...)` checks for `kind="retry"` constraints; the supervisor retries the same step instead of failing.
- **`WorkflowStrategy.ADAPTIVE`** — delegates to planner + supervisor.

### Integration: all participants through the engine

| Participant | Integration |
|---|---|
| HTTP request | `api._run_through_runtime` → `engine.execute` |
| Agent | capability-gated tool calls, effects lifted to Execution |
| Tool | `ToolSpec.permissions` enforced |
| MCP tool | `_run_tool_call` routes through engine (intent `mcp:<tool>`) |
| Worker | `_run_worker` executes via engine (intent `worker:<name>`) |
| Event handler | mesh handlers as child executions (intent `mesh:<event>`) |

### CLI

- `voodoo inspect plan <intent> --requires ...` — planner debug surface
- `voodoo inspect approvals [--pending] [--json]` — human approvals
- `voodoo recover [--store path] [--json]` — reload unfinished executions

### Tests

- **547 tests passing**, ruff clean.
- New test files: `test_human.py` (6), `test_persistence.py` (12), `test_http_runtime.py` (5), `test_mcp_runtime.py` (3), `test_planner_adaptive.py` (13), plus additions to `test_mesh.py` (2), `test_workers.py` (2), `test_cli_inspect.py` (6).

## 1.1.1 — 2026-08-17

### Default scaffold — Voodoo CSS + folder-based routing

- **`voodoo new` default template** now uses Voodoo CSS (the default adapter) and folder-based routing instead of Tailwind utility classes + `main.py`/`@page`.
- **Scaffold structure**: `app/page.py` → `/`, `app/about/page.py` → `/about`, `app/users/[id]/page.py` → `/users/{id}` (dynamic segment with `int` coercion).
- **Best practices showcased**: semantic component props (`variant`, `size`, `tone`, `level`), `Page`/`Stack`/`Flex`/`Card` layout, `(SEO, Component)` tuple returns, `A` + `voodoo.navigate()` for internal links.
- **Remote template repo** (`helderperez-dev/voodoo-templates`) `default/` variant updated to match.
- No `main.py`, `.env`, or infrastructure boilerplate — `voodoo dev` auto-discovers via `voodoo.core:app`.

### Bug fixes

- **`voodoo dev` module resolution**: Added `importlib.util.find_spec` check so importable packages (e.g. `voodoo.core`) are recognized even when not present as local files. Fixes `voodoo dev` in folder-routing projects with no `main.py`.
- **`find_spec` exception handling**: Wrapped `find_spec` in `try/except (ModuleNotFoundError, ValueError)` to prevent unhandled tracebacks when a dotted module's parent package is missing.

### Documentation

- Updated `docs/routing.md` and `docs/installation.md` to reflect folder-based routing as the scaffold default.
- Updated fallback AI rules (`scaffolding.py`) to describe Voodoo CSS as the default adapter and folder-based routing convention.

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
