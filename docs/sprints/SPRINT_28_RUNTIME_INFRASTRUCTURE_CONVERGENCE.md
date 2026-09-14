# Sprint 28 — Runtime Infrastructure Convergence

**Status:** ACTIVE · started 2026-09-13  
**Current focus:** 28.8 — Execution / Workflow / HITL durability, with 28.9 Identity foundation pulled forward

## Purpose

Sprint 28 makes Voodoo's local-first promise operational across the Runtime.
Voodoo Store is the default durable application infrastructure, Voodoo Identity
becomes a first-class Runtime semantic, and a single-node application gains a path to
multiple Voodoo Nodes without changing application architecture.

> **Scaling a Voodoo application must change deployment topology, not application architecture.**

The default developer experience is:

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
Voodoo Store
      |
application.vstore
```

A fresh full Runtime does not silently fall back to SQLite. PostgreSQL, SQLite,
Redis, S3 and future providers remain explicit adapters for workloads that need them.

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

## Runtime ownership law

One process owns one Runtime Store handle.

```text
                         Process / Runtime
                                |
                         RuntimeStore owner
                                |
                    application.vstore
                                |
        +-----------+-----------+-----------+-----------+
        |           |           |           |           |
      Data        Queue       Events      Objects    Execution
        |           |           |           |           |
        +-----------+-----------+-----------+-----------+
                      SAME STORE / SAME WRITER
```

Infrastructure touched before an `App` lifespan uses a process-shared RuntimeStore.
When `App` starts, it adopts the compatible shared Store rather than opening a second
writer. A failed activation may leave an inert, unopened RuntimeStore registration;
that registration is replaceable on the next activation. An actually opened Store
with a conflicting configuration remains an error.

## Default infrastructure model

The zero-configuration path resolves to:

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

The developer normally does not need to write these blocks.

Explicit adapters remain possible:

```toml
[database]
provider = "postgres"

[queue]
provider = "redis"

[objects]
provider = "s3"
```

Adapters replace only the selected infrastructure domain. They do not replace Runtime
semantics or create another authority model.

## Store semantic mapping

```text
Voodoo Model / Data      -> Store Collections / indexes / transactions
Voodoo @task             -> Store Jobs / Queues
Voodoo Scheduler         -> Store schedules / Cron / Triggers
Voodoo events            -> Store durable event state; native Topics/Streams later
Voodoo ObjectStore       -> Store durable object state; native Objects binding later
Execution / HITL         -> Store durable Runtime state / journal / approvals
Runtime Identity         -> identity state persisted through Store
```

## Released Store dependency

Sprint 28 targets the released line:

```text
voodoo-store>=0.2.2,<0.3
```

`voodoo-store 0.2.2` is published to PyPI and contains the native Collections,
Jobs, Schedule, Cron and Trigger APIs required by the active Framework integration.
The old 0.1.1 Data/Model compatibility representation is no longer part of the
Store-first Framework path.

## Execution slices

| Slice | Goal | State |
|---|---|---|
| 28.1 | Store provider foundation and dependency/lifecycle boundary | **DONE** |
| 28.2 | Make Voodoo Store the zero-config default; demote legacy defaults to adapters | **DONE** |
| 28.3 | Data/Model -> Store Collections, indexes and transactions | **DONE** |
| 28.4 | `@task` / Jobs / Queues -> Store durable work | **DONE** |
| 28.5 | Scheduler / Cron / Triggers -> Store | **ACTIVE** |
| 28.6 | Events / Topics / Streams / Outbox -> Store | **DONE** for current Framework event contract |
| 28.7 | ObjectStore -> Store Objects | **DONE** for current Framework object contract |
| 28.8 | Execution / Workflow / HITL Runtime durability -> Store | **ACTIVE** |
| 28.9 | Voodoo Identity semantic foundation | **ACTIVE** (pulled forward) |
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

Implemented:

- Runtime-owned Store provider protocol and registry;
- `VoodooStoreProvider` with deterministic open/health/close lifecycle;
- `RuntimeStore` application lifecycle boundary;
- process-shared Store acquisition for infrastructure used before App startup;
- active Store binding for Runtime infrastructure adapters;
- safe adoption of the process-shared Store by `App`;
- safe replacement of an inert Store registration left by a failed startup;
- conflicting live writers remain rejected;
- native `voodoo_store` objects stay behind Runtime-owned adapters.

## 28.2 — Store as zero-config application infrastructure — DONE

Implemented:

- `voodoo-store>=0.2.2,<0.3` is a Framework base dependency;
- Store enabled by default at `.voodoo/application.vstore`;
- `database`, `queue`, `events` and `objects` default to `voodoo`;
- `App` resolves current configuration/environment when building the application;
- one Runtime Store is activated and shared across infrastructure domains;
- Store-disabled default Runtime startup fails explicitly rather than falling back to SQLite;
- SQLite/PostgreSQL/Redis/S3 remain explicit adapters.

## 28.3 — Data / Model -> Store — DONE

Implemented:

- public `Model` is Store-first unless an explicit SQL adapter is initialized;
- native Store Collections are required on the Store path;
- CRUD and fluent query ergonomics remain intact;
- native transactional record upsert is used for atomic id allocation + insert;
- no active 0.1.1 KV-row compatibility fallback;
- Model/Data shares the Runtime-owned Store.

## 28.4 — `@task` / Jobs / Queues -> Store — DONE

Implemented:

- canonical `VoodooStoreQueue` adapter;
- process-shared Store acquisition for standalone/direct queue use;
- workers reuse the Runtime Store and never open a competing `.vstore`;
- reversible 128-bit Store Job ID projection onto the public integer task ID surface;
- handler-filtered claims;
- heartbeat, lease ownership, completion, failure, release, expired-lease reclaim and manual retry;
- payload and trace metadata preserved;
- pending/retrying/running/completed/failed projections and list/stats;
- active-job idempotency and native Store retry semantics;
- worker queue cache is reset across Runtime lifecycles.

## 28.5 — Scheduler / Cron / Triggers -> Store — ACTIVE

Implemented:

- native Store one-shot and interval schedules;
- native Store Cron schedules;
- native Store trigger definitions/fire semantics;
- Runtime-owned `VoodooStoreScheduleStore`;
- Store-native ticks create durable Jobs without a second Framework enqueue;
- `TimeSpec`, create/get/list/pause/resume and SQLite compatibility surfaces retained;
- no implicit SQLite scheduler fallback.

Remaining contract gap:

- Store 0.2.2 can enable/disable an existing schedule but cannot reposition its current
  cursor. Therefore `resume(schedule_id, next_run_at=...)` explicitly refuses a
  different requested cursor instead of silently changing behavior. 28.5 remains
  ACTIVE until cursor repositioning is either added to Store or the public contract is
  deliberately revised.

## 28.6 — Events -> Store — DONE for current event contract

Implemented:

- `VoodooStoreEventBus` persists event envelopes in the Runtime-owned Store;
- deterministic sequence/order and replay;
- in-process subscribers preserve the public event API;
- no separate event database is required by default.

Store 0.2.x does not yet expose the richer Topics/Streams subsystem through the Python
binding. The Framework currently uses Store KV/transactions as its durable compatibility
boundary so application code will not change when native Topics/Streams replace it.

## 28.7 — ObjectStore -> Store — DONE for current object contract

Implemented:

- `VoodooStoreObjectStore` persists object bytes and metadata in the Runtime-owned Store;
- put/get/delete/exists/stat/list/checksum semantics;
- no mandatory S3/MinIO or parallel local metadata database on the default path.

The richer Store object subsystem is not yet exposed through the Python binding, so the
Framework currently uses Store KV/transactions behind the unchanged ObjectStore API.

## 28.8 — Execution / Workflow / HITL -> Store — ACTIVE

Implemented:

- `VoodooStoreExecutionStore` is the default execution persistence adapter;
- materialized execution state and append-only Runtime journal share `application.vstore`;
- artifacts share the same Store;
- HITL approvals share the same Store;
- execution persistence is detached from the global engine before RuntimeStore shutdown;
- SQLite and PostgreSQL execution stores are explicit choices only;
- lifecycle, save/load, timeline, artifacts and approval acceptance tests are present.

Current focus:

- converge the remaining Workflow/HITL durable semantics around the canonical Store-backed
  Execution lifecycle;
- remove any residual hidden SQLite durability in the default Runtime path;
- prepare cross-domain transaction boundaries for 28.11 without falsely claiming atomicity
  that Store/Framework do not yet expose.

## 28.9 — Identity foundation — ACTIVE

Identity remains a Runtime semantic:

```text
Identity
  +-- user
  +-- agent
  +-- service
  +-- device
  +-- node
       |
       v
Authentication evidence
       |
       v
Principal / Actor
       |
       v
Capability + Policy
       |
       v
Execution
```

Started:

- built-in `User` persistence follows the Store-first default instead of assuming SQLite;
- credential mechanisms remain separate from authority semantics;
- Store persists identity state but does not grant authorization.

## Current CI baseline

Head `abf27d8565bfb5bbd927ec45eb66ac333cf80027` established a clean Sprint 28 baseline:

- Ruff format: green;
- Ruff lint: green;
- declared mypy boundary: green;
- Python 3.12 full suite: **1525 passed**;
- Python 3.13 full suite: **1525 passed**;
- CodeQL: green.

The lifecycle regression exposed during convergence is now covered: a failed Store
activation cannot poison the next application startup with an inert conflicting Store.

## Transparent node scaling

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
- routing may consider capability, Policy, health, ownership and load;
- durable work has explicit ownership/lease semantics;
- governed reassignment occurs only where semantics permit it;
- Store files are node-local, never a network-filesystem coordination trick;
- application code remains topology-agnostic.

## Known remaining SQLite surface

The default application path is Store-first and no longer depends on SQLite. Edge/device
state still uses `SQLiteDeviceStore` when Edge is explicitly enabled. That is not part of
the default path, but Sprint 28 must converge it before claiming complete Store-only
operation for an Edge-enabled Runtime.

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
2. SQLite and external systems are explicit adapters rather than hidden defaults;
3. Data, work, scheduling, events, objects and Runtime durability have coherent Store-backed paths;
4. Identity is a first-class Runtime semantic spanning human, service, agent, device and node actors;
5. identity/authority converges through Capability + Policy + canonical Execution;
6. supported cross-domain state/work/outbox transactions have an explicit atomic boundary;
7. one-node applications remain zero-infrastructure and restart-safe;
8. authenticated Voodoo Nodes can join, advertise capability/health and route governed work without application rewrites;
9. distributed ownership/failover semantics are explicit and failure-tested;
10. external adapters remain supported through explicit configuration;
11. docs/examples teach Store-first and topology-transparent architecture;
12. Ruff, supported Python suites, security analysis, warning-zero gates and the declared Sprint 28 type boundary are green.

## Sprint statement

> **Sprint 28 turns Voodoo from a runtime that can use infrastructure into a runtime
> that provides its own coherent infrastructure by default — and can grow from one
> local node to a governed fabric without forcing the application to adopt distributed-
> systems complexity.**
