# Sprint 28 — Runtime Infrastructure Convergence

**Status:** ACTIVE · started 2026-09-13  
**Current slice:** 28.5 — Scheduler / Cron / Triggers -> Store

## Purpose

Sprint 28 makes Voodoo's local-first promise operational across the Runtime.
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
SQLite, PostgreSQL, Redis, S3 and future providers remain supported, but they do not
define Voodoo's application architecture.

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
12. Voodoo must not claim distributed consensus, global exactly-once, or shared-file multi-writer semantics it does not implement.

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

The intended no-configuration path is:

```toml
[store]
provider = "voodoo"
path = ".voodoo/application.vstore"
```

The normal developer should not need to write that block.

Explicit domain adapters remain possible:

```toml
[database]
provider = "postgres"

[queue]
provider = "redis"

[objects]
provider = "s3"
```

Adapters replace only the selected infrastructure domain. They do not replace Runtime
semantics or create a second authority model.

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

Cross-domain transactions remain a strategic requirement. Where Store supports the
necessary primitives, Voodoo should atomically persist application state, durable work
and outbox effects instead of creating split-brain across separate infrastructure.

## Execution slices

| Slice | Goal | State |
|---|---|---|
| 28.1 | Store provider foundation and dependency/lifecycle boundary | **DONE** |
| 28.2 | Make Voodoo Store the zero-config default; demote legacy defaults to adapters | **DONE** |
| 28.3 | Data/Model -> Store Collections, indexes and transactions | **DONE** |
| 28.4 | `@task` / Jobs / Queues -> Store durable work | **DONE** |
| 28.5 | Scheduler / Cron / Triggers -> Store | **ACTIVE** |
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

## 28.1 — Store provider foundation — DONE

Implemented and accepted:

- Runtime-owned Store provider protocol and registry;
- `VoodooStoreProvider` and deterministic open/health/close lifecycle;
- `RuntimeStore` as the application-owned lifecycle boundary;
- active Runtime Store accessor for infrastructure adapters;
- environment/configuration boundary for provider/path/durability;
- native `voodoo_store` objects remain behind Runtime-owned adapters;
- contract/lifecycle tests cover optional import, errors and idempotent startup/shutdown.

## 28.2 — Store as zero-config application infrastructure — DONE

Implemented and accepted:

- framework depends on the currently published `voodoo-store` compatibility line;
- Store is enabled by default at `.voodoo/application.vstore`;
- one `App` lifecycle opens one application Store and closes it on shutdown;
- Data/Queue and later infrastructure domains reuse that Store instead of opening
  parallel `.vstore` files;
- explicit opt-out and external provider overrides remain possible;
- legacy domain adapters stay available while each domain converges deliberately.

The Store package is not republished automatically during Sprint development. New
native capabilities remain capability-gated until a compatible Store release is
explicitly authorized and published.

## 28.3 — Data / Model -> Store — DONE

Framework side:

- public `Model` is Store-first unless an explicit SQL adapter is initialized;
- existing CRUD and fluent query ergonomics remain intact;
- published Store 0.1.1 transactional-KV representation remains readable/writable;
- native Collections are detected when the newer binding is available;
- native records supersede legacy rows and rewritten records remove stale legacy copies;
- Model/Data uses the same application `RuntimeStore`.

Store side (`voodoo-store` Sprint 28 integration branch):

- native Collections metadata;
- secondary and unique indexes;
- record upsert/get/delete/scan and index lookup;
- transactional native record upsert alongside KV metadata;
- rollback and uniqueness acceptance coverage;
- Python binding coverage across supported CI platforms.

## 28.4 — `@task` / Jobs / Queues -> Store — DONE

Framework side:

- canonical `VoodooStoreQueue` adapter lives at `voodoo.storage.queue.store`;
- provider registry recognizes `queue.provider: voodoo`;
- worker runtime reuses the active application Store and never opens another `.vstore`;
- Store 128-bit Job IDs project reversibly onto the existing integer task API;
- handler-filtered claim preserves worker-type isolation;
- heartbeat, lease ownership, completion, failure, release, expired-lease reclaim and
  manual retry preserve the `VoodooQueue` contract;
- payload and trace metadata remain behind the existing public queue API;
- pending/retrying/running/completed/failed projections and list/stats are covered;
- Redis/memory queue resolution no longer initializes an unrelated SQL database.

Store side:

- durable submit/get/claim/complete/fail/cancel/history;
- handler-filtered claims;
- heartbeat / lease extension;
- explicit release and expired-lease recovery;
- manual retry, list and state statistics;
- priority, delay, deadlines, retry backoff and durable attempt counts;
- active-job idempotency: Ready/Leased work deduplicates, terminal work may reuse the key.

Acceptance evidence:

- Store Rust workspace green on Linux, macOS and Windows;
- Store Python package/binding green on Linux, macOS and Windows;
- Store MSRV 1.85, rustfmt and Clippy green;
- Framework Ruff, mypy, Python 3.12, Python 3.13 and CodeQL green;
- async SQLite compatibility adapters now have deterministic teardown so no aiosqlite
  worker survives its owning event loop.

## 28.5 — Scheduler / Cron / Triggers -> Store — ACTIVE

### Goal

Move durable temporal work from the SQLite-era pattern:

```text
claim/advance schedule -> return record -> enqueue separately
```

into Store-owned durable mechanics:

```text
schedule/cron/trigger -> Store tick/fire -> durable Job
```

The important semantic improvement is eliminating the failure window where a scheduler
advances its durable cursor but crashes before durable work is enqueued.

### Current implementation

The Store core already provides:

- one-shot and interval schedules backed by Jobs;
- durable cron schedules with occurrence-level idempotency;
- durable trigger definitions for manual/collection/stream/topic sources;
- atomic `fire_trigger()` that creates the Job and advances trigger metadata in one
  Store transaction.

The Sprint 28 Store Python binding is being expanded to expose:

- `create/get/set-enabled/tick` for one-shot and interval schedules;
- `create/get/list/set-enabled/tick` for cron schedules;
- `create/get/list/set-enabled/fire` for triggers;
- Python acceptance proving `schedule/cron/trigger -> Job -> claim` without Framework
  application code inside Store.

Before Framework activation, 28.5 must also preserve the existing scheduler contract:

- `TimeSpec` support;
- create/get/list/pause/resume semantics;
- explicit `next_run_at` resume behavior;
- compatibility with SQLite scheduler adapters;
- Store-backed ticking must not enqueue the same occurrence a second time through the
  Framework worker layer.

### 28.5 acceptance

28.5 is DONE only when:

1. the required Store scheduler/cron/trigger Python APIs are green across the Store CI matrix;
2. Framework has a Runtime-owned Store scheduler adapter with no `voodoo_store` leakage;
3. existing public schedule/TimeSpec behavior remains compatible;
4. Store-native ticks/fires create Jobs exactly once according to their documented semantics;
5. the App scheduler lifecycle reuses the same application RuntimeStore;
6. SQLite remains an explicit compatibility adapter;
7. Framework full Python 3.12/3.13, Ruff, mypy and CodeQL gates are green.

## Identity model

Sprint 28 will elevate identity above the existing auth helper surface:

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
credential mechanisms; they are not separate authority models.

## Transparent node scaling

A Voodoo Node is an authenticated Runtime participant with identity, health,
capabilities, load/resource information and ownership metadata.

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
- durable work has explicit ownership/lease semantics;
- failure may cause governed reassignment only when semantics permit it;
- Store files are node-local, never a network-filesystem coordination trick;
- application code remains topology-agnostic.

## Sprint 28 acceptance target

### Single node

```text
app -> Voodoo Runtime -> application.vstore
```

A canonical application must survive process restart with durable state/work/execution
semantics and require no mandatory PostgreSQL, Redis, RabbitMQ, Kafka, Celery, S3/MinIO
or external auth database.

### Multiple nodes

```text
same app semantics
      |
      +-- node-a -> node-a.vstore
      +-- node-b -> node-b.vstore
      `-- node-c -> node-c.vstore
```

Acceptance must prove authenticated membership, governed routing, ownership,
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
