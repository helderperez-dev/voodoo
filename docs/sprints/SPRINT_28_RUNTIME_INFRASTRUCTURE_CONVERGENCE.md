# Sprint 28 — Runtime Infrastructure Convergence

**Status:** ACTIVE · started 2026-09-13

## Purpose

Sprint 28 makes Voodoo's local-first promise operational across the whole runtime.
Voodoo Store becomes the default durable application infrastructure, Voodoo Identity
becomes a first-class Runtime semantic, and a single-node application gains a path to
multiple Voodoo Nodes without changing application architecture.

> **Scaling a Voodoo application must change deployment topology, not application architecture.**

The target developer experience is:

```text
Voodoo application
      |
      v
Voodoo Runtime
      |
      +-- Identity / Capability / Policy
      +-- Data / Work / Events / Objects
      +-- Execution / Workflow / HITL
      +-- World / Agency / Edge / Mesh
      |
      v
Voodoo Store (default)
      |
application.vstore
```

External systems remain explicit adapters for workloads that genuinely need them.
SQLite is no longer the default database/runtime persistence choice; SQLite,
PostgreSQL, Redis, S3 and future providers are optional adapters behind Voodoo
semantics.

## Architectural laws

1. There is exactly one Voodoo Runtime and one canonical `Execution` lifecycle.
2. Voodoo Store is the default local-first durable infrastructure provider.
3. Store owns durable mechanics; Runtime owns application semantics, authority and intelligence.
4. Identity belongs to Runtime. Store may persist identity state but never defines authorization semantics.
5. SQLite/PostgreSQL/Redis/S3/etc. are adapters, not architectural requirements.
6. Application APIs must not leak `voodoo_store` implementation details.
7. A one-node application must work with no mandatory external infrastructure.
8. Adding Voodoo Nodes must not require rewriting application code.
9. Distributed ownership precedes distributed storage: each Store remains locally owned until replication/sync is explicitly designed.
10. Remote work still enters Capability + Policy + canonical Execution before effects occur.
11. Node discovery/routing never grants authority by itself.
12. Voodoo must not claim distributed consensus, global exactly-once, or shared-file multi-writer semantics that it does not implement.

## Target topology

```text
                         Application
                             |
                             v
                       Voodoo Runtime
                             |
          +------------------+------------------+
          |                  |                  |
       Identity            Agency             World
          |                  |                  |
          +---------- Capability + Policy ------+
                             |
                             v
                         Execution
                             |
                             v
                       Runtime Router
                             |
                 +-----------+-----------+
                 |           |           |
               Node A      Node B      Node C
                 |           |           |
              A.vstore    B.vstore    C.vstore
                 |           |           |
                 +-------- Voodoo Mesh --------+
                             |
                             v
                        Edge / Devices
```

The first implementation does **not** make multiple processes write the same `.vstore`.
Multi-node operation uses node-local ownership and governed Runtime routing.

## Default infrastructure model

Current fragmented defaults (`sqlite`, `local`, `memory`) converge behind a Store
provider. The intended no-configuration path is conceptually:

```toml
[store]
provider = "voodoo"
path = ".voodoo/application.vstore"
```

The normal developer should not need to write that block.

Explicit adapters remain possible, for example:

```toml
[database]
provider = "postgres"

[queue]
provider = "redis"

[objects]
provider = "s3"
```

Adapters replace only the domain selected by the application/operator; they do not
replace Runtime semantics.

## Store semantic mapping

```text
Voodoo Model / Data      -> Store Collections / indexes / transactions
Voodoo @task             -> Store Jobs / Queues
Voodoo Scheduler         -> Store schedules / Cron / Triggers
Voodoo events            -> Store Topics / Streams / Outbox
Voodoo ObjectStore       -> Store Objects
Execution / HITL         -> Store Workflow / durable Runtime state
Runtime Identity         -> identity state persisted through Store
```

Cross-domain transactions are a strategic requirement. Where Store supports the
necessary primitives, Voodoo should be able to atomically persist application state,
enqueue durable work and emit an outbox event rather than create split-brain across a
database, broker and event system.

## Identity model

Sprint 28 elevates identity above the existing auth helper surface.

Canonical semantic direction:

```text
Identity
  |
  +-- Human / User
  +-- Agent
  +-- Service
  +-- Device
  +-- Node / Runtime participant
  |
  v
Authentication / credential evidence
  |
  v
Principal / Actor
  |
  v
Capability
  |
  v
Contextual Policy
  |
  v
Execution
```

Password, JWT, API key, OAuth/OIDC, device credentials and future mTLS/PKI are
credential/authentication mechanisms; they are not separate authority models.

Production PKI/OIDC/mTLS infrastructure remains allowed to mature incrementally, but
Sprint 28 must establish the unified Runtime identity contracts and make existing
local auth fit them.

## Transparent node scaling

A Voodoo Node is an authenticated Runtime participant with identity, health,
capabilities, load/resource information and ownership metadata.

The intended progression is:

```text
Phase 1: Runtime + application.vstore
Phase 2: multiple Voodoo Nodes + node-local stores + Runtime routing
Phase 3: Store replication/sync when explicitly designed
Phase 4: larger managed/fleet/cloud fabrics
```

Initial multi-node laws:

- nodes discover/join a governed Runtime fabric;
- node identity is authenticated;
- membership never implies capability;
- routing can consider capability, Policy, health, ownership and load;
- durable work has an explicit owner/lease;
- failure may cause governed reassignment only when semantics permit it;
- Store files are node-local, never a network-filesystem coordination trick;
- application code remains topology-agnostic.

## Execution slices

| Slice | Goal | State |
|---|---|---|
| 28.1 | Store provider foundation and dependency/lifecycle boundary | **ACTIVE** |
| 28.2 | Make Voodoo Store the zero-config default; demote legacy defaults to adapters | TODO |
| 28.3 | Data/Model -> Store Collections, indexes and transactions | TODO |
| 28.4 | `@task` / Jobs / Queues -> Store durable work | TODO |
| 28.5 | Scheduler / Cron / Triggers -> Store | TODO |
| 28.6 | Events / Topics / Streams / Outbox -> Store | TODO |
| 28.7 | ObjectStore -> Store Objects | TODO |
| 28.8 | Execution / Workflow / HITL Runtime durability -> Store | TODO |
| 28.9 | Voodoo Identity semantic foundation | TODO |
| 28.10 | Identity -> Principal/Actor -> Capability -> Policy convergence | TODO |
| 28.11 | Unified cross-domain Runtime transactions | TODO |
| 28.12 | Node Identity and authenticated membership | TODO |
| 28.13 | Node discovery, health and membership lifecycle | TODO |
| 28.14 | Transparent Runtime routing and distributed ownership | TODO |
| 28.15 | Capability/Policy-aware and load-aware placement | TODO |
| 28.16 | Failure detection, leases, recovery and bounded failover | TODO |
| 28.17 | Mesh/Protocol convergence for node fabric semantics | TODO |
| 28.18 | External adapter compatibility and explicit override rules | TODO |
| 28.19 | CLI/DX: create/dev/inspect/health/verify/backup/join | TODO |
| 28.20 | Legacy SQLite/default migration and compatibility strategy | TODO |
| 28.21 | Single-node zero-infrastructure acceptance | TODO |
| 28.22 | Multi-node topology-transparent acceptance | TODO |
| 28.23 | Edge/distributed closed-loop acceptance and sprint closure | TODO |

## 28.1 — Store provider foundation

**Status: ACTIVE**

First implementation work:

1. audit existing provider registries and every implicit SQLite/local/memory default;
2. audit the currently published `voodoo-store` Python API rather than assuming Rust-core coverage is exposed;
3. define a Runtime-owned Store/provider protocol that does not leak native binding classes;
4. add Store configuration and lifecycle (`open`, health, close) semantics;
5. establish optional-import/error behavior so compatibility adapters remain usable;
6. add contract tests before changing existing defaults.

Acceptance for 28.1:

- Voodoo can resolve a Store provider through a Runtime-owned abstraction;
- lifecycle is deterministic and test-covered;
- importing Voodoo does not require application code to import `voodoo_store` directly;
- no legacy provider is removed before an adapter/migration path exists;
- the abstraction is broad enough for later Data/Work/Event/Object/Runtime slices without becoming a second Runtime.

## Acceptance target for Sprint 28

A canonical application must demonstrate both forms without changing its application
architecture:

### Single node

```text
app -> Voodoo Runtime -> application.vstore
```

It must survive process restart with durable state/work/execution semantics and require
no mandatory PostgreSQL, Redis, RabbitMQ, Kafka, Celery, S3/MinIO or external auth
database.

### Multiple nodes

```text
same app semantics
      |
      +-- node-a -> node-a.vstore
      +-- node-b -> node-b.vstore
      `-- node-c -> node-c.vstore
```

The acceptance must prove authenticated membership, governed routing, ownership,
capability/policy enforcement, health/failure behavior and a closed-loop execution
without application code becoming topology-aware.

## Explicit non-goals

Sprint 28 does not promise:

- shared multi-writer `.vstore` files;
- distributed consensus;
- globally serializable transactions across nodes;
- global exactly-once execution;
- automatic Store replication before its protocol is designed and tested;
- a production Voodoo Cloud control plane;
- unconstrained autonomous placement that bypasses Capability or Policy.

## Definition of Done

Sprint 28 is done only when:

1. Voodoo Store is the default durable provider for a fresh Voodoo application;
2. SQLite and other legacy/external systems are explicit adapters rather than hidden defaults;
3. Data, durable work, scheduling, events, objects and Runtime durability have a coherent Store-backed path;
4. Identity is a first-class Runtime semantic spanning human, service, agent, device and node actors;
5. identity/authority converges through Capability + Policy + canonical Execution;
6. one Store-backed transaction can cover the supported state/work/outbox boundary;
7. one-node applications remain zero-infrastructure and restart-safe;
8. multiple authenticated Voodoo Nodes can join, advertise capability/health and route governed work without changing application code;
9. distributed ownership/failover semantics are explicit and failure-tested;
10. external adapters remain supported through explicit configuration;
11. docs/examples teach Store-first and topology-transparent architecture;
12. Ruff, supported Python suites, security analysis, warning-zero gates and the declared Sprint 28 type boundary are green.

## Sprint statement

> **Sprint 28 turns Voodoo from a runtime that can use infrastructure into a runtime
> that provides its own coherent infrastructure by default — and can grow from one
> local node to a governed fabric without forcing the application to adopt distributed-
> systems complexity.**
