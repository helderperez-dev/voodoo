# Architecture

> **Root architecture reference.** Detailed subsystem guides live under `docs/`.

## What Voodoo is

Voodoo is a **programmable runtime for adaptive applications and operational
systems**. Web applications, APIs, agents, background workers, human workflows,
remote nodes and physical devices converge on one Runtime and one canonical
Execution model.

```text
World / Application State
          |
          v
        Intent
          |
          v
Identity / Principal
          |
          v
Capability + Policy
          |
          v
 canonical Execution
          |
          v
Compute -> Effect -> observed evidence -> World
```

AI is one form of Compute. It is not a second runtime and it does not grant
ambient authority.

## Default infrastructure

Fresh applications are Store-first:

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Model / Data
    +-- Queue / Jobs
    +-- Scheduler / Cron / Triggers
    +-- Events / Outbox
    +-- Objects
    +-- Execution / Workflow / Goal / HITL
    +-- Identity
    +-- Edge / device state
    |
    v
RuntimeStore
    |
    v
.voodoo/application.vstore
```

The Framework depends on Voodoo Store and requires no external database, queue
server or object server for its local default path. PostgreSQL, SQLite, Redis,
S3 and other providers remain explicit adapters.

## Architectural laws

1. There is one Voodoo Runtime and one canonical `Execution` lifecycle.
2. Voodoo Store is the default local durable infrastructure provider.
3. Store owns durable mechanics; Runtime owns semantics, authority and intelligence.
4. Identity belongs to Runtime; persistence does not define authorization.
5. Application APIs do not leak native `voodoo_store` implementation types.
6. One Runtime process owns one local Store writer.
7. Multiple processes never coordinate by writing one shared `.vstore` file.
8. Scaling changes deployment topology, not application business architecture.
9. Distributed ownership comes before distributed storage/replication.
10. Remote work still enters Capability + Policy + canonical Execution.
11. Discovery or advertisement never grants authority.
12. Voodoo does not claim consensus, global transactions or global exactly-once semantics it has not implemented.

## One process, one Runtime Store

```text
Process / Runtime
       |
       v
 RuntimeStore
       |
       v
application.vstore
```

Infrastructure used before App startup acquires a process-shared Store. App
startup adopts the compatible handle instead of opening a competing writer.
Conflicting live Store configurations fail explicitly.

## Computational concepts

| Concept | Purpose |
|---|---|
| Entity | identifiable participant or thing |
| State | current operational truth |
| Intent | desired outcome |
| Capability | ability/authorization to produce an effect |
| Policy | contextual decision about whether authority may be exercised now |
| Execution | durable/observable meaningful unit of Runtime work |
| Effect | attempted external/state-changing action |
| Observation | evidence about what actually happened |
| Compute | how work is performed; AI is one form |
| Time | deadlines, retries, schedules and lifecycle |
| Resource | cost, tokens, CPU, memory, energy or other consumption |
| Constraint | condition that must hold |

`Effect != Observation`: sending a command does not make the World true. World
state changes from observed evidence.

## Choosing abstractions

| Need | Use |
|---|---|
| UI-local mutable value | `state()` |
| Persistent business data | `Model` |
| Retryable durable background delivery | Store-backed Queue / `@queue` |
| Callable retry/timeout wrapper | `@task` |
| Decoupled durable application notification | Event bus / Outbox |
| Meaningful governed operation | `Execution` |
| LLM reasoning/tool loop | `Agent` + `@tool` |
| Human decision in ongoing work | HITL approval |
| Durable desired outcome | `Goal` + `GoalRuntime` |
| Physical/external participant | Edge / `DeviceGateway` |
| Node-to-node governed work | Runtime Fabric |

UI state is not business persistence. A tool is not a Capability. An event is
not automatically an Execution.

## Identity and authority

```text
Identity
  +-- user
  +-- agent
  +-- service
  +-- device
  `-- node
        |
        v
AuthenticationEvidence
        |
        v
Principal
        |
        v
Capability + Policy
        |
        v
Execution
```

Roles, scopes, credentials and node advertisements are evidence/context. They do
not automatically become Runtime Capability grants.

## Durable Runtime state

The default Store-backed Runtime includes:

- Model Collections and CRUD/query compatibility;
- Jobs/Queue with leases, heartbeat, retries and idempotency keys;
- schedules, Cron and triggers;
- durable event state and replay;
- object bytes/metadata compatibility layer;
- Execution materialized state and journal;
- Goal and Workflow checkpoints;
- HITL approval persistence/recovery;
- built-in identity persistence;
- Edge device/session/effect/replay state.

Some richer native Store subsystems are not yet exposed through the Python
binding; stable Framework contracts hide those compatibility details.

## Local transactions and outbox

One local Runtime transaction can atomically combine Store KV/Collection
mutations and a durable outbox message:

```text
business state mutation
        +
   outbox record
        |
        v
 ONE Store commit
```

Delivery happens after commit with at-least-once semantics. The outbox message
id is the idempotency key for consumers that require duplicate suppression.
External APIs, jobs already executing elsewhere, and another node's Store are
not part of that local atomic transaction.

## Runtime Fabric

A Voodoo application can grow from one node to multiple node-local Runtimes:

```text
same application semantics
          |
          v
     Runtime Fabric
      /    |    \
   node-a node-b node-c
      |      |      |
   a.vstore b.vstore c.vstore
```

The fabric provides authenticated node identity, durable membership,
heartbeats/health, discovery, capability/service/ownership filtering,
load/locality/data-owner placement, lease generations and bounded failover.

Failover is permitted only where work semantics allow it. Ambiguous physical or
external work can be declared non-retryable so the Runtime does not blindly
reissue it on another node.

## Protocol boundary

Node advertisement, membership and fabric work request/outcome models live in
the language-neutral Protocol boundary. Transport is replaceable; authority and
Execution semantics are not.

## Deployment model

Default Store-backed production deployment:

```text
one process = one Voodoo Node = one local Store writer
```

Do not run multiple uvicorn/gunicorn workers against the same Store file. To
scale horizontally, add separate Voodoo Nodes with separate local Stores.

## External adapters

Explicit overrides include:

| Domain | Examples |
|---|---|
| Database | SQLite, PostgreSQL |
| Queue | Redis, PostgreSQL, legacy SQLite |
| Objects | S3-compatible storage |
| Cache | in-memory, Redis |
| Telemetry | OpenTelemetry |

Changing an infrastructure adapter does not replace Runtime authority or create
a second execution model.

## Package/module responsibilities

```text
src/voodoo/
├── core/        # App lifecycle/facade and errors
├── primitives/  # ontology and execution dimensions
├── runtime/     # Execution, identity, workflow, goals, fabric, Store boundary
├── storage/     # infrastructure contracts/adapters
├── data/        # Store-first Model + SQL compatibility
├── workers/     # task and durable queue runtime
├── ai/          # agents/providers/tools
├── world/       # entities/relationships/observations/world model
├── edge/        # physical/external participant boundary
├── protocol/    # transport/language-neutral contracts
├── ui/          # components/reactive state/design system
├── routing/     # page/API routing
├── mesh/        # realtime/remote communication surfaces
├── auth/        # credential/session compatibility APIs
├── security/    # HTTP security and redaction
├── telemetry/   # traces/metrics/observability
└── cli/         # create/dev/fabric/inspection operations
```

## Honest boundaries

Current architecture deliberately does **not** promise:

- Store replication/sync between nodes;
- shared multi-writer Store files;
- distributed consensus;
- global serializable transactions;
- global exactly-once execution;
- production PKI/OIDC/mTLS infrastructure;
- managed cloud/fleet control plane.

Store 0.2.2 also lacks arbitrary schedule-cursor repositioning and richer native
Python bindings for Topics/Streams and Objects. The Framework fails clearly or
uses stable compatibility boundaries instead of inventing unsupported behavior.

## Further reading

- `docs/runtime.md`
- `docs/data.md`
- `docs/workers.md`
- `docs/deployment.md`
- `docs/protocol.md`
- `docs/hitl.md`
- `docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`
