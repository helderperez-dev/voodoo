# Voodoo

**The programmable runtime for adaptive applications and operational systems.**

[Website](https://voodoo.build) · [Documentation](#documentation) · [Architecture](ARCHITECTURE.md) · [Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md)

[![CI](https://github.com/helderperez-dev/voodoo/actions/workflows/ci.yml/badge.svg)](https://github.com/helderperez-dev/voodoo/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/voodoo-framework)](https://pypi.org/project/voodoo-framework/)
[![Python](https://img.shields.io/pypi/pyversions/voodoo-framework)](https://pypi.org/project/voodoo-framework/)
[![License](https://img.shields.io/badge/license-MIT-informational)](LICENSE)

Voodoo lets a Python application start small — a page, API, model, task or agent —
and grow into durable workflows, human approvals, adaptive goals, distributed
participants and physical-device systems **without replacing the execution model
underneath it**.

> Composition over configuration. Python over DSLs. Adapters over lock-in.
> Explicit capabilities over ambient authority.

## What Voodoo is

Most application stacks accumulate separate execution models as they grow:
HTTP handlers, frontend state, database jobs, queues, schedulers, agent loops,
workflow engines, event buses, human approvals, distributed workers and device
control.

Voodoo treats those as different manifestations of one programmable Runtime.

```text
Entity → State → Intent → Capability + Policy → Execution → Effect → State
```

For operational systems, the model becomes a closed loop:

```text
World
  ↓
Observation
  ↓
Goal / Intent
  ↓
Plan
  ↓
Capability + Policy
  ↓
Execution
  ↓
Effect
  ↓
Participant
  ↓
ACK / observed evidence
  └────────────────────→ World
```

Two rules are central:

- **AI is Compute, not authority.** Agents participate in the same Runtime and
  remain subject to capabilities and policy.
- **Effect != Observation.** What the system attempted is not automatically
  treated as evidence that the real world changed.

An `Execution` is not every function call. It is meaningful work worth
authorizing, observing, recovering, accounting for, waiting on, or reasoning
about.

## Quick start

Voodoo requires Python 3.12+.

```bash
pip install voodoo-framework

voodoo create my_app
cd my_app
voodoo dev
```

Open `http://localhost:8000`.

A fresh application needs no external database, Redis server, queue service or
object server. On first run, Voodoo creates its local durable substrate:

```text
.voodoo/application.vstore
```

### Small application

```python
from voodoo import App, page
from voodoo.ui import Heading, Page, Stack, Text

app = App()


@page("/")
def home():
    return Page(
        Stack(
            Heading("Hello, Voodoo", level=1),
            Text("One application. One runtime."),
            gap="md",
        )
    )


if __name__ == "__main__":
    app.run()
```

## Start simple, grow only when needed

Voodoo is designed for progressive complexity. You do not need World Models,
Goals, AI or distributed execution to build a normal application.

| You need | Use |
|---|---|
| UI-local mutable value | `state()` |
| Persistent business data | `Model` |
| Page / browser interaction | Voodoo UI + Python-callable events |
| HTTP/API surface | routing / API primitives |
| Retryable background work | `@task` |
| Future or recurring work | Runtime scheduling |
| Decoupled notification | Mesh / event bus |
| Meaningful governed work | `Execution` |
| LLM reasoning and tool use | `Agent` + `@tool` |
| Authorization to produce effects | `Capability` + `Policy` |
| Human decision during work | HITL approval |
| Durable desired outcome | `Goal` + `GoalRuntime` |
| Operational reality | `Entity` + `Observation` + `WorldModel` |
| Physical/external participant | Edge / `DeviceGateway` |
| Governed node-to-node work | Runtime Fabric |

See [Choosing primitives](docs/choosing-primitives.md) for the semantic
boundaries between state, models, events, tools, tasks, capabilities and
executions.

## One Runtime, one durable substrate

Voodoo Store is the default embedded infrastructure for a local application.

```text
Application
    │
    ▼
Voodoo Runtime
    │
    ├── Model / Data
    ├── Jobs / Queue
    ├── Scheduler / Cron / Triggers
    ├── Events / Outbox
    ├── Objects
    ├── Execution / Workflow / Goal / HITL
    ├── Identity
    └── Edge / device state
    │
    ▼
RuntimeStore
    │
    ▼
.voodoo/application.vstore
```

The default path is **local-first and single-writer**. PostgreSQL, SQLite,
Redis, S3-compatible object storage and OpenTelemetry remain explicit adapters
or integrations for workloads that need them; they are not silent defaults.

Store owns durable mechanics. Runtime owns semantics, authority and
intelligence.

## The Voodoo 3.0 architecture

Voodoo 3.0 deliberately converges concepts under one semantic owner instead of
preserving duplicate historical namespaces.

```text
src/voodoo/
├── core/          application facade, lifecycle, state and events
├── primitives/    foundational semantic concepts
├── runtime/       canonical Runtime semantics
│   ├── execution/
│   ├── scheduling/
│   ├── agency/
│   ├── distributed/
│   ├── reconciliation/
│   └── inspection/
├── world/         entities, relationships, observations, WorldModel
├── edge/          physical/external participant boundary
├── protocol/      language-neutral semantic contracts
├── ai/            native Agent/provider/tool semantics
├── integrations/  MCP, provider SDK and OpenTelemetry integrations
├── observability/ traces, metrics and runtime inspection
├── data/          Store-first Model API
├── storage/       infrastructure contracts
├── adapters/      explicit infrastructure providers
├── ui/            reactive UI and design system
├── routing/       pages and APIs
├── mesh/          realtime/event transport surface
├── auth/          application authentication surfaces
├── security/      HTTP security and redaction
└── cli/           developer tooling
```

The package root stays intentionally small:

```python
from voodoo import Agent, App, Model, page, state, task, tool
```

Advanced APIs come from the namespace that owns them:

```python
from voodoo.ui import Button, Card, DataTable
from voodoo.runtime import ExecutionEngine, Goal, GoalRuntime, Planner
from voodoo.world import Entity, Observation, WorldModel
from voodoo.edge import DeviceGateway, WorldAwareDeviceGateway
from voodoo.protocol import RemoteExecutionRequest, WorldSnapshot
from voodoo.integrations.mcp import mcp
```

See [Voodoo 3.0 public API law](docs/public-api-3.md) for the canonical import
model and the clean-break migration map from 2.x.

## Adaptive applications

An adaptive application can observe facts, express desired outcomes and allow
the Runtime to reconcile the two without creating a second orchestration model.

```python
from voodoo import App
from voodoo.primitives import Intent

app = App()

conversion = app.observation("business", "conversion")


@app.goal(
    "grow",
    observes=(conversion,),
    target_entity_id="business",
    propose=lambda goal, world: Intent(name="conversion.adjust"),
)
def growth(world):
    return world is not None and world.entity.properties.get("conversion", 0) >= 0.10


@app.capability("conversion.adjust")
async def improve(ctx):
    return {"accepted": True}
```

The application declares observations, goals and executable capabilities.
Execution, scheduling, reconciliation and authority remain Runtime concerns.

## AI and tools

AI is optional. The core package does not install provider SDKs.

```bash
pip install "voodoo-framework[ai]"
```

A tool remains normal Python while also becoming introspectable Runtime
capability for agent/tool workflows:

```python
from voodoo import Agent, tool


@tool
async def find_customer(email: str) -> dict:
    """Find a customer by email."""
    return {"email": email}


agent = Agent(
    model="mock:test",
    tools=[find_customer],
)
```

MCP is an interoperability boundary under `voodoo.integrations.mcp`; it is
not a second tool registry or execution model.

## Operational systems and Edge

Voodoo can connect software decisions to external or physical participants
without treating a sent command as reality.

```text
Device evidence
    ↓
Edge
    ↓
Observation
    ↓
World
    ↓
Goal / Intent
    ↓
Planner
    ↓
Capability + Policy
    ↓
Execution
    ↓
Effect
    ↓
Device
    ↓
ACK / measured evidence
    └──────────────→ Observation → World
```

Run the zero-infrastructure operational canary:

```bash
python examples/adaptive/operational_closed_loop/main.py
```

The example proves the important boundary: the World changes only after the
simulated device reports observed evidence, not merely because an Effect was
sent.

## Distributed Runtime

Voodoo scales by adding Runtime nodes, not by letting multiple processes write
the same Store file.

```text
same application semantics
          │
          ▼
     Runtime Fabric
      /    |    \
   node-a node-b node-c
      |      |      |
   a.vstore b.vstore c.vstore
```

Each node owns its local Store. Remote work re-enters canonical
`Capability + Policy + Execution` at the destination.

The Runtime Fabric includes authenticated node identity, durable membership,
health/discovery, placement, lease generations, replay/idempotency boundaries
and bounded failover. Failover remains constrained by the semantics of the work:
ambiguous external or physical effects must not be blindly reissued.

## Major capabilities

| Domain | Capabilities |
|---|---|
| Application | pages, APIs, reactive Python UI, design system, SEO |
| Data | Store-first `Model`, explicit SQL adapters |
| Runtime | Execution, recovery, tasks, scheduling, workflows, transactions/outbox |
| Agency | Goals, planning, adaptive supervision, reconciliation |
| Authority | Identity, Capability, contextual Policy |
| Human | durable HITL waiting/approval |
| AI | Agents, tools, provider abstraction, persistent Memory |
| Interoperability | MCP integration, language-neutral Protocol |
| Distributed | remote execution, membership, placement, leases, bounded failover |
| World | Entity, Relationship, Observation, WorldModel |
| Edge | device identity/session/effects/ACK/evidence flows |
| Observability | execution lineage, traces, metrics and inspection |
| Infrastructure | PostgreSQL, SQLite, Redis, S3 and OpenTelemetry adapters/integrations |

## Installation options

```bash
# Core Runtime + Voodoo Store
pip install voodoo-framework

# AI providers
pip install "voodoo-framework[ai]"

# External infrastructure adapters
pip install "voodoo-framework[postgres,redis,s3,otel]"

# Explicit SQLite adapter
pip install "voodoo-framework[sqlite]"

# Edge MQTT transport
pip install "voodoo-framework[edge]"

# Development dependencies
pip install "voodoo-framework[dev]"
```

You can also install the CLI with `uv tool install voodoo-framework` or
`pipx install voodoo-framework`.

## Configuration

A fresh application is zero-config. The effective defaults are equivalent to:

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

Override only the domain that actually needs external infrastructure:

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

Voodoo does not silently migrate or copy legacy external data into Voodoo Store
at startup. Migration is an explicit operation.

## Examples

| Example | What it demonstrates |
|---|---|
| `examples/basics/hello_world/` | smallest application + native design system |
| `examples/web/dashboard/` | reactive UI/state |
| `examples/web/realtime/` | realtime communication |
| `examples/web/ui_magic/` | callable UI + current design-system acceptance app |
| `examples/ai/agent/` | Agent + Tool |
| `examples/ai/saas/` | UI + Agent + Tool + Mesh + Task + Model |
| `examples/adaptive/operational_closed_loop/` | Edge → World → Goal → Execution → Effect → evidence |

## Documentation

A useful reading order:

1. [Hello world](docs/hello_world.md)
2. [Choosing primitives](docs/choosing-primitives.md)
3. [Computational primitives](docs/primitives.md)
4. [Execution model](docs/execution-model.md)
5. [Runtime](docs/runtime.md)
6. [Agents](docs/agents.md) and [Tools](docs/tools.md)
7. [Human-in-the-loop](docs/hitl.md)
8. [MCP](docs/mcp.md)
9. [Protocol](docs/protocol.md)
10. [Voodoo 3.0 public API law](docs/public-api-3.md)
11. [Architecture](ARCHITECTURE.md)
12. [Roadmap](ROADMAP.md)

`SPRINT_PLAN.md` is the implementation tracker; it should not be treated as a
marketing promise for future capabilities.

## What Voodoo deliberately does not claim

Voodoo's architecture is broad, but its guarantees are intentionally explicit.

Current Voodoo 3.0 does **not** claim:

- automatic Store replication or synchronization between nodes;
- shared multi-writer `.vstore` files;
- distributed consensus;
- globally serializable cross-node transactions;
- global exactly-once execution;
- production PKI/OIDC/mTLS infrastructure;
- a managed Voodoo Cloud control plane.

Current Voodoo Store 0.2.x also has explicit Python-binding boundaries around
some richer native Topics/Streams, Object and schedule-cursor capabilities.
The Framework fails clearly or preserves a stable internal contract rather than
pretending unsupported guarantees exist.

## What Voodoo is trying to preserve

As the project grows, these properties are architectural constraints:

- one Runtime and one canonical Execution lifecycle;
- local-first progressive complexity;
- Python application code instead of a mandatory workflow DSL;
- explicit authority for effects;
- AI as a participant, not an ambient superuser;
- replaceable infrastructure behind contracts;
- topology changes without rewriting business semantics;
- observable lineage from Intent → Execution → Effect → Observation;
- one semantic owner per concept.

## Project status

Voodoo is **beta software**.

**v3.0.0** is the current published architecture baseline. The `main` branch may
contain post-release documentation or implementation work, so a merge to
`main` is not itself a package release.

The next numbered development sprint is intentionally selected from real
product/architecture pressure rather than by accumulating unrelated framework
features.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before
structural changes. Repository architecture is enforced by tests, including
rules that prevent removed 2.x compatibility namespaces from returning.

Security issues should follow [SECURITY.md](SECURITY.md). Community behavior is
covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).
