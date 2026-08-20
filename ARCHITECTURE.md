# Architecture

> **Root-level architecture reference.** For the full guide, see `docs/architecture.md`. For AI agent guidance, see `.github/instructions/architecture.instructions.md`.

---

## What it is

Voodoo is a **programmable runtime for adaptive applications and operational
systems**. Web applications, APIs, agents, background workers, realtime
systems, MCP tools, data-driven applications, human workflows, distributed
systems, and physical systems are different manifestations of the same runtime
— they converge on one execution model.

**Built on:** Starlette, Uvicorn, Pydantic, aiosqlite, and standard Python `asyncio`.

**Zero-config by default** (SQLite + local filesystem). **Production-ready by configuration** (PostgreSQL, Redis, S3, OpenAI/Anthropic).

---

## The Convergence Model

Every subsystem — UI, API, Agent, Worker, Tool, MCP, Human, Device, Robot —
flows through the same conceptual model. There is no independent execution
model per subsystem.

```text
                    ENTITY
                       │
                       ▼
                     STATE
                       │
                       ▼
                    INTENT
                       │
                       ▼
                 CAPABILITY
                       │
                       ▼
                  EXECUTION
                       │
          ┌────────────┼────────────┐
          │            │            │
       COMPUTE       TIME      CONSTRAINT
          │            │            │
          └────────────┼────────────┘
                       │
                    EFFECT
                       │
                       ▼
                     STATE
```

An **Entity** with **State** pursues an **Intent**, which resolves to a
**Capability**, which is performed as an **Execution**. The execution is
governed by **Compute** (how), **Time** (when / how long), **Resource** (what
is consumed), and **Constraint** (what must hold). The execution produces an
**Effect**, which changes **State**.

---

## Design Principles

1. **Progressive complexity** — Start with the smallest executable application. Add capabilities when needed.
2. **Minimal scaffold** — `voodoo new` produces only `app/page.py`. No empty directories, no placeholder files.
3. **Lazy capabilities** — Database, storage, and workers initialize only when actually used.
4. **AI as one Compute** — AI is not a separate subsystem; it is one class of Compute, never a fundamental primitive.
5. **Capability-based security** — Explicit, composable, revocable permissions rather than implicit role-based access.
6. **Observability everywhere** — Correlation IDs + telemetry as the sensory system.
7. **Zero-config runtime** — `voodoo new` → `voodoo dev` → working app.

---

## The Computational Model

Voodoo's concepts live at different semantic levels (see
[`docs/primitives.md`](docs/primitives.md)):

### Core Ontology

| Concept | Purpose |
|---|---|
| **Entity** | Something with identity that participates in the system |
| **State** | Current operational truth of an entity or system |
| **Intent** | The desired outcome to achieve |
| **Capability** | Ability + authorization to produce an effect under conditions |
| **Effect** | A change produced by an execution |

### Runtime

| Concept | Purpose |
|---|---|
| **Execution** | The central runtime mechanism — every operation is one |

### Execution Dimensions

| Concept | Purpose |
|---|---|
| **Compute** | How the execution is performed (AI is one class) |
| **Time** | Lifecycle and validity (deadline, timeout, schedule, retry) |
| **Resource** | What is consumed (CPU, GPU, memory, tokens, energy) |
| **Constraint** | Conditions that must hold |

### Cross-Cutting Concepts

**Event**, **Identity**, **Telemetry**, **Relationship**.

### Execution Model

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

```python
from voodoo.primitives import State, Capability, Intent, Effect
from voodoo.primitives import TimeSpec, ComputeSpec, Resource, Constraint
```

---

## System Layers

```
┌─────────────────────────────────────────────┐
│              Primitives Layer                 │
│  Entity, State, Intent, Capability, Effect   │
│  Compute, Time, Resource, Constraint          │
├─────────────────────────────────────────────┤
│              Runtime Engine Layer             │
│  ExecutionEngine (execute, delegate, recover) │
│  ExecutionContext (trace, capabilities, ...)  │
│  Execution (status, effects, cost, state)    │
│  CapabilityResolver (allow/deny/approve)     │
│  ConstraintEnforcer + ResourceAccountant     │
│  Planner (capability → compute resolution)  │
│  AdaptiveSupervisor (retry/fallback/budget)  │
│  Human (ask_human, approve, deny)           │
│  Persistence (SQLiteExecutionStore)         │
├─────────────────────────────────────────────┤
│                  UI Layer                     │
│  Components (Div, Card, Button, ...)         │
│  Reactive State (State, StateRenderer)       │
│  WebSocket Transport (ws_manager, events)    │
├─────────────────────────────────────────────┤
│                  AI Layer                      │
│  Agent (run, stream, tool calling)           │
│  LLM Providers (OpenAI, Anthropic, Mock)     │
│  Tool Registry (@tool, ToolSpec)             │
├─────────────────────────────────────────────┤
│               Realtime Layer                   │
│  Voodoo Mesh (events, expose, WS nodes)      │
│  MCP Server (SSE, tools/list, tools/call)    │
├─────────────────────────────────────────────┤
│               Worker Layer                    │
│  @task (retries, timeout, telemetry)         │
│  Async Queue (enqueue, start_workers)        │
├─────────────────────────────────────────────┤
│                Data Layer                      │
│  Model / BaseModel (async CRUD)              │
│  SQLite (aiosqlite) with RLS policies        │
├─────────────────────────────────────────────┤
│              Infrastructure                    │
│  Auth (JWT, API keys, RBAC)                  │
│  Security (CORS, CSRF, rate limit, headers)  │
│  Telemetry (trace_id, metrics, spans)       │
│  Config (voodoo.toml, env vars)              │
└─────────────────────────────────────────────┘
```

### Layering Rules

- **UI layer** doesn't import from `storage/` or `runtime/` internals.
- **AI layer** doesn't import from `ui/` or `routing/`.
- **Runtime layer** doesn't import provider SDKs directly.
- **Primitives layer** has zero dependencies on other layers.
- **Data layer** doesn't import from `ai/` or `mesh/`.

---

## Request Lifecycle

1. HTTP request enters the ASGI app.
2. Middleware stack processes: SecurityHeaders → CORS → RateLimit → CSRF → Telemetry → I18n → Auth.
3. TelemetryMiddleware assigns a `trace_id` (UUID).
4. AuthMiddleware resolves user from token/API key/cookie.
5. Routing dispatches to page handler or API endpoint.
6. Handler runs, renders component tree to HTML.
7. Response flows back through middleware.

## Reactive Loop

1. Browser sends event over WebSocket (`{"type": "event", "event": "increment", ...}`).
2. Event handler mutates `State` cell.
3. `StateRenderer` re-renders the page function.
4. DOM patch broadcast to all WebSocket clients.
5. Client swaps `outerHTML` of the target element.

## Agent Execution Loop

```
prompt → provider → tool call? → execute tool → feed result back → final answer
```

1. Agent builds messages from prompt + system_prompt + context.
2. Provider (OpenAI/Anthropic/Mock) processes the messages.
3. If the response contains a tool-call marker, the tool is invoked from the registry.
4. The tool result is appended to messages and the loop continues.
5. When no more tool calls are requested, the final answer is returned.

---

## Correlation ID Propagation

Every request gets a `trace_id` (UUID) via `ContextVar`. This ID propagates through:

- HTTP request telemetry
- Agent runs (recorded in `AgentRun.trace_id`)
- Tool call telemetry
- Queue items (stored in envelope, restored in worker)
- Mesh event envelopes (`correlation_id` field)

---

## Runtime Engine

The `ExecutionEngine` is the unified execution model. Every meaningful operation — HTTP request, agent run, tool call, MCP dispatch, worker job, task, workflow step, human approval, event handler — produces an `Execution` record with:

- `execution_id` / `trace_id` / `parent_execution_id` — full traceability
- `status` — `created → planned → authorized → running → waiting → completed | failed | cancelled | timed_out`
- `effects` — side effects recorded on the execution
- `state_changes` — observable state transitions
- `cost` / `duration_seconds` — resource accounting
- `error` — structured error with execution context

### Execution Lifecycle

```
created → planned → authorized → running → waiting → completed
                    ↓              ↓         ↓
                  failed        timed_out  cancelled
```

### Intent → Capability → Execution → Effect → State

```python
from voodoo.runtime import Intent, execute, Task, Workflow

result = await execute(
    Intent(name="qualify_customer", params={"customer_id": 123}),
    compute=some_fn,
)
```

### Human-in-the-Loop

```python
from voodoo.runtime import ask_human, ExecutionEngine

engine = ExecutionEngine()

# Raises ApprovalRequired — execution enters "waiting"
# Approval persisted to execution_approvals table
# voodoo recover restores pending approvals after crash
```

---

## Provider/Adapter System

Every infrastructure adapter implements a Protocol and declares boolean capability flags:

| Protocol | Implementations |
|---|---|
| `VoodooDatabase` | SQLite (default), PostgreSQL |
| `VoodooQueue` | In-memory (default), PostgreSQL, Redis |
| `VoodooEventBus` | In-memory (default), PostgreSQL |
| `VoodooObjectStore` | Local filesystem (default), S3/MinIO |
| `VoodooCache` | In-memory (default), Redis |

### LLM Providers

| Provider | Model format |
|---|---|
| Mock | `mock:default` |
| OpenAI | `openai:gpt-4o` |
| Anthropic | `anthropic:claude-3-5-sonnet` |
| Gemini | `gemini:gemini-1.5-pro` |
| Ollama | `ollama:llama3` |

---

## Module Map

```
src/voodoo/
├── __init__.py          # Public API, __version__, deprecation shims
├── core/               # App facade, routing, errors, events, state
├── primitives/         # Core ontology + execution dimensions
├── runtime/            # ExecutionEngine, context, planner, adaptive, human, persistence
├── ai/                 # Agent, LLM providers, tool registry
├── adapters/           # Provider registry, capability system, style adapters
├── storage/            # Database, queue, events, execution, objects, cache adapters
├── ui/                 # Component system, reactive state, styles, theme
├── routing/            # Page registry, API routing
├── mesh/               # Realtime event bus
├── mcp/                # Model Context Protocol server/client
├── workers/            # @task decorator, queue runtime
├── data/               # Async ORM (BaseModel, Model)
├── auth/               # JWT, passwords, users, guards, middleware
├── security/           # CORS, CSRF, rate limit, security headers
├── telemetry/          # Trace store, middleware, metrics
├── cli/                # Typer CLI (new, dev, generate, inspect, recover, ...)
├── config.py           # Config loading, env interpolation
├── i18n.py             # Internationalization
├── schedule.py         # Durable scheduler
├── seo.py              # SEO/OpenGraph metadata
└── status.py           # Health check endpoint
```

---

## Further Reading

| Topic | Document |
|---|---|
| Full architecture guide | `docs/architecture.md` |
| AI agent guidance | `.github/instructions/architecture.instructions.md` |
| Runtime engine | `docs/runtime.md`, `.github/instructions/runtime.instructions.md` |
| Provider system | `.github/instructions/providers.instructions.md` |
| Durable persistence | `.github/instructions/execution.instructions.md` |
| AI agents & tools | `docs/agents.md`, `.github/instructions/ai.instructions.md` |
| Testing & contracts | `.github/instructions/testing.instructions.md` |
| Primitives | `docs/primitives.md` |
| Components | `docs/components.md` |
| Mesh | `docs/mesh.md` |
| MCP | `docs/mcp.md` |
| Workers | `docs/workers.md` |
| Data ORM | `docs/data.md` |
| Auth | `docs/auth.md` |
| Telemetry | `docs/telemetry.md` |
