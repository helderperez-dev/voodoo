# Runtime Engine

> **Status:** Store-first Runtime infrastructure convergence is complete on this branch.

The Voodoo Runtime Engine is the unified execution model that makes the
computational model operational. Meaningful work converges on one canonical
`ExecutionEngine`; persistence and infrastructure converge on one Runtime-owned
Voodoo Store by default.

## Execution lifecycle

```text
Observation / Goal
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

AI is one form of Compute. Node membership, authentication and network location
do not create authority by themselves.

## Store-first Runtime

A fresh application uses:

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Model / Data
    +-- Jobs / Queue
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

The framework depends on `voodoo-store>=0.3.0,<0.4`. Application
code should not import native `voodoo_store` objects for normal Runtime use;
Store implementation details remain behind Voodoo-owned contracts.

## Runtime Store ownership

One process owns one Store handle:

```text
Process / Runtime
       |
       v
 RuntimeStore
       |
       v
application.vstore
```

Infrastructure touched before `App` startup acquires the process-shared
RuntimeStore. App startup adopts that compatible handle rather than opening a
second writer. A live Store with a conflicting configuration is rejected.

This is a single-writer law, not a limitation Voodoo tries to hide. Multiple
processes must not write the same `.vstore` file.

## Execution

An `Execution` is meaningful work worth observing, authorizing, recovering,
accounting for, waiting on, or reasoning about. Internal helper calls do not
become executions merely because they occur inside Voodoo.

```python
from voodoo.primitives import Intent
from voodoo.runtime import ExecutionEngine

engine = ExecutionEngine()


async def compute(ctx):
    return {"ok": True}


execution = await engine.execute(
    Intent(name="customer.refresh"),
    compute,
    actor="service:crm",
)
```

App startup attaches the Store-backed execution persistence adapter to the
canonical engine. Execution materialized state, journal events, artifacts and
HITL approvals share the Runtime Store.

## Identity and authority

Runtime Identity is separate from authentication evidence and authority:

```text
Identity
   |
AuthenticationEvidence
   |
Principal
   |
Capability + Policy
   |
Execution
```

Supported identity kinds include user, agent, service, device and node.
Authentication, roles/scopes or node advertisements do **not** automatically
grant Runtime Capability.

## Durable workflows, Goals and HITL

- execution checkpoints survive Store restart;
- Goal checkpoints have a Store-backed provider;
- Workflow orchestration checkpoints persist references to canonical
  Executions rather than creating a second execution truth;
- HITL approvals persist and can be rehydrated by `ExecutionEngine.recover()`
  after restart.

Durability does not mean global exactly-once. External effects still require
idempotency and domain-appropriate recovery semantics.

## Runtime transactions and outbox

The supported local atomic boundary is explicit:

```python
from voodoo.runtime import OutboxMessage, transaction

with transaction() as tx:
    tx.upsert_record(
        b"orders",
        b"42",
        b'{"status":"created"}',
    )
    tx.stage_outbox(
        OutboxMessage(
            id="order-42-created",
            topic="order.created",
            payload={"order_id": "42"},
        )
    )
```

The Collection/KV mutation and outbox insertion commit atomically in one local
Store transaction. Outbox delivery is at-least-once; consumers should use the
message id as an idempotency key where duplicate suppression matters.

Jobs, arbitrary external effects, and operations on another node are not
claimed to be part of this local transaction.

## Transparent node scaling

> **Scaling a Voodoo application changes deployment topology, not application architecture.**

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

The Runtime Fabric provides:

- authenticated node Principals;
- durable membership and heartbeat lifecycle;
- health-aware discovery;
- capability/service/ownership filtering;
- load/locality/data-owner aware placement;
- durable lease generations;
- bounded failover for work explicitly declared retryable;
- stable idempotency keys across attempts.

A node advertising a capability is not the same as being authorized to use it.
Remote work still enters Capability + Policy + canonical Execution.

## Protocol boundary

Node advertisement, membership and fabric work request/outcome semantics are
represented in transport-neutral Protocol models. The transport may evolve
without changing Runtime authority or Execution semantics.

## Edge

When Edge is enabled, device/credential/session/effect/replay state uses the
same Runtime Store by default. `SQLiteDeviceStore` remains an explicit adapter,
not a hidden Edge default.

## Configuration

A fresh Runtime is equivalent to:

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

Those blocks normally do not need to be written. PostgreSQL, SQLite, Redis and
S3 are explicit domain overrides.

## Current honest boundaries

Voodoo does not currently claim:

- shared-file multi-writer Store semantics;
- Store replication/sync between node-local Stores;
- distributed consensus;
- globally serializable transactions;
- global exactly-once execution;
- production PKI/OIDC/mTLS identity infrastructure;
- a managed cloud/fleet control plane.

Store 0.3 exposes the richer native Topics/Streams and Objects subsystems
through its Python binding; the Events and ObjectStore adapters use those native
surfaces behind stable Framework APIs. Store 0.3 still does not expose arbitrary
schedule cursor repositioning, and the Framework fails clearly for that
unsupported operation instead of pretending the binding supports it.

## See also

- [Sprint 28 closure](sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)
- [Architecture](architecture.md)
- [Data & Models](data.md)
- [Workers](workers.md)
- [Deployment](deployment.md)
- [Human-in-the-Loop](hitl.md)
- [Protocol](protocol.md)
