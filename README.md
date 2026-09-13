# Voodoo

**The programmable runtime for adaptive applications and operational systems.**

Voodoo lets a Python application start as a page or API and grow into durable
workers, agents, human approvals, distributed participants and physical-device
workflows without replacing the execution model underneath it.

> Composition over configuration. Python over DSLs. Adapters over lock-in. Explicit capabilities over unrestricted autonomy.

## Why Voodoo?

Modern systems often assemble separate frameworks for HTTP, UI, persistence,
queues, scheduling, AI, realtime communication, workflow execution,
observability and devices. Voodoo provides a common runtime model so those
pieces can converge when the application actually needs them.

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

`Compute`, `Time`, `Resource` and `Constraint` govern Execution. AI is one form
of Compute, not a second runtime.

An `Execution` is not every function call. It is meaningful work worth
observing, authorizing, recovering, accounting for, waiting on or reasoning
about.

For operational systems Voodoo also keeps attempted action and observed reality
separate:

```text
Effect != Observation
```

An Effect records what the runtime tried to do. An Observation records evidence
about what actually happened in the World.

## Quick start

```bash
pip install voodoo-framework
voodoo create my_app
cd my_app
voodoo dev
```

Open `http://localhost:8000`. The default path requires no external database,
queue or object store.

AI provider SDKs are optional:

```bash
pip install "voodoo-framework[ai]"
```

The core package does not install OpenAI, Anthropic, Gemini or Ollama SDKs.
Providers are resolved lazily when used.

## Start simple

| You need | Voodoo primitive |
|---|---|
| UI-local mutable value | `state()` |
| Persistent business data | `Model` |
| Browser interaction | Python-callable UI event/action |
| Decoupled application notification | Mesh / event bus |
| Retryable background work | `@task` |
| Meaningful durable/observable work | `Execution` |
| LLM reasoning and tool use | `Agent` + `@tool` |
| Authorization to produce an effect | `Capability` |
| Human decision inside work | HITL approval |
| Operational identity/evidence | `Entity` + `Observation` + `WorldModel` |
| Durable desired outcome | `Goal` + `GoalRuntime` |
| External physical participant | Edge / `DeviceGateway` |
| Future/recurring work | Scheduler |

See `docs/choosing-primitives.md` for semantic boundaries between State, Model,
Memory, events, tools, tasks, capabilities and executions.

## Small AI + data + event example

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

The local chain is exactly what it says: Agent → Tool → Model → Mesh. Tools may
also be exposed through MCP, but MCP is a separate interoperability boundary,
not a fake step inserted into every tool call.

## Operational closed loop

Sprint 27 adds a zero-infrastructure canary proving the deeper runtime model:

```text
simulated device
  → Edge
  → Observation
  → World
  → Goal / Intent
  → context-aware Planner
  → Capability + Policy
  → Execution
  → Effect
  → device
  → ACK / observed evidence
  → Observation
  → World
```

Run it with:

```bash
python examples/operational_closed_loop/main.py
```

The World does not change merely because an Effect was sent. It changes only
when the simulated device reports observed evidence back through the Edge
boundary.

## What makes Voodoo different

- **One execution model.** APIs, agents, tools, workers, humans, remote nodes and
  devices can converge on one traceable runtime instead of independent
  orchestration stacks.
- **World-aware operational state.** `Entity`, `Relationship`, `Observation` and
  `WorldModel` represent changing operational reality with provenance.
- **Governed agency.** Goal/Intent planning can use current World context, but
  authority still flows through Capability and Policy.
- **AI is Compute.** Agents are powerful participants, not ambient authority.
- **Durable when it matters.** Executions, tasks, schedules, Goals and approvals
  have persistence/recovery seams.
- **Human-in-the-loop is native.** Waiting is an execution lifecycle state.
- **Distributed without a second runtime.** Remote work re-enters the same
  ExecutionEngine, capability and policy boundary.
- **Physical participants use the same semantics.** Edge devices report
  evidence and receive Effects without owning a DeviceExecutionEngine.
- **Local-first, production-capable.** SQLite/local filesystem provide the
  default path; PostgreSQL, Redis and S3-compatible storage are adapters.
- **Observability is structural.** Trace/execution lineage connects meaningful
  work, Effects and resulting Observations.

## Canonical import model

The 2.x package root remains a compatibility facade. New code should use the
namespace that owns the concept:

```python
from voodoo import App, Agent, Model, page, state, task, tool
from voodoo.ui import Button, Card, DataTable
from voodoo.runtime import ExecutionEngine, Goal, GoalRuntime, Planner
from voodoo.world import Entity, Observation, WorldModel
from voodoo.edge import DeviceGateway, WorldAwareDeviceGateway
from voodoo.protocol import WorldSnapshot, RemoteExecutionRequest
```

See `docs/public-api-3.md` for the 3.0 import law and 2.x compatibility policy.

## Major capabilities

**Application:** server-rendered/reactive Python UI, routing/APIs, design
system/themes, SEO, async ORM, auth and security middleware.

**Runtime:** ExecutionEngine, durable checkpoints/recovery, workers/tasks,
scheduler, event infrastructure, human approvals, capability security,
contextual Policy, Goal Runtime and bounded adaptive planning/supervision.

**World:** stable entities, relationships, append-only observations, durable
World storage and reasoning/policy snapshots.

**AI:** agents, native provider tool calling, `@tool`, MCP integration, Memory,
model/provider abstraction and config-driven OpenAI-compatible endpoints.

**Distributed/Edge:** governed remote execution, replay/idempotency, distributed
WAITING/HITL, device identity/auth, HTTP/MQTT Edge semantics, effect delivery,
ACKs and Edge → World evidence convergence.

**Infrastructure adapters:** PostgreSQL, Redis, S3-compatible object storage and
OpenTelemetry are optional extras behind runtime contracts.

## Installation

```bash
# Core runtime
pip install voodoo-framework

# Model providers
pip install "voodoo-framework[ai]"

# Production adapters as needed
pip install "voodoo-framework[postgres,redis,s3,otel]"

# Edge MQTT adapter when needed
pip install "voodoo-framework[edge]"

# Development tools
pip install "voodoo-framework[dev]"
```

Other supported installation paths include Homebrew, `uv tool install
voodoo-framework`, and `pipx install voodoo-framework`.

## Configuration

Voodoo is zero-config locally. Add `voodoo.yaml` only when you need explicit
providers:

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

## Documentation

Start here:

- `docs/hello_world.md` — first application
- `docs/choosing-primitives.md` — which abstraction to use
- `docs/primitives.md` — computational model
- `docs/execution-model.md` and `docs/runtime.md` — execution semantics
- `docs/agents.md`, `docs/tools.md`, `docs/mcp.md` — AI/tool integration
- `docs/hitl.md` — human approvals
- `docs/protocol.md` — language-neutral semantic boundary
- `docs/public-api-3.md` — canonical 3.0 import model
- `ARCHITECTURE.md` — root architecture reference
- `ROADMAP.md` — long-range architectural direction
- `SPRINT_PLAN.md` — implementation source of truth

## Examples

| Example | Purpose |
|---|---|
| `examples/hello_world/` | smallest page |
| `examples/dashboard/` | reactive UI/state |
| `examples/realtime/` | realtime communication |
| `examples/ai_agent/` | agent/tool application |
| `examples/ai_saas/` | UI + Agent + Tool + Mesh + Worker + Model |
| `examples/ui_magic/` | current callable UI / Design System acceptance app |
| `examples/operational_closed_loop/` | Edge → World → Goal → Execution → Effect → evidence canary |

## Project status

Voodoo is beta software. `SPRINT_PLAN.md` is the implementation source of truth
and `ROADMAP.md` is the architectural source of truth. Sprint completion and a
published package release are intentionally separate operations.

## Contributing and security

See `CONTRIBUTING.md` for development workflow, `SECURITY.md` for vulnerability
reporting and `CODE_OF_CONDUCT.md` for community expectations.

## License

MIT. See `LICENSE`.
