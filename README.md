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

Open `http://localhost:8000`. On first run Voodoo creates:

```text
.voodoo/application.vstore
```

That Store is the default durable application substrate for local data, durable
work, scheduling, event state, objects, execution state, workflows, approvals,
identity state, and Edge/device state. A local application does not require an
external database, Redis, queue server, or object server.

AI provider SDKs are optional:

```bash
pip install "voodoo-framework[ai]"
```

The core package does not install OpenAI, Anthropic, Gemini or Ollama SDKs.
Providers are resolved lazily when used.

## Voodoo Store by default

Voodoo Store is embedded application infrastructure. The framework owns one
Runtime Store handle per process/application lifecycle and shares it across
Store-backed Runtime domains.

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Model / Data
    +-- Jobs / Queue
    +-- Scheduler
    +-- Events
    +-- Objects
    +-- Execution / Workflow / HITL
    +-- Identity
    +-- Edge
    |
    v
.voodoo/application.vstore
```

The Store is local-first and single-writer. PostgreSQL, SQLite, Redis, S3 and
other infrastructure remain explicit adapters for workloads that need them;
they are not silent defaults.

## Start simple

| You need | Voodoo primitive |
|---|---|
| UI-local mutable value | `state()` |
| Persistent business data | `Model` |
| Browser interaction | Python-callable UI event/action |
| Decoupled application notification | Mesh / event bus |
| Retryable background work | `@task` / durable queue |
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

With the default configuration, `Lead` is persisted through Voodoo Store. Tools
may also be exposed through MCP, but MCP is a separate interoperability
boundary, not a fake step inserted into every tool call.

## Operational closed loop

The operational runtime keeps attempted effects separate from observed reality:

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

Run the canary with:

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
- **Store-first and local-first.** Voodoo Store provides the default embedded
  durable infrastructure; PostgreSQL, SQLite, Redis and S3-compatible storage
  are explicit adapters.
- **Observability is structural.** Trace/execution lineage connects meaningful
  work, Effects and resulting Observations.

## Canonical import model

Voodoo 3.0 keeps the package root intentionally small. Common application
vocabulary lives at `voodoo`; subsystem catalogs live in the namespace that
owns their semantics:

```python
from voodoo import App, Agent, Model, page, state, task, tool
from voodoo.ui import Button, Card, DataTable
from voodoo.runtime import ExecutionEngine, Goal, GoalRuntime, Planner
from voodoo.world import Entity, Observation, WorldModel
from voodoo.edge import DeviceGateway, WorldAwareDeviceGateway
from voodoo.protocol import WorldSnapshot, RemoteExecutionRequest
```

See `docs/public-api-3.md` for the 3.0 import law and clean-break migration map.

## Major capabilities

**Application:** server-rendered/reactive Python UI, routing/APIs, design
system/themes, SEO, async Model persistence, auth and security middleware.

**Runtime:** ExecutionEngine, durable checkpoints/recovery, workers/tasks,
scheduler, event infrastructure, human approvals, capability security,
contextual Policy, Goal Runtime and bounded adaptive planning/supervision.

**World:** stable entities, relationships, append-only observations, durable
World storage and reasoning/policy snapshots.

**AI:** agents, native provider tool calling, `@tool`, MCP integration, Memory,
model/provider abstraction and config-driven OpenAI-compatible endpoints.

**Distributed/Edge:** governed remote execution, replay/idempotency, distributed
WAITING/HITL, node membership/routing, device identity/auth, HTTP/MQTT Edge
semantics, effect delivery, ACKs and Edge → World evidence convergence.

**Infrastructure adapters:** PostgreSQL, SQLite, Redis, S3-compatible object
storage and OpenTelemetry are optional or explicit integrations behind Runtime
contracts.

## Installation

```bash
# Core runtime (includes the Voodoo Store dependency)
pip install voodoo-framework

# Model providers
pip install "voodoo-framework[ai]"

# Explicit external adapters as needed
pip install "voodoo-framework[postgres,redis,s3,otel]"

# Explicit SQLite adapter when needed
pip install "voodoo-framework[sqlite]"

# Edge MQTT transport when needed
pip install "voodoo-framework[edge]"

# Development tools
pip install "voodoo-framework[dev]"
```

Other supported installation paths include `uv tool install voodoo-framework`
and `pipx install voodoo-framework`.

## Configuration

Voodoo is zero-config locally. The effective defaults are equivalent to:

```toml
[store]
provider = "voodoo"
path = ".voodoo/application.vstore"

[database]
provider = "voodoo"

[queue]
provider = "voodoo"

[events]
provider = "voodoo"

[objects]
provider = "voodoo"
```

You normally do not need to write those blocks. Override only the domain that
needs external infrastructure. For example:

```toml
[database]
provider = "postgres"
url = "postgresql://..."

[queue]
provider = "redis"
url = "redis://..."

[objects]
provider = "s3"
bucket = "my-bucket"
```

Voodoo does not silently migrate or copy legacy SQLite/PostgreSQL/Redis/S3 data
into the Store at startup. Migration is an explicit operation.

## Current Store boundaries

The Store-first path is usable, but current 0.2.x boundaries are explicit:

- schedule enable/disable is supported, but arbitrary schedule-cursor
  repositioning is not exposed by Store 0.2.2;
- Events and Objects preserve their Framework contracts through Store-backed
  compatibility layers while richer native Python bindings evolve;
- node-local Stores are not replicated automatically;
- Voodoo does not claim distributed consensus, global serializable
  transactions, or global exactly-once execution.

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
| `examples/basics/hello_world/` | smallest page |
| `examples/web/dashboard/` | reactive UI/state |
| `examples/web/realtime/` | realtime communication |
| `examples/ai/agent/` | agent/tool application |
| `examples/ai/saas/` | UI + Agent + Tool + Mesh + Task + Model |
| `examples/web/ui_magic/` | current callable UI / Design System acceptance app |
| `examples/adaptive/operational_closed_loop/` | Edge → World → Goal → Execution → Effect → evidence canary |

## Project status

Voodoo is beta software. **v3.0.0** is the current architecture baseline and
published package release. Sprint completion and package release remain
separate operations, so future `main` changes must not be described as released
until the release workflow completes.

## Contributing and security

See `CONTRIBUTING.md` for development workflow, `SECURITY.md` for vulnerability
reporting and `CODE_OF_CONDUCT.md` for community expectations.

## License

MIT. See `LICENSE`.
