# Runtime Engine

> **Status:** Implemented and architecture-stabilized. Sprint 28 is converging
> durable infrastructure behind a Runtime-owned Voodoo Store provider boundary.

The Voodoo Runtime Engine is the unified execution model that makes the
computational model operational. Every meaningful operation — HTTP request,
agent run, task, workflow step, tool invocation, MCP call, worker job, human
approval, event handler or governed remote operation — is represented as an
**Execution** produced by a single `ExecutionEngine`.

## The Execution Lifecycle

```mermaid
flowchart LR
    Intent --> Capability
    Capability --> Policy
    Policy --> Execution
    Execution --> Compute
    Compute --> Effect
    Effect --> Observation
    Observation --> World
```

## Core Concepts

### Execution

An `Execution` is the universal durable/observable unit of meaningful work.
Internal helper calls do not become executions merely because they happen
inside Voodoo.

```python
from voodoo.runtime import Execution, ExecutionStatus
```

### ExecutionEngine

The `ExecutionEngine` (singleton: `engine`) drives the canonical lifecycle:

```python
from voodoo.runtime import execute
from voodoo.primitives import Intent

result = await execute(
    Intent("qualify_customer", customer_id=123),
    capabilities=["customers:read", "customers:write"],
)
```

### ExecutionContext

Every execution carries an `ExecutionContext` with identity/actor context,
trace and parent lineage, granted capabilities, deadlines and runtime state.
Capability and contextual Policy determine authority; network location or node
membership never grants authority by itself.

## Durable infrastructure — Sprint 28

Sprint 28 introduces a Runtime-owned Store boundary. The first slice deliberately
creates the lifecycle seam **before** switching legacy defaults.

```python
from voodoo.runtime import VoodooStoreProvider

store = VoodooStoreProvider(".voodoo/application.vstore")
store.open()
health = store.health()
store.close()
```

Application code is not expected to import `voodoo_store.Store` directly. The
native binding remains behind `voodoo.runtime` so later Data, Jobs, Events,
Objects, Identity and Execution durability adapters can depend on a stable
Voodoo semantic boundary instead of a binding implementation.

The target architecture is:

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Identity / Capability / Policy
    +-- Data / Jobs / Scheduler / Events / Objects
    +-- Execution / Workflow / HITL
    |
    v
Voodoo Store
    |
application.vstore
```

### Current transition state

During **Sprint 28.1**, existing SQLite/local/memory defaults remain operational
for compatibility. The Store lifecycle boundary is being established and tested
first. Sprint 28.2 is the explicit point where fresh zero-config applications
move to Voodoo Store as the default and SQLite/PostgreSQL/Redis/S3 become
explicit adapters.

This sequencing prevents a fake migration in which configuration says
"Voodoo Store" while subsystems still silently write to SQLite.

### Store provider contract

`StoreProvider` currently owns only provider-neutral lifecycle semantics:

- deterministic `open()` / `close()`;
- provider path and opened state;
- verification-backed health projection;
- lazy loading of the native Voodoo Store binding;
- normalization of binding failures into Voodoo errors.

It deliberately does **not** duplicate Data, Queue, Event or Execution
semantics. Those remain Runtime/framework concepts and receive Store-backed
adapters in later Sprint 28 slices.

### Binding coverage

The Voodoo Store Rust engine contains more capabilities than the current Python
0.1.x binding exposes. The integration therefore proceeds in parallel:

```text
voodoo Runtime contracts
        |
        +--> currently exposed Store lifecycle/KV/transactions
        |
        `--> typed binding expansion as later slices need
             Collections / Jobs / Queues / Scheduler / Streams /
             Objects / Workflow / Outbox
```

Voodoo must never claim a Store capability through Python until that capability
is actually exposed and contract-tested by the binding used by the framework.

## Checkpoints & Resume

Executions checkpoint at meaningful durability boundaries, including before
human waiting and after meaningful completed work. Recovery must restore runtime
truth without re-running already committed effects.

Existing execution persistence remains compatible during the Sprint 28
migration. Its durable representation will converge onto Store in slice 28.8.

## Transparent node scaling

Sprint 28 also establishes the infrastructure direction for topology-transparent
scaling:

> **Scaling a Voodoo application must change deployment topology, not
> application architecture.**

The initial model is node-local ownership, not shared-file storage:

```text
same application semantics
        |
        v
   Runtime Router
     /    |    \
 node-a node-b node-c
   |      |      |
 a.vstore b.vstore c.vstore
```

Multiple processes must not write the same `.vstore`. Authenticated Voodoo Nodes
will advertise identity, capability, health, load and ownership, while Runtime
routing preserves Capability + Policy + Execution semantics. Replication/sync,
distributed consensus and global exactly-once are separate future problems and
are not implied by this architecture.

## Configuration

Legacy provider configuration remains valid during the transition:

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
```

Sprint 28.2 will introduce the zero-config Store default while keeping these
providers available as explicit adapters. Compatibility is preserved until the
migration path is implemented and acceptance-tested.

## See Also

- [Sprint 28 — Runtime Infrastructure Convergence](sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)
- [Computational Model](primitives.md)
- [Human-in-the-Loop](hitl.md)
- [Planner & Adaptive Runtime](adaptive.md)
- [Architecture](architecture.md)
- [ROADMAP.md](../ROADMAP.md)
