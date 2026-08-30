# Runtime Contract — v2.5.2

> **Status:** Architecture Freeze
> **Date:** 2026-03-15
> **Purpose:** Definitive semantics of the Voodoo runtime core primitives.
> After this document is accepted, treat the runtime core as frozen.

---

## What is Voodoo?

**Voodoo is a durable execution runtime for building adaptive applications
and autonomous operational systems.**

Web applications, APIs, agents, background workers, realtime systems, MCP
tools, human workflows, distributed systems, and physical systems are
different manifestations of one runtime that converge on **Execution**.

---

## Core Primitives

### Entity

**An Entity is anything that can be identified and hold state.**

Entities are conceptual — there is no `Entity` class. Users, agents, orders,
devices, and robots are all entities. They are represented through State,
Identity, and their participation in Executions.

- **Identity** — stable identifier (`id`, `kind`, `owner`)
- **State** — mutable, versioned, checkpointable
- **Capabilities** — what the entity is allowed to do
- **Relationships** — links to other entities
- **Intents** — what the entity wants to achieve
- **Executions** — what the entity has done

### State

**State is the durable system truth.**

```python
from voodoo.primitives import State

state = State(entity_id="user:42", data={"name": "Alice"})
```

- Versioned — every mutation increments the version
- Mutable — changes through Effects
- Checkpointable — snapshots at meaningful boundaries
- Reactive — UI cells subscribe to state changes

### Intent

**Intent is a named desire to produce an effect.**

```python
from voodoo.primitives import Intent

intent = Intent("qualify_customer", customer_id=123)
```

- Named — human-readable purpose
- Payload — structured data for the execution
- Resolved — maps to a Capability via the resolver

### Capability

**Capability is the ability and authorization to produce an effect.**

```python
from voodoo.primitives import Capability

cap = Capability(name="customers:write", scope="tenant:acme")
```

- Explicit — no ambient authority
- Scoped — limited to a context (tenant, user, time)
- Delegatable — can be transferred to another entity
- Revocable — can be withdrawn
- Time-limited — can expire

Sensitive capabilities are denied by default:
`filesystem.write`, `network.request`, `shell.execute`, `secrets.read`,
`payment.execute`, `email.send`.

### Execution

**Execution is the central runtime mechanism — every meaningful operation
is one.**

```python
from voodoo.runtime import Execution, ExecutionStatus

# 9 implemented states:
# created → authorized → running → completed
# planned     waiting      failed
# cancelled   timed_out
```

- First-class — persisted, queryable, recoverable
- Lifecycle — 9 states, 18 validated transitions
- Parent/child — tool calls nest inside agent runs
- Identity — `id`, `parent_execution_id`, `trace_id`
- Journal — append-only event log

### Compute

**Compute is how an execution is performed.**

AI is one form of Compute — never a fundamental primitive.

```python
from voodoo.primitives import ComputeParticipant

ai = ComputeParticipant(name="gpt-4", kind="ai", capabilities=["reason"])
tool = ComputeParticipant(name="search", kind="tool", capabilities=["net.fetch"])
human = ComputeParticipant(name="approver", kind="human", capabilities=["approve"])
```

Compute participants:
- **AI** — language models, embeddings, classifiers
- **Tool** — functions, APIs, services
- **Human** — approvals, decisions, input
- **Worker** — background tasks, queues
- **Device** — robots, sensors, actuators

### Effect

**Effect is a change produced by an execution.**

```python
from voodoo.primitives import Effect, EffectStatus

effect = Effect(
    name="send_email",
    intent_id=intent.id,
    idempotency_key="email-123",
)
```

- Named — what happened
- Idempotent — carries `idempotency_key` for deduplication
- Lifecycle — PENDING → EXECUTING → SUCCEEDED | FAILED | ROLLED_BACK
- Reversible — can be compensated (if marked reversible)
- Recorded — persisted on the execution

### Time

**Time governs the lifecycle and validity of an execution.**

- Deadlines — absolute cutoff
- Timeouts — relative duration
- Retry policies — backoff, max attempts
- Schedules — cron-like recurring execution

### Resource

**Resource is something required or consumed by an execution.**

- Cost — monetary
- Tokens — AI model tokens
- Energy — compute cycles
- Storage — bytes

Resources are tracked against a budget via the ResourceAccountant.

### Constraint

**Constraint is a condition that must hold.**

- Guards — preconditions
- Invariants — must hold during execution
- Policies — business rules
- Rate limits — throughput constraints

A violated constraint fails or pauses the execution.

---

## Execution Lifecycle

### States (9 implemented)

```text
Created → Authorized → Running → Completed
Planned     Waiting      Failed
Cancelled   Timed Out
```

### Transitions (18 validated)

| From | To | Trigger |
|---|---|---|
| `created` | `authorized` | Engine authorizes capability |
| `created` | `planned` | Planner resolves participants |
| `created` | `running` | Direct start (test/recovery) |
| `created` | `waiting` | Direct wait (test/recovery) |
| `created` | `completed` | Skipped task |
| `created` | `failed` | Validation failure |
| `created` | `cancelled` | Cancelled before start |
| `planned` | `authorized` | Capability resolution allows |
| `planned` | `running` | Direct start |
| `planned` | `failed` | Planning failure |
| `planned` | `cancelled` | Cancelled during planning |
| `authorized` | `running` | Compute begins |
| `authorized` | `failed` | Authorization failure |
| `authorized` | `cancelled` | Cancelled after authorization |
| `running` | `waiting` | Human approval or resource needed |
| `running` | `completed` | All effects applied |
| `running` | `failed` | Error or constraint violation |
| `running` | `cancelled` | Cooperative cancellation |
| `running` | `timed_out` | Deadline exceeded |
| `waiting` | `running` | Approval granted / resource available |
| `waiting` | `completed` | Direct completion |
| `waiting` | `failed` | Approval denied |
| `waiting` | `cancelled` | Approval timeout |

Terminal states (`completed`, `failed`, `cancelled`, `timed_out`) have no
outgoing transitions. Attempting an illegal transition raises `ValueError`.

---

## Durability Semantics

### Guarantee

**At-least-once delivery with explicit idempotency support.**

- Every execution is persisted to SQLite (default) or PostgreSQL
- Journal is append-only with sequence numbers
- Checkpoints record completed effects for idempotency skip
- Effects carry `idempotency_key` for caller-enforced exactly-once

### What is NOT guaranteed

- Exactly-once delivery (caller must use idempotency keys)
- Crash-safe checkpoints (no fsync barrier between effect and checkpoint)
- Cross-process coordination (SQLite uses WAL mode with `busy_timeout=5000`)

### Recovery

On crash, `engine.recover()`:
1. Loads unfinished executions from durable storage
2. `RUNNING` executions are demoted to `WAITING`
3. Pending approvals are rehydrated
4. Executions resume from last checkpoint

---

## Agent Convergence

### Agent as runtime participant (v2.5.2)

Agents are durable entities registered in an `AgentRegistry`. Every agent
run **is** an Execution — there is no separate agent execution model.

When an `ExecutionEngine` is available, `Agent.run()` creates a first-class
`Execution` via the engine. Tool calls create child Executions with their
own lifecycle, capability context, and trace context.

```text
Agent Execution (execution_id: abc-123)
      ├── Tool Execution #1 (execution_id: def-456, parent: abc-123)
      ├── Tool Execution #2 (execution_id: ghi-789, parent: abc-123)
      └── Tool Execution #3 (execution_id: jkl-012, parent: abc-123)
```

`AgentRun` is a projection of the underlying `Execution` — it exists for
backward-compatible telemetry and agent-specific accounting, not as a
second source of truth.

---

## Security Model

### Capability-based, not role-based

- No ambient authority for sensitive operations
- Capabilities are explicit, scoped, delegatable, revocable, time-limited
- Sensitive capabilities denied by default (6 capabilities)
- `RedactionGuard` scrubs secrets from events/journal/telemetry
- `EnvSecretStore` (default) and `LocalSecretStore` (Fernet) for secrets

### Authorization flow

```text
principal → capability → authorization → execution → effect
```

Three outcomes: `ALLOWED`, `DENIED`, `REQUIRES_APPROVAL`.

---

## Observability

### Trace propagation

Every execution carries a `trace_id` that propagates through:
- HTTP requests (via middleware)
- Agent runs (via ContextVar)
- Tool calls (via child execution context)
- Worker jobs (via queue metadata)
- Mesh events (via correlation_id)
- HITL approvals (via execution context)

### Telemetry

`TelemetryStore` records:
- Agent runs (tokens, cost, tool calls)
- HTTP requests (latency, status)
- Tool calls (duration, errors)
- Custom spans (OTel-compatible)

---

## External Devices & the Edge Protocol (Sprint 23)

> **Amendment to the Architecture Freeze** — distinguishes the **Core
> Runtime Contract** (frozen above) from **External Integration
> Contracts** (versioned boundaries). The Edge Protocol is the first
> such external contract: `voodoo-edge/v1`. Future protocol versions
> must be additive or explicitly versioned; V1 clients must never be
> silently broken.

A physical or distributed device (ESP32, Raspberry Pi, robot,
industrial controller, browser runtime) participates in the **same**
model — no second architecture:

- **A Device is an Entity** — identity (`device:<id>`), versioned State,
  advertised Capabilities, participation in Executions.
- **Device Events enter the normal Event system.** A semantic event
  creates `Intent("device:<event>")` run by the standard
  ExecutionEngine with actor `device:<id>`; telemetry (heartbeat)
  updates state without creating Executions.
- **Device-triggered work enters the normal Execution system** — there
  is **no** `DeviceExecutionEngine`. Device executions carry the same
  lifecycle, capability checks, durability, and checkpoints as any
  other execution.
- **Device Effects are normal Effects** — stable `effect_id`, capability
  authorization at the runtime boundary, delivery tracked as
  `pending → delivered → acked` through the Device Gateway.
- **Capabilities govern Device Effects** — advertisement is separate
  from authorization; the runtime rejects effects a device lacks the
  capability for, at the boundary.
- **Device State uses normal State semantics** — monotonic
  `state_version` with compare-and-swap; stale state never overwrites
  newer state. Runtime-authoritative reconciliation (explicit).

### Edge concepts (NOT new core primitives)

The following are **conceptual contracts / boundary types** in
`voodoo.edge`, deliberately outside the frozen core: Device Identity,
Device Session (transport state — not an Entity, not an Execution),
Transport (HTTP/MQTT — interchangeable carriers of the same envelope),
Protocol Message (`voodoo-edge/v1` envelope), Acknowledgement
(effect delivery confirmation), Synchronization (state versioning +
reconciliation).

### Reliability contract

Edge delivery is **at-least-once with mandatory idempotency** — stable
`message_id`/`effect_id` collapse duplicates. No exactly-once semantics
are claimed on any transport.

### Where it lives

```
src/voodoo/edge/   — models, store, auth, protocol, gateway, transports, simulator
docs/edge/         — overview, protocol, http, mqtt, security, lifecycle,
                     state-synchronization, reliability, simulator
```

Edge is **disabled by default**; enabling it is pure configuration
(`[edge]` block / `VOODOO_EDGE_*`). Applications that never enable it
are unaffected (zero overhead — no broker, gateway, or device tables).

---

## Adding a New Core Primitive

Any new core primitive must answer:

1. Why can this not be composed from existing primitives?
2. What real problem does it solve?
3. Why does it belong in the runtime?
4. What invariant does it introduce?
5. What complexity does it introduce?
6. Why is that complexity justified?

If those questions cannot be answered convincingly, do not add it to core.

---

## See also

- [Execution Model](execution-model.md)
- [Runtime Engine](runtime.md)
- [Agents](agents.md)
- [Primitives](primitives.md)
- [Architecture Review](architecture-review-v2.5.md)
- [Voodoo Edge](edge/overview.md) · [Edge Protocol](edge/protocol.md)
