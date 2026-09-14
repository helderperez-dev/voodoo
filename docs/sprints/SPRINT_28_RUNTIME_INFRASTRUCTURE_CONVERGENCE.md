# Sprint 28 — Runtime Infrastructure Convergence

**Status:** DONE · started 2026-09-13 · closed 2026-09-14  
**Validated feature head:** `0f03dc01ad21dac17a9fdbd40d762b087679e46f`  
**Validation:** CI #475 · CodeQL #443 · Python 3.12/3.13 · **1574 tests passed**

## Purpose

Sprint 28 makes Voodoo's local-first infrastructure model operational and gives the
same application semantics a governed path from one local Runtime to multiple Voodoo
Nodes.

> **Scaling a Voodoo application must change deployment topology, not application architecture.**

The one-node default is now:

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Identity / Capability / Policy
    +-- Data / Jobs / Scheduler / Events / Objects
    +-- Execution / Goal / Workflow / HITL
    +-- Edge / World / Agency
    |
    v
application.vstore
```

The multi-node model is:

```text
                         Application
                             |
                             v
                       Voodoo Runtime
                             |
          Identity -> Capability + Policy -> Execution
                             |
                       Runtime Fabric
                             |
              +--------------+--------------+
              |              |              |
            Node A         Node B         Node C
              |              |              |
          A.vstore       B.vstore       C.vstore
```

Each Store is node-local. Routing, ownership, health, placement and bounded failover
are Runtime semantics; Sprint 28 does not turn Store files into a distributed database.

## Architectural laws preserved

1. One Voodoo Runtime and one canonical `Execution` lifecycle.
2. Voodoo Store is the zero-configuration local durable provider.
3. Store owns durable mechanics; Runtime owns semantics, authority and intelligence.
4. Identity belongs to Runtime; persistence never grants authority.
5. SQLite/PostgreSQL/Redis/S3 remain explicit adapters.
6. Application APIs do not expose `voodoo_store` implementation types.
7. One-node applications require no mandatory external infrastructure.
8. Multi-node topology does not require application rewrites.
9. Distributed ownership precedes distributed storage/replication.
10. Remote work still enters Capability + Policy + canonical Execution.
11. Discovery, advertisements and placement never grant Capability.
12. No claims of distributed consensus, global exactly-once, globally serializable
    transactions or shared-file multi-writer semantics.

## Slice closure

| Slice | Goal | State |
|---|---|---|
| 28.1 | Runtime Store provider/lifecycle foundation | **DONE** |
| 28.2 | Voodoo Store as zero-config default | **DONE** |
| 28.3 | Data/Model -> Store Collections/indexes/transactions | **DONE** |
| 28.4 | Jobs/Queues -> Store native durable work | **DONE** |
| 28.5 | Scheduler/Cron/Triggers -> Store | **DONE** for released 0.2.2 contract |
| 28.6 | Events/Outbox -> Store | **DONE** for current public contract |
| 28.7 | ObjectStore -> Store | **DONE** for current public contract |
| 28.8 | Execution/Goal/Workflow/HITL durability | **DONE** |
| 28.9 | Runtime Identity foundation | **DONE** |
| 28.10 | Principal -> Capability -> Policy -> Execution | **DONE** |
| 28.11 | Local cross-domain transactions + durable outbox | **DONE** |
| 28.12 | Node Identity and authenticated membership | **DONE** |
| 28.13 | Node discovery, health and membership lifecycle | **DONE** |
| 28.14 | Transparent Runtime routing and ownership | **DONE** |
| 28.15 | Capability/policy/load/locality-aware placement | **DONE** |
| 28.16 | Failure detection, leases and bounded failover | **DONE** |
| 28.17 | Protocol convergence for node-fabric semantics | **DONE** |
| 28.18 | Explicit external-adapter compatibility | **DONE** |
| 28.19 | CLI/DX for Store/fabric operations | **DONE** |
| 28.20 | Store-first migration/compatibility strategy | **DONE** |
| 28.21 | Single-node zero-infrastructure acceptance | **DONE** |
| 28.22 | Multi-node topology-transparent acceptance | **DONE** |
| 28.23 | Edge closed-loop acceptance and sprint closure | **DONE** |

## Store-first runtime

The default configuration remains equivalent to:

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

`voodoo-store>=0.2.2,<0.3` is the released integration line used by this sprint.
There is no silent SQLite fallback when the default Store path is unavailable or lacks
required capabilities.

### Durable domains

```text
Model / Data            -> Collections / indexes / transactions
@task / Queue           -> Jobs / leases / retry / reclaim
Scheduler               -> Schedule / Cron / Trigger APIs
Events                  -> durable Store event state + replay
Runtime transactions    -> state/Collection + outbox in one local Store commit
Objects                 -> durable Store-backed ObjectStore contract
Execution               -> materialized state + journal + artifacts
Goal / Workflow         -> durable checkpoints and restart recovery
HITL                    -> durable approvals and post-restart resolution
Identity                -> Store-backed identity state
Edge                    -> devices/credentials/sessions/effects/replay state
```

Events and Objects use Store KV/transaction compatibility boundaries because the richer
Store Topics/Streams and Objects subsystems are not yet exposed by the 0.2.2 Python
binding. Their public Framework contracts remain stable for a later native binding swap.

### Scheduler capability boundary

Store 0.2.2 supports native schedule creation, Cron, triggers, enable/disable and ticks.
It does not expose repositioning an existing schedule cursor. Therefore
`resume(schedule_id, next_run_at=...)` rejects a different cursor explicitly. Sprint 28
closes 28.5 around the released Store capability rather than silently simulating a
semantic the Store does not provide.

## Identity and authority

```text
Identity (user/agent/service/device/node)
        |
AuthenticationEvidence
        |
Principal
        |
Capability + Policy
        |
canonical Execution
```

Authentication does not imply authorization. Roles/scopes and node-advertised
capabilities do not automatically become Runtime Capability grants.

## Runtime transactions and outbox

`RuntimeTransaction` defines the supported local atomic boundary:

```text
Collection/state mutation + Outbox intent
                  |
                  v
       one application.vstore commit
                  |
                  v
        at-least-once dispatcher
```

Jobs, arbitrary external effects and work on another node are not claimed to be inside
that transaction. Outbox messages retain stable IDs for idempotent consumers. A crash
after publication but before delivery acknowledgement may cause redelivery.

## Governed node fabric

Authenticated node Principals can join durable membership and advertise descriptive
placement metadata:

- Runtime version;
- capabilities available on the node;
- resources/load;
- services;
- location;
- Store ownership;
- metadata.

`RuntimeFabric` provides:

- ACTIVE-member discovery;
- stale-heartbeat transition to `SUSPECT`;
- capability/service/ownership filtering;
- load-aware placement;
- preferred-node, data-owner and locality preference;
- optional placement policy predicate;
- durable work leases with generations;
- explicit stable idempotency keys;
- bounded failover for work declared retryable;
- prohibition on reassignment when ambiguous physical/external work is declared
  `retryable=False`.

The fabric executor is deliberately a replaceable transport boundary. Receiving nodes
remain responsible for authentication and canonical Runtime authorization/execution.

## Protocol boundary

The public Protocol registry now includes transport-neutral schemas for:

- `NodeAdvertisement`;
- `NodeMembership`;
- `FabricWorkRequest`;
- `FabricWorkOutcome`.

They are JSON-Schema exportable and do not expose Python Runtime internals.

## Edge convergence

Edge no longer introduces a hidden SQLite database on the Store-first Runtime path.
`VoodooStoreDeviceStore` shares the Runtime-owned `application.vstore` for:

- devices;
- credentials;
- enrollments;
- sessions;
- durable effect deliveries;
- message replay/idempotency state;
- cached responses.

`SQLiteDeviceStore` remains available only as an explicit compatibility adapter.
Acceptance proves a device effect and its ACK survive Store/process restart.

## Explicit adapters and migration

Existing PostgreSQL, SQLite, Redis and S3 contract suites remain green. An explicit
provider override changes infrastructure mechanics for that domain; it does not create
another Identity, Capability, Policy or Execution model.

Migration is intentionally operator-controlled. Voodoo does not silently import legacy
production data during startup. See `docs/guides/STORE_FIRST_MIGRATION.md`.

Operational CLI added under `voodoo fabric`:

```text
status
health
verify
join
backup
```

`backup` is a verified cold-copy workflow: it acquires the Store writer lock rather
than presenting a live multi-writer file copy as safe.

## Acceptance evidence

### 28.21 — single node

Acceptance proves Collection state + local transaction + durable outbox + EventBus
survive restart using only `application.vstore` for the tested Runtime infrastructure.

### 28.22 — multiple nodes

Acceptance proves the same application operation is routed by Runtime placement to an
eligible node without application code selecting a node, transport or retry loop. The
receiving path still creates a canonical `Execution`.

### 28.23 — Edge closed loop

Acceptance proves Store-backed device/effect state, delivery claim, ACK and restart
recovery without a default SQLite Edge database.

## Validation baseline

Validated feature head `0f03dc01ad21dac17a9fdbd40d762b087679e46f`:

- CI #475: **success**;
- Ruff format/lint: **green**;
- declared mypy boundary: **green**;
- Python 3.12: **1574 passed**;
- Python 3.13: **green**;
- CodeQL #443: **success**.

The suite also keeps PostgreSQL, Redis, S3 and explicit SQLite compatibility contracts
green, so Store-first did not require deleting external-adapter support.

## Explicit post-Sprint-28 work

Sprint 28 intentionally leaves these for later work rather than overstating the fabric:

- Store replication/synchronization between node-local Stores;
- distributed consensus or globally serializable transactions;
- global exactly-once execution;
- production PKI/OIDC/mTLS identity infrastructure;
- generated multi-language SDKs;
- managed fleet/cloud scheduling/control plane;
- native Python bindings for Store Topics/Streams and Objects;
- Store schedule-cursor repositioning beyond the 0.2.2 capability;
- production transport implementations may evolve behind the `FabricExecutor` semantic boundary.

## Definition of Done — satisfied

Sprint 28 closes with:

1. Store-first zero-config local durability;
2. external systems demoted to explicit adapters;
3. coherent Store-backed Data/Work/Scheduler/Events/Objects/Execution/Identity/Edge paths;
4. first-class Runtime Identity and Principal semantics;
5. authority convergence through Capability + Policy + canonical Execution;
6. explicit local cross-domain transaction/outbox atomicity;
7. restart-safe one-node acceptance;
8. authenticated durable node membership;
9. health, ownership, placement, leases and bounded failover semantics;
10. language-neutral fabric Protocol schemas;
11. Store/fabric operational CLI and migration guidance;
12. topology-transparent multi-node and Edge closed-loop acceptance;
13. full supported CI/type/security gates green.

> **Sprint 28 turns Voodoo from a runtime that can use infrastructure into a runtime
> that provides coherent application infrastructure by default and can grow from one
> local node into a governed fabric without pushing distributed-systems complexity into
> application code.**
