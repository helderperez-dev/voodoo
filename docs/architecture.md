# Architecture

Voodoo is a programmable Runtime for adaptive applications and operational
systems. Web, APIs, agents, workers, human workflows, remote nodes and physical
devices are different participants around one Runtime — not independent stacks
with separate authority and execution semantics.

## North-star loop

```text
World → Observation → Goal → Intent → Plan
      → Capability + Policy
      → Execution → Effect → Participant
      → ACK / Observation → World
```

Two laws follow from this:

1. **AI is Compute, not authority.**
2. **Effect is not Observation.** Attempting an action does not make it true.

## Runtime convergence

```text
                         Application
                             |
                             v
                       Voodoo Runtime
                             |
        +--------------------+--------------------+
        |                    |                    |
     Identity              Agency               World
        |                    |                    |
        +----------- Capability + Policy ---------+
                             |
                             v
                     canonical Execution
                             |
        +--------------------+--------------------+
        |         |          |         |          |
      Data      Work      Events    Objects    Workflow
        |         |          |         |          |
        +--------------------+--------------------+
                             |
                             v
                        RuntimeStore
                             |
                             v
                  .voodoo/application.vstore
```

Voodoo Store is the default durable infrastructure substrate for a fresh app.
SQLite, PostgreSQL, Redis and S3-compatible storage are explicit adapters.

## Core concepts

### Identity

Anything that acts is identified as a user, agent, service, device or node.
Authentication evidence proves identity; it does not grant Runtime authority.

```text
Identity → AuthenticationEvidence → Principal
                                      |
                                      v
                             Capability + Policy
                                      |
                                      v
                                  Execution
```

### Intent

Intent expresses the desired outcome. It does not select a host, database
connection, transport or specific device driver.

### Capability

Capability expresses ability/authority to produce an effect. Policy adds
contextual rules about whether that authority may be exercised now.

### Execution

`Execution` is the canonical durable/observable lifecycle for meaningful work:

```text
created → planned → authorized → running → waiting
                                  |          |
                                  |          +→ running (resume)
                                  v
                        completed / failed / cancelled / timed_out
```

Do not create Executions for every helper call. Create them for work where
authorization, effects, durability, recovery, accounting, waiting or lineage
matters.

### Effect and Observation

Effects describe attempted changes. Observations describe evidence about
reality. World state is updated from observations, not optimistic assumptions
that an external participant obeyed a command.

## Store-first local Runtime

A fresh app normally needs no infrastructure configuration:

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

These are effective defaults; users normally do not write them.

### What shares the Store

- `Model`/Data Collections;
- Jobs and durable Queue state;
- Schedule/Cron/Trigger state;
- durable Events/replay compatibility state;
- Object bytes/metadata compatibility state;
- canonical Execution state and journal;
- Workflow and Goal checkpoints;
- HITL approvals;
- built-in Identity persistence;
- Edge device/session/effect/replay state.

### Runtime ownership

One process owns one RuntimeStore writer. Subsystems reuse that handle; they do
not each open their own `.vstore`.

```text
Process
  |
  `-- RuntimeStore
        |
        `-- application.vstore
              +-- Data
              +-- Queue
              +-- Events
              +-- Objects
              +-- Execution
              +-- Identity
              `-- Edge
```

## Local transaction boundary

`RuntimeTransaction` exposes provider-neutral atomicity over the capabilities
Voodoo Store can actually commit together: KV/Collection mutations and an
Outbox record.

```text
state mutation + outbox message
             |
             v
       one local commit
```

Outbox publication happens after commit and is at-least-once. Message ids are
stable idempotency keys. Voodoo does not call an external API part of the same
local transaction.

## Workers and scheduling

Queued jobs are durable Store Jobs. Claims use explicit leases; workers
heartbeat ownership, complete/fail/release jobs and reclaim expired leases.
Each application attempt executes through the canonical `ExecutionEngine`.

Schedules/Cron/Triggers are Store-backed on the default path. Store 0.2.2 can
enable/disable existing schedules but cannot arbitrarily reposition a schedule
cursor; Voodoo fails clearly for that unsupported operation.

## Events and objects

Events and objects use Store-backed compatibility boundaries behind stable
Framework APIs. Voodoo Store 0.2.2 does not yet expose the richer native
Topics/Streams and Object subsystems through its Python binding, so the
Framework does not pretend those bindings exist.

## Workflow, Goals and HITL

Durability is checkpoint-oriented:

- Execution state/journal persists;
- Workflow orchestration checkpoints reference canonical Execution ids;
- Goal checkpoints can use Voodoo Store;
- HITL approvals persist and are rehydrated after restart.

Resume semantics must respect already committed effects and idempotency. Voodoo
does not equate persistence with global exactly-once execution.

## Runtime Fabric

The same app semantics can grow into multiple Voodoo Nodes:

```text
Application semantics
        |
        v
  Runtime Fabric
   /    |    \
Node A Node B Node C
  |      |      |
A.vstore B.vstore C.vstore
```

### Node membership

Authenticated node Principals join durable membership and advertise metadata:

- Runtime version;
- capabilities they can service;
- resources/load;
- services;
- location;
- Store/data ownership.

Advertisements support discovery/placement; they do not grant Capability.

### Routing and placement

Routing can filter/score by:

- member health;
- required capability/service;
- data ownership;
- preferred node;
- load/resource metadata;
- locality.

The selected remote operation still passes Capability + Policy + canonical
Execution at the destination boundary.

### Leases and failover

Distributed work has lease generation/idempotency state. Failover is bounded:
retryable work may be reassigned according to policy; ambiguous physical or
external work can be declared non-retryable to avoid blindly repeating an
effect.

## Protocol

Node advertisements, memberships, fabric work requests/outcomes and existing
remote Execution semantics have transport-neutral models under
`voodoo.protocol`. HTTP, WebSocket, MQTT, QUIC or another transport can carry
those contracts without changing Runtime authority.

## Edge

Physical/external devices use the same Runtime semantics:

```text
Device → Observation → World
                     → Goal / Intent
                     → Capability + Policy
                     → Execution → Effect → Device
                     → ACK / Observation → World
```

The default Edge device store is Store-backed and shares the application
RuntimeStore. `SQLiteDeviceStore` remains available as an explicit adapter.

## Deployment topology

Store-first local deployment obeys:

> **one process = one Voodoo Node = one local Store writer**

Do not use multiple uvicorn/gunicorn worker processes against the same
`.vstore`. Scale by creating separate nodes with separate local Stores.

Store replication/sync is a future layer; shared network-file Store writes are
not a substitute.

## External adapters

Voodoo supports explicit domain overrides where needed:

```text
Database -> PostgreSQL / SQLite
Queue    -> Redis / PostgreSQL / compatibility adapters
Objects  -> S3-compatible storage
Cache    -> memory / Redis
Telemetry-> OpenTelemetry
```

Adapters change infrastructure mechanics, not Runtime meaning or authority.

## What Voodoo does not claim yet

- automatic Store replication/sync;
- shared multi-writer `.vstore` files;
- distributed consensus;
- globally serializable cross-node transactions;
- global exactly-once execution;
- production PKI/OIDC/mTLS identity infrastructure;
- managed cloud/fleet control plane.

## Public API ownership

```python
from voodoo import App, Agent, Model, page, state, task, tool
from voodoo.ui import Button, Card, DataTable
from voodoo.runtime import ExecutionEngine, Goal, GoalRuntime, Planner
from voodoo.world import Entity, Observation, WorldModel
from voodoo.edge import DeviceGateway, WorldAwareDeviceGateway
from voodoo.protocol import WorldSnapshot, RemoteExecutionRequest
```

Concepts should live in the namespace that owns them; the 2.x package root is a
compatibility facade while 3.0 import law is stabilized.

## Further reading

- `ARCHITECTURE.md`
- `docs/runtime.md`
- `docs/data.md`
- `docs/workers.md`
- `docs/deployment.md`
- `docs/protocol.md`
- `docs/hitl.md`
- `docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`
