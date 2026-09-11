# Voodoo

**The programmable runtime for adaptive applications and operational systems.**

Voodoo lets Python applications grow from a page or API into durable workers, agents, human approvals, realtime communication and physical systems without replacing the execution model underneath them.

At its north star, **Voodoo gives AI durable agency in software and a governed body in the physical world**: intelligence can perceive state, remember, decide, act through explicit capabilities, observe consequences, recover, and continue across software and device boundaries.

> Composition over configuration. Python over DSLs. Adapters over lock-in. Explicit capabilities over ambient authority.

## Why Voodoo?

Modern applications often assemble separate frameworks for HTTP, UI, persistence, queues, scheduling, AI, realtime communication, observability and devices. Voodoo provides these as composable capabilities of one runtime.

The central model is:

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

An `Execution` is not every function call. It is meaningful work worth observing, authorizing, recovering, accounting for, waiting on, or reasoning about.

For autonomous and embodied systems, the same model closes the loop:

```text
World → Event/State → Intent → AI/Compute → Capability → Execution
      → Effect → Software/Human/Device → ACK/Observation → State ↺
```

Freedom to reason is not the same as unlimited authority to act. Voodoo makes useful autonomy possible by giving intelligent entities durable identity, memory, tools, time, execution and effects while making authority explicit and inspectable. See `docs/agency-and-embodiment.md`.

## Quick start

```bash
pip install voodoo-framework
voodoo create my_app
cd my_app
voodoo dev
```

Open `http://localhost:8000`. The default path requires no external database, queue or object store.

`voodoo create` is the primary onboarding path and scaffolds the local runtime. If you deliberately want only the smallest UI/routing scaffold, use `voodoo new`.

AI provider SDKs are optional:

```bash
pip install "voodoo-framework[ai]"
```

The core package does not install OpenAI, Anthropic, Gemini or Ollama SDKs. Providers are resolved lazily when used.

## Start simple, add runtime capabilities when they matter

| You need | Voodoo primitive |
|---|---|
| UI-local mutable value | `state()` |
| Persistent business data | `Model` |
| Browser interaction | `@event` |
| Decoupled application notification | Mesh / event bus |
| Retryable background work | `@task` |
| Meaningful durable/observable work | `Execution` |
| LLM reasoning and tool use | `Agent` + `@tool` |
| Authorization to produce an effect | `Capability` |
| Human decision inside work | HITL approval |
| Future/recurring work | Scheduler |
| Physical observation and action | Edge Device + Event/Effect |

See `docs/choosing-primitives.md` for the semantic boundaries between State, Model, Memory, events, tools, tasks, capabilities and executions.

## A small AI + data + event example

Install the `ai` extra for real providers, or use `mock:*` locally. This example intentionally claims only the chain it executes: **Agent → Tool → Model → Mesh**.

```python
from voodoo import Agent, Model, tool
from voodoo.mesh import mesh


class Lead(Model):
    name: str
    email: str


@tool
async def create_lead(name: str, email: str) -> str:
    lead = await Lead.create(name=name, email=email)
    await mesh.emit("lead.created", {"id": lead.id, "name": name})
    return f"Created lead #{lead.id}"


@mesh.on("lead.created")
async def notify(payload):
    print("new lead", payload["name"])


agent = Agent(model="mock:test", tools=["create_lead"])
```

For the broader UI → agent → tool → event → worker → database demonstration, run `examples/ai_saas/main.py`. Tools registered with `@tool` are also available to Voodoo's MCP integration; that exposure is a separate integration boundary rather than a fake step inserted into the local call chain.

## What makes Voodoo different

- **One execution model.** APIs, agents, tools, workers, humans and physical devices can participate in a traceable runtime rather than forming independent orchestration stacks.
- **AI is one form of Compute.** Agents are powerful participants, not the foundation every application must depend on.
- **Agency is durable.** Identity, memory, executions, tasks, schedules and approvals can survive process restarts using local persistence by default.
- **Action is capability-mediated.** Intelligent participants can be given real authority without relying on ambient, all-or-nothing privilege.
- **Human-in-the-loop is native.** Waiting for approval is an execution lifecycle state, not an ad-hoc polling pattern.
- **Physical systems use the same semantics.** Edge devices observe through events/state and act through effects/acknowledgements; they do not create a second runtime.
- **Local-first, production-capable.** SQLite/local filesystem provide the default path; PostgreSQL, Redis and S3-compatible storage are adapters.
- **Adaptive execution is optional.** Planner/supervisor capabilities are available when capability resolution, fallback or budget steering is useful; simple paths remain simple.
- **Observability is part of the runtime.** Correlation and execution context connect meaningful work across boundaries.

## Computational model

```text
Intent       desired outcome
Capability   ability + authorization to produce an effect
Execution    meaningful unit of runtime work
Effect       change produced by an execution
State        operational truth
```

`Compute`, `Time`, `Resource`, and `Constraint` govern how an Execution happens. See `docs/primitives.md`, `docs/execution-model.md`, `ARCHITECTURE.md`, `docs/runtime-consolidation.md`, and `docs/agency-and-embodiment.md`.

## Major capabilities

**Application:** server-rendered/reactive Python UI, routing/APIs, design system/themes, SEO, async ORM, auth and security middleware.

**Runtime:** ExecutionEngine, durable execution/checkpoints/recovery, workers/tasks, scheduler, event infrastructure, human approvals, capability security, telemetry and optional adaptive planning/supervision.

**AI:** agents, native provider tool calling, `@tool`, MCP integration, memory, model/provider abstraction and config-driven OpenAI-compatible endpoints.

**Physical systems:** Edge device identity/enrollment, HTTP/MQTT protocol boundary, device events/state, effect delivery/acknowledgement, reconnect semantics and idempotent physical action.

**Infrastructure adapters:** PostgreSQL, Redis, S3-compatible object storage and OpenTelemetry are optional extras behind runtime contracts.

## Installation

```bash
# Core runtime — no third-party AI provider SDKs
pip install voodoo-framework

# Model providers
pip install "voodoo-framework[ai]"

# Production adapters as needed
pip install "voodoo-framework[postgres,redis,s3,otel]"

# Edge MQTT transport
pip install "voodoo-framework[edge]"

# Development tools
pip install "voodoo-framework[dev]"
```

Other supported installation paths include Homebrew (`brew tap helderperez-dev/voodoo && brew install voodoo`), `uv tool install voodoo-framework`, and `pipx install voodoo-framework`.

Verify with:

```bash
voodoo version
```

## Configuration

Voodoo is zero-config locally. Add `voodoo.yaml` when you need explicit providers:

```yaml
database:
  provider: sqlite
queue:
  provider: sqlite
events:
  provider: sqlite
objects:
  provider: local
cache:
  provider: memory
runtime:
  run_api_through_runtime: true
```

AI configuration is opt-in and requires the corresponding optional SDK:

```yaml
ai:
  provider: openai
  model: gpt-4o
  api_key: "${OPENAI_API_KEY}"
```

Environment variables use the `VOODOO_*` convention. See `.env.example` for the full reference.

## Documentation

Start here:

- `docs/hello_world.md` — first application
- `docs/choosing-primitives.md` — which Voodoo abstraction to use
- `docs/primitives.md` — computational model
- `docs/execution-model.md` and `docs/runtime.md` — execution semantics
- `docs/agency-and-embodiment.md` — north star for AI agency and physical systems
- `docs/data.md` — Models and persistence
- `docs/events.md` and `docs/mesh.md` — communication boundaries
- `docs/workers.md` — background tasks
- `docs/agents.md`, `docs/tools.md`, `docs/mcp.md` — AI/tool integration
- `docs/hitl.md` — human approvals
- `docs/edge/` — physical-device protocol and runtime boundary
- `docs/telemetry.md` — observability
- `docs/deployment.md` — production deployment
- `ARCHITECTURE.md` — root architecture reference
- `docs/runtime-consolidation.md` — invariants that keep the runtime coherent

## Examples

| Example | Purpose |
|---|---|
| `examples/hello_world/` | smallest page |
| `examples/dashboard/` | reactive UI/state |
| `examples/realtime/` | realtime communication |
| `examples/ai_agent/` | agent/tool application |
| `examples/ai_saas/` | UI + Agent + Tool + Mesh + Worker + Model |

The examples are intentionally progressive. Applications do not need to adopt the complete runtime surface at once.

## Project status

Voodoo is beta software. The repository's `SPRINT_PLAN.md` is the source of truth for implementation progress; `ROADMAP.md` describes longer-term direction. Public API and behavior should be treated with beta-level compatibility expectations until a stable release policy is declared.

## Contributing and security

See `CONTRIBUTING.md` for the development workflow, `SECURITY.md` for vulnerability reporting, and `CODE_OF_CONDUCT.md` for community expectations.

## License

MIT. See `LICENSE`.
