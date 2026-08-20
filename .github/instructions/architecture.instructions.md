# Architecture Instructions

> **Read this before:** touching any module in `src/voodoo/`, adding new subsystems, or refactoring cross-layer boundaries.

---

## System Layers (top → bottom)

```
┌─────────────────────────────────────────────────────┐
│  UI Layer        — Components, Reactive State, WS    │
├─────────────────────────────────────────────────────┤
│  AI Layer        — Agent, LLM Providers, Tools       │
├─────────────────────────────────────────────────────┤
│  Realtime Layer  — Mesh, MCP                         │
├─────────────────────────────────────────────────────┤
│  Worker Layer    — @task, Async Queue                │
├─────────────────────────────────────────────────────┤
│  Runtime Engine  — ExecutionEngine, Planner,        │
│                    Adaptive, Human, Persistence      │
├─────────────────────────────────────────────────────┤
│  Computational   — Entity, State, Intent,           │
│  Model             Capability, Effect, Execution,   │
│                    Compute, Time, Resource,         │
│                    Constraint                        │
├─────────────────────────────────────────────────────┤
│  Data Layer      — Model/BaseModel, SQLite/PG        │
├─────────────────────────────────────────────────────┤
│  Infrastructure  — Auth, Security, Telemetry, Config │
└─────────────────────────────────────────────────────┘
```

**Rule:** Dependencies flow downward. A lower layer must never import from a higher layer. The runtime engine sits above primitives but below AI/UI — it orchestrates compute without knowing whether the compute is an LLM call or a pure function.

---

## The Computational Model (`voodoo.primitives`)

Every meaningful operation in Voodoo can be described with these concepts. When adding a new feature, identify which ones it touches — and whether the behavior is already expressible before introducing a new abstraction.

| Concept | Purpose | Key Type |
|---|---|---|
| **Entity** | Ontological identity — anything that holds state (conceptual; no code type) | — |
| **State** | Durable, versioned system truth | `State(kind, data, version)` |
| **Intent** | Outcome-oriented goal with lifecycle | `Intent(name, params)` |
| **Capability** | Explicit, revocable permission to produce an effect | `Capability(name, scope)` |
| **Effect** | Traceable side effect (reversible/irreversible) | `Effect(name, intent_id)` |
| **Execution** | The central runtime mechanism (produced by the runtime engine) | `Execution` |
| **Compute** | The act of computation (AI is one form) | `ComputeSpec` |
| **Time** | Deadlines, expiration, retry, scheduling | `TimeSpec` |
| **Resource** | Cost, latency, energy, tokens consumed | `Resource` |
| **Constraint** | What the system must/must not do | `Constraint` |

**Execution model:** `ENTITY → STATE → INTENT → CAPABILITY → EXECUTION → EFFECT → STATE`, with `TIME + CONSTRAINT` surrounding the lifecycle and `RESOURCE` determining execution mode.

---

## Module Boundaries

### `core/` — Application facade & cross-cutting
- `App` is the central runtime facade — wraps `create_app`, lazy Starlette build, `run()` dev server, `use()` plugin extension.
- `errors.py` defines the `VoodooError` hierarchy. All custom errors must subclass `VoodooError` and live here or in a domain-specific error module.
- Never put business logic in `core/` — it's the glue layer.

### `primitives/` — Foundational model
- These are pure data structures + lifecycle logic. No I/O, no side effects, no async.
- Never import from `runtime/`, `ai/`, `ui/`, or `storage/` here.

### `runtime/` — Unified execution engine
- `ExecutionEngine` is a singleton (`engine`) that walks `Intent → Capability → Execution → Effect → State → Mesh`.
- Every operation (HTTP, agent, tool, worker, MCP) produces an `Execution` record.
- `ExecutionContext` carries `trace_id`, `parent_execution_id`, `actor`, `capabilities`, `deadline`.
- Never bypass the engine for operations that should be durable/observable.

### `ai/` — Agent & LLM abstraction
- `Agent` is the user-facing API for AI. It delegates to `LLMProvider` implementations.
- Provider SDKs (`openai`, `anthropic`, etc.) are imported lazily at function level.
- `MockProvider` is the default for tests — deterministic, no network.
- Tools are registered via `@tool` decorator in `voodoo.ai.tools.registry`.

### `adapters/` — Provider registry & capabilities
- `ProviderRegistry` maps category+name → factory function.
- `*Capabilities` are frozen dataclasses with **boolean** flags (never enums).
- `require()` / `negotiate()` perform runtime capability checks.
- Style adapters (`VoodooCSSAdapter`, `TailwindAdapter`) live here too.

### `storage/` — Durable persistence adapters
- Each subdirectory implements a Protocol: `VoodooDatabase`, `VoodooQueue`, `VoodooEventBus`, `VoodooObjectStore`, `VoodooCache`.
- SQLite is the default for all categories. PostgreSQL/Redis/S3 are opt-in.
- Migrations are registered via `register_framework_migration()` at import time.

### `ui/` — Component system & reactive state
- `Component` is the base class. The library (`library.py`) has 50+ components.
- `State` cells are reactive — `StateRenderer` re-renders on mutation, patches DOM via WebSocket.
- `@event` decorator registers browser-side event handlers.
- Style adapters are swappable via `set_style_adapter()`.

### `routing/` — Page & API routing
- `PageRegistry` manages file-based routing (`app/<segment>/page.py`).
- `API` class handles REST endpoints, OpenAPI docs, and routes handlers through the ExecutionEngine.
- `call_page()` does dependency injection: request, user, path params with type coercion.

### `mesh/` — Realtime event bus
- `MeshNetwork` is the singleton. Events are namespaced (`"agent.started"`).
- `expose()` auto-bridges mesh events to MCP tools.
- Routes through the active `VoodooEventBus` implementation.

### `mcp/` — Model Context Protocol
- `MCPServer` exposes tools/resources over SSE.
- `tool()` decorator registers in both `MCPServer.tools` and `ToolRegistry`.
- Auto-bridges from `mesh.expose()`.

### `workers/` — Background tasks
- `@task` decorator wraps async functions with retries, timeout, backoff, telemetry.
- `.enqueue()` submits to the queue (memory, SQLite, Postgres, or Redis).
- Handler registry is populated at import time — see gotcha #5.

### `data/` — Async ORM
- `BaseModel` provides async `insert`/`update`/`_create_table`.
- `Model` is the CRUD facade (`create`/`get`/`all`/`save`/`delete`).
- `on_insert`/`on_update` hooks, `rls_policy` decorator for row-level security.
- PEP 562 `__getattr__` forwarding for live globals.

### `auth/` — Identity & access
- JWT tokens, API keys, PBKDF2 password hashing.
- `AuthMiddleware` extracts identity from `X-API-Key` > `Bearer` > cookie.
- Guards: `require_auth()`, `require_roles()`, `require_scopes()`, `require_api_key()`.

### `security/` — Security middleware
- `SecurityHeadersMiddleware`, `CORSMiddleware`, `CSRFMiddleware`, `RateLimitMiddleware`.
- These are Starlette middleware — order matters (see request lifecycle below).

### `telemetry/` — Observability
- `TelemetryStore` singleton, `trace` decorator, `trace_id_var` ContextVar.
- `TelemetryMiddleware` assigns UUID `trace_id` per request.
- Correlation IDs propagate through HTTP → agent → tool → queue → mesh.

### `cli/` — Typer CLI
- Commands: `new`, `dev`, `generate`, `auth`, `ai`, `inspect`, `tasks`, `schedules`, `executions`, `objects`, `doctor`, `routes`, `recover`, `version`.
- `voodoo doctor` prints the capability matrix (static, side-effect-free).
- `voodoo ai init` generates `.voodoo/ai/` context for IDE integration.

---

## Request Lifecycle

```
HTTP Request
  → SecurityHeadersMiddleware (headers)
  → CORSMiddleware (preflight, origins)
  → RateLimitMiddleware (throttle)
  → CSRFMiddleware (token validation)
  → TelemetryMiddleware (assign trace_id)
  → I18nMiddleware (locale detection)
  → AuthMiddleware (extract user)
  → Router (match path)
  → Page handler or API endpoint
  → Component tree render → HTML response
```

**Middleware order is defined in `voodoo.core.app.create_app()`.** Never reorder without understanding the security implications.

---

## Reactive Loop

```
Browser → WebSocket event
  → @event handler mutates State cell
  → StateRenderer re-renders affected components
  → DOM patch broadcast via WebSocket
  → Client swaps outerHTML
```

---

## Agent Execution Loop

```
prompt → provider → tool call?
  → execute tool (via ToolRegistry)
  → feed result back to provider
  → final answer
```

Every agent run produces an `AgentRun` dataclass with `run_id`, `model`, `provider`, `prompt`, `output`, `tokens_in`, `tokens_out`, `cost`, `tool_calls`, `timings`, `trace_id`.

---

## Compatibility Shims

When refactoring, **preserve old import paths**:

### `sys.modules` replacement
Used when a module is fully relocated:
```python
# voodoo/queue.py
import sys
from voodoo.workers.queue import *  # noqa: F401,F403

sys.modules[__name__] = sys.modules["voodoo.workers.queue"]
```

### PEP 562 `__getattr__`
Used for forwarding specific globals:
```python
# voodoo/__init__.py
def __getattr__(name: str) -> Any:
    if name == "SomeOldName":
        from voodoo.new_location import NewName

        return NewName
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Function-level imports
Used for provider SDKs and circular dependency avoidance:
```python
def get_provider(model: str) -> LLMProvider:
    import openai  # lazy import — only when needed

    ...
```

---

## When Adding a New Subsystem

1. **Identify the layer** — Where does it belong? (primitives, runtime, ai, ui, storage, etc.)
2. **Check dependencies** — Does it need to import from a higher layer? If so, reconsider.
3. **Define the Protocol** — If it's an adapter, define a Protocol in `storage/<category>/interfaces.py`.
4. **Add capabilities** — If it has varying feature support, add a `*Capabilities` dataclass.
5. **Register** — If it's a provider, register in `voodoo/adapters/registry.py`.
6. **Test** — Add tests following the contract test pattern.
7. **Export** — Add to `__all__` in the module and in `voodoo/__init__.py` if public API.
8. **Document** — Add a docstring and update relevant docs.

---

## What NOT to Build

- No custom programming language or JSX equivalent
- No React clone or CSS/JS framework
- No distributed database
- No Kubernetes integration
- No Celery replacement
- No autonomous coding agent
- No auto-deployments
- No self-modifying production code
- No autonomous financial transactions
- No vector DB abstraction
- No custom LLM training infrastructure

Voodoo is built on standards (Starlette, Pydantic, aiosqlite, asyncio) and interoperates with FastAPI, SQLAlchemy, httpx, pytest. Don't reinvent what these provide.
