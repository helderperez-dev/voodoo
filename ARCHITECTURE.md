# Architecture

> **Root-level architecture reference.** For the full guide, see `docs/architecture.md`. For AI agent guidance, see `.github/instructions/architecture.instructions.md`.

---

## What it is

Voodoo is a **programmable runtime for adaptive applications and operational
systems**. Web applications, APIs, agents, background workers, realtime
systems, MCP tools, data-driven applications, human workflows, and distributed
systems are different manifestations of the same runtime — they converge on one
execution model.

**Built on:** Starlette, Uvicorn, Pydantic, aiosqlite, and standard Python `asyncio`.

**Zero-config by default** (SQLite + local filesystem). **Production-ready by configuration** (PostgreSQL, Redis, S3, and optional model providers).

---

## The Convergence Model

Every subsystem flows through the same conceptual model. There is no independent execution model per subsystem.

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

An **Entity** with **State** pursues an **Intent**, which resolves to a
**Capability**, which is performed as an **Execution**. The execution is
governed by **Compute** (how), **Time** (when / how long), **Resource** (what
is consumed), and **Constraint** (what must hold). The execution produces an
**Effect**, which changes **State**.

---

## Design Principles

1. **Progressive complexity** — Start with the smallest executable application. Add capabilities when needed.
2. **One primary onboarding path** — `voodoo create` is the standard full-runtime scaffold; `voodoo new` is the intentionally minimal UI/routing scaffold.
3. **Lazy capabilities** — Database, storage, workers, and optional provider SDKs initialize only when actually used.
4. **AI as one Compute** — AI is not a separate subsystem; it is one class of Compute, never a fundamental primitive.
5. **Capability-based security** — Explicit, composable, revocable permissions rather than implicit access.
6. **Observability everywhere** — Correlation IDs + telemetry form the runtime's sensory system.
7. **Zero-config runtime** — `voodoo create` → `voodoo dev` → working local runtime.
8. **Meaningful executions only** — an `Execution` represents work worth observing, authorizing, recovering, accounting for, or reasoning about. Internal function calls, state reads, and implementation callbacks do not become executions merely because they occur inside Voodoo.
9. **Adaptive behavior stays optional** — planner/supervisor features may enrich execution without making simple application paths depend on adaptive orchestration.

---

## Computational concepts

| Concept | Purpose |
|---|---|
| **Entity** | Something with identity that participates in the system |
| **State** | Current operational truth of an entity or system |
| **Intent** | Desired outcome |
| **Capability** | Ability + authorization to produce an effect under conditions |
| **Execution** | Durable/observable unit of meaningful runtime work |
| **Effect** | Change produced by an execution |
| **Compute** | How execution is performed; AI is one form |
| **Time** | Deadline, timeout, schedule, retry and lifecycle |
| **Resource** | CPU, memory, tokens or other consumed resources |
| **Constraint** | Conditions that must hold |

Cross-cutting concepts are **Event**, **Identity**, **Telemetry**, and **Relationship**.

### Choosing the right abstraction

| Need | Use |
|---|---|
| UI-local mutable value | reactive `state()` |
| Persistent business data | `Model` |
| Long-term contextual recall | agent/runtime memory |
| Browser interaction | `@event` |
| Decoupled application notification | Mesh/event bus |
| Retryable background work | `@task` |
| Meaningful durable/observable operation | `Execution` |
| LLM reasoning/tool loop | `Agent` |
| Reusable callable action | `@tool` |
| Authorization to produce an effect | `Capability` |
| Human decision in an execution | HITL approval |
| Work at a future time | Scheduler |

The table is deliberately semantic: similar-looking primitives are not aliases. UI state is not business persistence; a tool is not a capability; an event is not automatically an execution.

---

## Layering rules

- **UI** does not import storage/runtime internals.
- **AI** does not import UI/routing.
- **Runtime** does not import provider SDKs directly.
- **Primitives** have zero dependencies on other Voodoo layers.
- **Data** does not import AI or Mesh.
- Optional infrastructure/provider SDKs stay behind lazy adapters and optional extras.

---

## Request lifecycle

1. HTTP request enters the ASGI app.
2. Middleware applies security, telemetry, i18n and auth concerns.
3. Telemetry assigns a correlation/trace identifier.
4. Auth resolves the caller when configured.
5. Routing dispatches to a page or API handler.
6. Runtime integration creates an `Execution` only when the configured boundary treats the operation as meaningful runtime work.
7. The response flows back through middleware.

## Reactive loop

1. Browser sends an event over WebSocket.
2. Event handler mutates a reactive state cell.
3. `StateRenderer` re-renders the bound component/page.
4. A DOM patch is broadcast.
5. The browser applies the patch.

Reactive reads/renders are not themselves durable executions.

## Agent execution loop

```text
prompt → provider → native tool call? → execute tool → tool result → provider → final answer
```

1. Agent builds messages from prompt, system prompt, history and context.
2. Provider returns normalized `ProviderResponse` / streaming `ProviderEvent` values.
3. Native provider tool calls are normalized into `ToolCall` objects and invoked through the tool registry.
4. Tool results are appended using the provider-compatible call/result identifiers and the loop continues.
5. When no tool calls remain, the final response is returned.
6. The legacy `[TOOL: ...]` text marker exists only as a compatibility/mock fallback; it is not the canonical provider protocol.

Provider SDKs are optional and lazily imported. A core installation can use the mock/runtime surfaces without installing third-party AI SDKs.

---

## Runtime Engine

`ExecutionEngine` is the unified runtime mechanism. A meaningful operation can produce an `Execution` with:

- `execution_id`, `trace_id`, `parent_execution_id`
- lifecycle status (`created`, `planned`, `authorized`, `running`, `waiting`, terminal states)
- effects and observable state changes
- resource/cost/duration accounting
- structured errors and recovery context

### Execution boundary rule

Create an `Execution` when at least one of these matters:

- durability or crash recovery;
- authorization/capability enforcement;
- parent/child delegation and traceability;
- effect/state-change recording;
- resource/cost accounting;
- retries, timeout, scheduling or human waiting;
- operational observability at a user/business boundary.

Do **not** create one for every helper call, state access, render pass, callback, or internal event. This keeps the execution graph useful rather than noisy.

### Human-in-the-loop

Human approval is a waiting state of the same execution model. Approval state is persisted so recoverable work can resume after a process restart.

---

## Provider / adapter system

Infrastructure implementations sit behind protocols so local defaults and production adapters share contracts.

| Protocol | Typical implementations |
|---|---|
| `VoodooDatabase` | SQLite, PostgreSQL |
| `VoodooQueue` | local/SQLite, PostgreSQL, Redis |
| `VoodooEventBus` | local/SQLite, PostgreSQL |
| `VoodooObjectStore` | local filesystem, S3-compatible |
| `VoodooCache` | in-memory, Redis |

Model providers are resolved lazily from `provider:model` references. Third-party SDKs belong to the `ai` optional extra; the base runtime does not require them.

---

## Module responsibilities

```text
src/voodoo/
├── core/        # application facade, routing-facing core, errors/events/state
├── primitives/  # ontology and execution dimensions
├── runtime/     # execution engine, planner/adaptive, human, persistence
├── ai/          # agents, provider abstraction, tools
├── adapters/    # adapter/capability integration
├── storage/     # database, queue, events, execution, objects, cache adapters
├── ui/          # components, reactive state, styles/themes
├── routing/     # page/API routing
├── mesh/        # realtime application communication
├── mcp/         # MCP integration
├── workers/     # background task runtime
├── data/        # async ORM
├── auth/        # identity/authentication/guards
├── security/    # HTTP/application security middleware
├── telemetry/   # traces, metrics and observability
├── cli/         # create/new/dev/generate/inspect/recover/etc.
├── config.py    # configuration and environment interpolation
├── schedule.py  # durable scheduling
└── status.py    # health/status endpoint
```

---

## Further reading

The detailed guides under `docs/` are authoritative for individual subsystems. In particular see `docs/primitives.md`, `docs/execution-model.md`, `docs/runtime.md`, `docs/agents.md`, `docs/events.md`, `docs/mesh.md`, `docs/workers.md`, `docs/data.md`, `docs/hitl.md`, and `docs/telemetry.md`.
