# Architecture

## What it is

Voodoo is an AI-native application framework for Python. It combines reactive UIs, APIs, agents, background workers, realtime systems, MCP tools, and data-driven applications in one Python runtime.

## Design principles

1. **Progressive complexity** — Start with the smallest executable application. Add capabilities when needed. Voodoo manages implementation details.
2. **Minimal scaffold** — `voodoo new` produces only `app/page.py`. No empty directories, no placeholder files, no infrastructure boilerplate.
3. **Lazy capabilities** — Database, storage, and workers initialize only when actually used. A project that doesn't use persistence doesn't create a database.
4. **AI as Compute** — AI is not a separate subsystem. It is one class of Compute within the architectural primitives model.
5. **Capability-based security** — Explicit, composable, revocable permissions rather than implicit role-based access.
6. **Observability everywhere** — Correlation IDs + telemetry as the sensory system.
7. **Zero-config runtime** — `voodoo new` → `voodoo dev` → working app.

## Architectural primitives

Voodoo is built on eight fundamental computational primitives that remain valid regardless of how computation evolves:

    State       — durable system truth
    Capability  — explicit permission to act
    Intent      — what the system is trying to accomplish
    Effect      — a change caused outside pure computation
    Time        — first-class temporal concept
    Compute     — the act of performing computation
    Resource    — something consumed or depended upon
    Constraint  — what the system must or must not do

They form a coherent execution model:

    STATE → INTENT → CAPABILITY → COMPUTE → EFFECT → STATE
    TIME + CONSTRAINTS surround the entire lifecycle.
    RESOURCE determines how execution should be performed.

```python
from voodoo.primitives import State, Capability, Intent, Effect
from voodoo.primitives import TimeSpec, ComputeSpec, Resource, Constraint
```

The sophistication is in the model, not in the API surface. Voodoo should feel almost boring at first — that is intentional.

## System layers

```
┌─────────────────────────────────────────────┐
│              Primitives Layer                 │
│  State, Capability, Intent, Effect, Time,    │
│  Compute, Resource, Constraint               │
├─────────────────────────────────────────────┤
│              Runtime Engine Layer             │
│  ExecutionEngine (execute, delegate, recover) │
│  ExecutionContext (trace, capabilities, ...)  │
│  Execution (status, effects, cost, state)    │
│  CapabilityResolver (allow/deny/approve)     │
│  ConstraintEnforcer + ResourceAccountant     │
│  Planner (capability → compute resolution)   │
│  AdaptiveSupervisor (retry/fallback/budget)  │
│  Human (ask_human, approve, deny)            │
│  Persistence (JSONFileExecutionStore)        │
├─────────────────────────────────────────────┤
│                  UI Layer                     │
│  Components (Div, Card, Button, ...)          │
│  Reactive State (State, StateRenderer)        │
│  WebSocket Transport (ws_manager, events)     │
├─────────────────────────────────────────────┤
│                  AI Layer                      │
│  Agent (run, stream, tool calling)            │
│  LLM Providers (OpenAI, Anthropic, Mock)      │
│  Tool Registry (@tool, ToolSpec)              │
├─────────────────────────────────────────────┤
│               Realtime Layer                   │
│  Voodoo Mesh (events, expose, WS nodes)       │
│  MCP Server (SSE, tools/list, tools/call)     │
├─────────────────────────────────────────────┤
│               Worker Layer                    │
│  @task (retries, timeout, telemetry)          │
│  Async Queue (enqueue, start_workers)         │
├─────────────────────────────────────────────┤
│                Data Layer                      │
│  Model / BaseModel (async CRUD)               │
│  SQLite (aiosqlite) with RLS policies         │
├─────────────────────────────────────────────┤
│              Infrastructure                    │
│  Auth (JWT, API keys, RBAC)                   │
│  Security (CORS, CSRF, rate limit, headers)   │
│  Telemetry (trace_id, metrics, spans)          │
│  Config (voodoo.toml, env vars)               │
└─────────────────────────────────────────────┘
```

## Request lifecycle

1. HTTP request enters the ASGI app
2. Middleware stack processes: SecurityHeaders → CORS → RateLimit → CSRF → Telemetry → I18n → Auth
3. TelemetryMiddleware assigns a `trace_id` (UUID)
4. AuthMiddleware resolves user from token/API key/cookie
5. Routing dispatches to page handler or API endpoint
6. Handler runs, renders component tree to HTML
7. Response flows back through middleware

## Reactive loop

1. Browser sends event over WebSocket (`{"type": "event", "event": "increment", ...}`)
2. Event handler mutates `State` cell
3. `StateRenderer` re-renders the page function
4. DOM patch broadcast to all WebSocket clients
5. Client swaps `outerHTML` of the target element

## Agent execution loop

```
prompt → provider → tool call? → execute tool → feed result back → final answer
```

1. Agent builds messages from prompt + system_prompt + context
2. Provider (OpenAI/Anthropic/Mock) processes the messages
3. If the response contains a tool-call marker, the tool is invoked from the registry
4. The tool result is appended to messages and the loop continues
5. When no more tool calls are requested, the final answer is returned

## Correlation ID propagation

Every request gets a `trace_id` (UUID) via `ContextVar`. This ID propagates through:
- HTTP request telemetry
- Agent runs (recorded in `AgentRun.trace_id`)
- Tool call telemetry
- Queue items (stored in envelope, restored in worker)
- Mesh event envelopes (`correlation_id` field)

## Runtime Engine

The `ExecutionEngine` is the unified execution model. Every meaningful operation — HTTP request, agent run, tool call, MCP dispatch, worker job, task, workflow step, human approval, event handler — produces an `Execution` record with:

- `execution_id` / `trace_id` / `parent_execution_id` — full traceability
- `status` — created → planned → authorized → running → waiting → completed | failed | cancelled | timed_out
- `effects` — side effects recorded on the execution
- `state_changes` — observable state transitions
- `cost` / `duration_seconds` — resource accounting
- `error` — structured error with execution context

### Intent → Capability → Compute → Effect → State

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
await engine.execute(Intent(name="payout"), ask_human("Approve payout?"))

# Resume or deny
await engine.approve(execution_id, by="admin")
await engine.deny(execution_id, by="admin", reason="not now")
```

### Planner & Adaptive Supervisor

```python
from voodoo.runtime import Planner, ComputeParticipant, AdaptiveSupervisor

planner = Planner()
planner.register(
    ComputeParticipant(name="agent", kind="agent", capabilities=["reason"])
)
planner.register(
    ComputeParticipant(name="human", kind="human", capabilities=["approve"])
)

supervisor = AdaptiveSupervisor(planner)
run = await supervisor.run(Intent(name="complex").require("reason").require("approve"))
```

### Durable Recovery

```python
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.persistence import JSONFileExecutionStore

engine = ExecutionEngine()
engine.use_store(JSONFileExecutionStore(".voodoo/executions.jsonl"))
# After restart:
recovered = engine.recover()  # reloads unfinished executions
```

```bash
voodoo recover --store .voodoo/executions.jsonl
voodoo inspect approvals --pending
voodoo inspect plan notify.customer --requires email.send,sms.send
```

## Framework boundaries

The boundary between core and ecosystem is explicit. This keeps the framework small.

**Voodoo core** — runtime, routing, components, state, events, mesh, data, auth, tools, agent abstraction, MCP, telemetry, CLI.

**Voodoo ecosystem** (adapters and integrations) — OpenAI/Anthropic adapters, Postgres, Redis, Stripe, GitHub, Cloudflare, AWS, etc.

**The adapter philosophy** — Voodoo does not try to own every technology. A developer must eventually be able to replace Tailwind without replacing Voodoo. The same applies to LLM providers, databases, queues, auth providers, storage, and deployment. Built on Starlette, Uvicorn, Pydantic, aiosqlite, and standard Python async — Voodoo must remain interoperable with FastAPI, SQLAlchemy, httpx, pytest, and asyncio. It must not become an island.

### Runtime Configuration & Provider Migration (§28, §31)

Infrastructure is selected by configuration, never by code changes. Standard application code (`storage.upload()`, `enqueue()`, `mesh.publish()`, `model.generate()`) runs identically across providers.

#### Provider Migration Matrix (§28)

| Capability | Local (Default) | Production | Future / Scaled |
|------------|-----------------|------------|-----------------|
| **Database** | SQLite (`sqlite`) | PostgreSQL (`postgres`) | PostgreSQL / CockroachDB |
| **Queue** | SQLite (`sqlite`) or Memory (`memory`) | PostgreSQL (`postgres`) / Redis (`redis`) | SQS / NATS / RabbitMQ |
| **Events** | SQLite (`sqlite`) or In-Process (`local`) | PostgreSQL (`postgres`) | NATS / Kafka |
| **Objects** | Local Filesystem (`local`) | S3 (`s3`) — AWS S3, MinIO, R2 | Cloudflare R2 / GCS |
| **Cache** | In-Memory (`memory`) | Redis (`redis`) | Memcached / Dragonfly |
| **Models** | Local / Mock (`mock:default`, `ollama:...`) | OpenAI / Anthropic / Gemini | Custom fine-tuned / Router |

#### Configuration Example (`voodoo.yaml`)

```yaml
runtime:
  mode: production

database:
  provider: sqlite
  path: ${DATABASE_URL:.voodoo/state/data.db}

queue:
  provider: sqlite

events:
  provider: sqlite

objects:
  provider: local
  base_dir: ${VOODOO_OBJECTS_DIR:.voodoo/objects}

cache:
  provider: memory

models:
  default: openai:gpt-4o
```

**S3-compatible object storage (Sprint 12):** switch `objects.provider` to `s3` for AWS S3, MinIO, or Cloudflare R2. Install the extra (`pip install "voodoo-framework[s3]"`) and set credentials:

```yaml
objects:
  provider: s3
  bucket: ${VOODOO_BUCKET:my-bucket}
  endpoint: ${VOODOO_OBJECTS_ENDPOINT:}
  # extra:
  #   root_prefix: ${VOODOO_OBJECTS_ROOT_PREFIX:}
```

Credentials come from `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (or `VOODOO_S3_KEY` / `VOODOO_S3_SECRET`), and the region from `AWS_DEFAULT_REGION`. Non-AWS endpoints (MinIO, R2) use path-style addressing automatically; AWS uses virtual-hosted style. The provider supports presigned GET/PUT URLs, checksum + content-type metadata, and multipart uploads for objects ≥ 8 MiB (`ObjectStoreCapabilities.multipart`).

**Redis queue + cache (Sprint 13):** switch `queue.provider` and/or `cache.provider` to `redis` for a shared, durable, multi-process backend. Install the extra (`pip install "voodoo-framework[redis]"`) and point at a server:

```yaml
queue:
  provider: redis
  url: ${VOODOO_QUEUE_URL:redis://localhost:6379/0}

cache:
  provider: redis
  url: ${VOODOO_CACHE_URL:redis://localhost:6379/0}
```

The URL resolves from `queue.url` / `cache.url` → `VOODOO_QUEUE_URL` / `VOODOO_CACHE_URL` → `VOODOO_REDIS_URL` → `extra.host`/`port`/`db` → `redis://localhost:6379/0`. `RedisQueue` implements the full `VoodooQueue` protocol (priority ordering, delayed delivery, idempotency keys, lease-based claiming, per-status stats) using atomic Lua scripts over ZSETs + per-task hashes; `RedisCache` implements `VoodooCache` with TTL + durability (`CacheCapabilities.ttl`, `.durable`). Both are honest about capabilities — `RedisQueue` declares `at_least_once` delivery and `best_effort` ordering, and `MemoryCache` rejects `set(ttl=...)` with a `CapabilityError` rather than silently dropping the TTL.

**Precedence:** Explicit file configuration (`voodoo.yaml` / `voodoo.toml`) > Environment variables (`VOODOO_QUEUE_PROVIDER`, `DATABASE_URL`, etc.) > Local zero-infra defaults.

**The "do not build" list** — no custom programming language, no JSX equivalent, no full React clone, no custom CSS/JS framework, no distributed database, no Kubernetes orchestration, no Celery replacement, no fully autonomous coding agent, no automatic production deployments, no self-modifying production code, no autonomous financial transactions, no vector database abstraction, no custom LLM training infrastructure.

**Security threat model** — the AI trust chain is Browser → Application → Agent → Tool → Internet → External system. Modeled threats: prompt injection, tool injection, SSRF, credential leakage, malicious MCP servers, unauthorized mesh events, agent privilege escalation, arbitrary code execution, malicious generated code. The `Capability` primitive is the structural answer — agents never receive ambient authority, only explicit, revocable, time-limited capabilities.

## Key design decisions

- **Minimal scaffold** — `voodoo new` creates only `app/page.py`, `voodoo.toml`, `pyproject.toml`. No `main.py`, no `.env`, no placeholder directories.
- **`voodoo dev` is canonical** — Auto-discovers the app (`main:app` if `main.py` exists, otherwise `voodoo.core:app`). No manual ASGI setup needed.
- **Lazy database** — SQLite initializes on first `get_db()` call, not at startup. Default path: `.voodoo/state/data.db`. PostgreSQL (Sprint 10) follows the same lazy pattern: the `postgres://` URL is resolved at config time, the psycopg connection opens on first use. Since Sprint 11 the app lifespan runs the durable execution store on PostgreSQL (via the shared translated migrations) when `database.provider: postgres`; the scheduler remains SQLite-backed (documented).
- **Lazy storage** — No storage directories created unless storage is used.
- **Lazy workers** — Worker subsystem starts only if workers are registered.
- **`voodoo.toml` preferred** — TOML config preferred for new projects; YAML compatibility preserved.
- **`voodoo ai init`** — AI development context is opt-in, not generated during `voodoo new`.
- **Starlette as ASGI base** — not reinventing the wheel.
- **Single-process queue** — asyncio.Queue today; distributed backend (Redis) is a seam. Since Sprint 13 the seam is real: `RedisQueue` provides a durable, multi-process backend behind the same `VoodooQueue` protocol.
- **Lazy provider imports** — `voodoo[ai]` installs SDKs, but they're imported only when a provider is used.
