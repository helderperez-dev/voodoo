# Runtime Engine Instructions

> Read before modifying `src/voodoo/runtime/`, canonical Execution, Identity,
> workflow/Goal durability, Store persistence, policy or Runtime Fabric.

## Canonical Execution law

`ExecutionEngine` is the one canonical mechanism for meaningful Runtime work.
Do not create subsystem-specific execution engines for agents, workers, devices
or remote nodes.

An Execution is appropriate when authorization, effects, durability/recovery,
resource accounting, waiting/HITL, retries or lineage matter. It is **not** every
helper call, render, state read or callback.

```python
from voodoo.primitives import Intent
from voodoo.runtime import engine


async def compute(ctx):
    return {"ok": True}


execution = await engine.execute(
    Intent(name="orders.reconcile"),
    compute,
    actor="service:orders",
)
```

Use the module-level `engine` in application/runtime integration. Fresh
`ExecutionEngine()` instances are appropriate in isolated tests.

## Lifecycle

The enforced lifecycle uses the statuses defined by `ExecutionStatus`, with
WAITING as the resumable HITL state and terminal states including completed,
failed, cancelled and timed out. Do not invent parallel lifecycle state machines.

## ExecutionContext

Context carries lineage and authority information including trace id, parent
execution id, actor, Principal, capabilities, intent, constraints/deadline and
engine reference.

Principal and actor are related but not identical:

- `Principal` is the authenticated Runtime identity/context;
- `actor` is the audit representation of who/what initiated work.

An explicit audit actor may override the default identity projection without
changing Capability grants.

## Identity and authority

```text
Identity
  ↓
AuthenticationEvidence
  ↓
Principal
  ↓
Capability + Policy
  ↓
Execution
```

Authentication, roles/scopes and node advertisements are not automatic grants.
Never authorize an effect merely because a caller is authenticated or claims a
role such as `admin`.

## Store-backed persistence

App startup attaches the Store-backed execution persistence adapter to the
canonical engine. Materialized Execution state, journal events, artifacts and
HITL approvals share the active RuntimeStore.

A Runtime component must **reuse** the Runtime-owned Store; it must not open a
second `application.vstore` writer.

During App shutdown, execution persistence is detached before the RuntimeStore
is stopped. Preserve that ordering to avoid stale closed Store handles across
application lifecycles.

## Checkpoint / recovery

`engine.checkpoint(execution)` persists a meaningful checkpoint when a store is
attached.

`engine.recover()` is synchronous and reloads unfinished persisted Executions.
It can rehydrate pending approvals when the attached execution store exposes
approval persistence.

```python
recovered = engine.recover()
```

Do **not** write `await engine.recover()` unless the API itself is deliberately
changed and all contracts are updated.

Recovery must not blindly replay already committed external effects. Use
checkpoints, participant registration and idempotency semantics appropriate to
the operation.

## HITL

Approval is a waiting state of canonical Execution. The Store-backed execution
adapter persists approval state; `recover()` rehydrates it after restart.

When implementing HITL changes:

- preserve the original waiting Execution;
- persist approval decisions/journal entries;
- resume through canonical Execution/child lineage;
- never create an independent human-workflow authority path.

## Workflow and Goal durability

Workflow orchestration checkpoints persist workflow progress/references to
canonical Execution ids; they do not duplicate the Execution truth.

Goal checkpoints have Store-backed persistence, but `GoalRuntime` is only
durable when a GoalStore is configured/passed according to its API. Do not claim
implicit Goal durability where no store is attached.

Resume semantics require explicit step identity/idempotency. Never claim a
workflow is restart-resumable without a test that closes/reopens the Store.

## Runtime transactions

`RuntimeTransaction` exposes the supported local atomic boundary:

- KV mutations;
- Collection upserts;
- durable `OutboxMessage` staging;
- one local Voodoo Store commit.

Outbox publication is at-least-once and occurs after commit. Another node,
external API, already executing job or physical Effect is outside this local
atomic boundary.

## Runtime Fabric

Fabric adds topology without adding another Runtime:

```text
Intent / requirement
       ↓
Runtime Fabric
       ↓
eligible ACTIVE node
       ↓
Capability + Policy
       ↓
canonical Execution
```

Membership/discovery/advertisement may influence placement, but does not grant
authority.

Leases/failover must be bounded. Only retry work on another node when semantics
allow retry. Non-retryable ambiguous physical/external work must not be
reissued automatically.

## Edge / World

Physical participants do not own their own ExecutionEngine. Device Effects and
observed evidence return through the same Runtime model:

```text
Execution → Effect → Device → ACK/Observation → World
```

World state changes from Observation/evidence, not merely from successful send.

## Capability / Policy rules

- register/resolve capabilities explicitly;
- preserve sensitive default-deny behavior;
- Policy evaluates contextual authority; it must not be bypassed by routing;
- child/delegated contexts may narrow authority but must not silently widen it;
- authentication evidence and advertised node capabilities are not grants.

## Errors

Use specific Runtime error types and preserve execution/trace context. Broad
exception conversion must not swallow underlying failure semantics.

## Adding Runtime behavior

1. Identify which existing Runtime concept owns the behavior.
2. Keep one canonical Execution path.
3. If durable, use RuntimeStore/Store-backed provider or an explicit adapter.
4. Preserve identity → capability → policy authority flow.
5. Add checkpoint/restart tests for durability claims.
6. Add failure/idempotency tests for retry/failover claims.
7. Update inspection/CLI where users need operational visibility.
8. Update `docs/runtime.md`, architecture docs and relevant instruction files.

## Testing requirements

Use fresh engine instances in unit tests. For integration/App tests, verify the
module-level engine lifecycle. Persistence acceptance tests must close and
reopen the actual Store when claiming restart safety.

Do not make tests pass by restoring SQLite defaults, weakening Capability/Policy
checks, bypassing canonical Execution, or swallowing Store lifecycle errors.
