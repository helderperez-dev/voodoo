# Voodoo Computational Model

Voodoo's power comes from a small, explicit set of concepts — not from a large
API surface. This document defines the computational model the entire runtime
is built on.

The concepts live at different semantic levels. Some describe *what exists and
what is wanted* (the ontology). One describes *how work actually happens* (the
runtime). The rest describe *the conditions under which work happens*
(execution dimensions) and *what cuts across everything* (cross-cutting
concepts). They are deliberately **not** eight equal primitives.

## Core Ontology

The ontology defines what the system can represent and pursue.

| Concept | Definition |
|---|---|
| **Entity** | Something with identity that participates in the system |
| **State** | The current operational representation of what the system considers true |
| **Intent** | The desired outcome an entity wants to achieve |
| **Capability** | The ability and authorization to produce an effect under conditions |
| **Effect** | A change produced by an execution |

### Entity

> Something that has identity and can participate in the system.

Examples:

```text
User        Agent       Worker      Robot       Device
Sensor      Service     Order       Payment     Vehicle
Location    Organization
```

An Entity is an **ontological concept**, not an ORM model. It is not a database
row — it is the stable notion of *what exists* in the system. An entity may
have identity, state, capabilities, relationships, intents, executions, and
telemetry.

Operational systems — robotics, distributed systems, mission systems — need a
consistent representation of what exists. Today Voodoo represents an entity
through `State` (every `State` carries an `id` and a `kind` that identify the
entity it describes) plus the cross-cutting concept of **Identity**. A
dedicated `Entity` type is on the roadmap; the concept already governs the
model.

### State

> The current operational representation of what the system considers to be
> true about an entity or system.

Examples:

```text
robot.location      robot.battery      order.status
service.health      mission.status     user.permissions
```

State is observable, versionable, persistable when required, temporally valid,
and capable of producing events when it changes. State is not "database data" —
it is the operational truth of the system, whether or not it is persisted.

```python
from voodoo.primitives import State

# Create durable, versioned state
user = State(kind="user", data={"name": "Ada", "balance": 500})

# Mutate (returns new version)
updated = user.mutate(balance=400)
assert updated.version == 2

# Persist and restore
checkpoint = user.checkpoint()
restored = State.restore(checkpoint)

# Temporal validity
user.expire_in(3600)  # expires in 1 hour
user.expired  # False
user.valid  # True
```

### Intent

> The desired outcome that an entity or system wants to achieve.

Intent is **not a command**. `move_robot(...)` is a command;
`deliver_package(package_id)` is an intent. The runtime decides how the
outcome is achieved.

```text
Intent → Resolution → Capability → Execution
```

```python
from voodoo.primitives import Intent, Constraint

# An outcome to achieve (not a function call)
intent = Intent(
    name="send_invoice",
    params={"to": "client@example.com", "amount": 500},
)

# Require capabilities
intent.require("email.send").require("payment.execute")

# Add constraints
intent.constrain(Constraint.cost(maximum=0.10))
intent.constrain(Constraint.approval_required())

# Set deadline
intent.with_deadline(3600)

# Lifecycle
intent.queue()
intent.evaluate()
intent.execute()
intent.complete(result={"invoice_id": "inv_123"})

assert intent.finished
```

### Capability

> The ability and authorization to produce a particular effect under specific
> conditions.

Examples:

```text
robot.move      camera.capture    database.write
email.send      payment.charge    human.approve
service.deploy
```

A Capability is **not merely a permission**:

```text
Permission  = may this actor perform something?
Capability  = what can the system actually perform, under what conditions?
```

A capability may be scoped, delegated, revocable, time-limited, constrained,
unavailable, or authorized.

```python
from voodoo.primitives import Capability

# Explicit permission
cap = Capability(name="email.send")

# Time-limited
cap = Capability.timed("payment.execute", expires_in=600)

# Resource-scoped
cap = Capability.scoped("database.read", resource="customer:123")

# Delegate without transferring identity
delegated = cap.delegate("agent:456")

# Revoke
cap.revoke()
cap.valid  # False
```

### Effect

> A change produced by an execution.

Examples:

```text
database record changed    email sent
payment charged            robot moved
service deployed           door opened
sensor measurement recorded
```

The model distinguishes **Computation** (pure) from **Effect** (a change in the
world). Not every computation produces an external effect.

```python
from voodoo.primitives import Effect

# An explicit side effect
effect = Effect(
    name="send_email",
    intent_id="int_123",
    capability_name="email.send",
    reversible=False,
    idempotent=True,
)

# Lifecycle
effect.mark_executing()
effect.mark_succeeded(result={"message_id": "msg_123"})

# Rollback (only if reversible)
effect = Effect(name="write_record", reversible=True)
effect.mark_succeeded()
effect.mark_rolled_back()
```

## Runtime

### Execution

> The first-class runtime mechanism by which any operation moves from intent
> to an observable, recoverable outcome.

Execution is the center of the runtime. Any meaningful operation is an
Execution:

```text
HTTP request      API operation      Task
Worker execution  Agent run          Tool invocation
MCP operation     Human approval     Scheduled job
Device operation  Robot action
```

The conceptual model:

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

An Execution conceptually carries: `id`, `parent_execution`, `entity`,
`intent`, `capabilities`, `compute`, `constraints`, `resources`, `time`,
`effects`, `events`, `state`, `telemetry`, `checkpoint`, `status`, `outcome`,
`error`, and `recovery`. Not every field is materialized in code — the
semantics come first.

In code, `Execution` and `ExecutionEngine` live in `voodoo.runtime`. See
[`docs/execution-model.md`](execution-model.md) for the full lifecycle.

## Execution Dimensions

These govern *how* and *under what conditions* an Execution happens. They are
fundamental, but they are **dimensions of execution**, not peers of the core
ontology.

### Compute

> How an execution is performed.

```text
deterministic    inference    reasoning    human
remote           edge         distributed  physical
```

**AI is only one form of Compute** — never a primitive of its own. The same
runtime executes work through CPU, GPU, LLM, human, worker, device, robot, or
remote service without changing the Intent model.

```python
from voodoo.primitives import ComputeSpec, Constraint, Resource

# Deterministic (default)
c = ComputeSpec.deterministic()

# AI reasoning (one class of compute)
c = ComputeSpec.reasoning(provider="openai", model="gpt-4o")

# Inference
c = ComputeSpec.inference(provider="local", model="llama-3")

# Human-assisted
c = ComputeSpec.human()

# With constraints and resources
c = (
    ComputeSpec.reasoning(provider="anthropic", model="claude-3")
    .constrain(Constraint.cost(maximum=0.05))
    .with_resources(Resource(cost=0.03, latency_ms=500))
)
```

### Time

> Governs the lifecycle and validity of an execution.

```text
deadline    timeout    expiration    schedule
retry delay duration    temporal validity
```

```python
from voodoo.primitives import TimeSpec

# Deadline
t = TimeSpec.with_deadline(3600)
t.remaining  # ~3600 seconds
t.deadline_passed  # False

# Expiration
t = TimeSpec.with_expiration(600)
t.expired  # False

# Retry
t = TimeSpec.with_retry(retry_after=30, max_retries=3)

# Periodic
t = TimeSpec.with_interval(60)
```

### Resource

> Something required or consumed by an execution.

```text
CPU     GPU       memory        storage
network tokens    money         energy
battery human attention  physical capacity
```

Resources eventually support resource-aware planning. For physical systems:

```text
Robot
 ├── battery
 ├── compute
 ├── mobility
 ├── payload
 ├── sensors
 └── network
```

```python
from voodoo.primitives import Resource

# Resource consumption
r = Resource(cost=0.03, latency_ms=500, energy="high", tokens=1500)

# Combine resources
a = Resource(cost=0.01, latency_ms=100)
b = Resource(cost=0.02, latency_ms=200)
combined = a.add(b)
# combined.cost == 0.03, combined.latency_ms == 200
```

### Constraint

> Conditions that must be satisfied.

```text
cost < $1              latency < 200ms
battery > 20%          human approval required
location == local      temperature < 80°C
max_amount = $1000
```

Conceptually, `Intent + Capability + Constraints` define the feasible
execution space.

```python
from voodoo.primitives import Constraint

# Cost constraint
c = Constraint.cost(maximum=0.10)
c.evaluate(0.05)  # True
c.evaluate(0.15)  # False

# Latency constraint
c = Constraint.latency(maximum_ms=100)
c.evaluate(50)  # True
c.evaluate(150)  # False

# Data locality
c = Constraint.locality(must_be="local")

# Human approval required
c = Constraint.approval_required()

# Maximum payment amount
c = Constraint.max_amount(100)
```

## Cross-Cutting Concepts

These cut across every level of the model.

- **Event** — something that happened; lets other parts of the runtime react.
- **Identity** — stable identity for entities, executions, capabilities, and
  other runtime objects.
- **Telemetry** — observability into what the runtime is doing and what
  actually happened.
- **Relationship** — connections between entities; lets the runtime represent
  operational graphs rather than isolated objects.

## Execution Model

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

with **Compute**, **Time**, **Resource**, and **Constraint** governing the
Execution at every stage.

## Progressive Complexity

The complexity comes from composition, not from framework magic:

| Application type | Concepts in play |
|---|---|
| Small app | Entity, State, Effect |
| Distributed app | Entity, State, Intent, Execution, Effect, Time |
| AI application | Entity, State, Intent, Capability, Execution, Compute, Effect |
| Autonomous system | Entity, State, Intent, Capability, Execution, Compute, Constraint, Effect, Time |
| Physical-world system | all — plus Resource (battery, payload, sensors) |

## Design Philosophy

- **Small primitives** — a focused set of composable concepts
- **Explicit semantics** — clear meaning, no magic
- **Composable execution** — executions nest and chain
- **Inspectable state** — state is observable and versionable
- **Recoverable operations** — every execution can checkpoint and resume
- **Vendor-independent core** — no OpenAI / Anthropic / AWS coupling
- **Local-first, cloud-capable** — zero infra by default, production by config
- **AI-optional** — AI is one Compute, never mandatory
- **Physical-world capable** — the same model reaches devices and robots

The sophistication is in the model, not in the API surface. Voodoo should feel
almost boring at first — that is intentional.

## The Voodoo Test

Every proposed feature or abstraction must pass:

1. Is this a fundamental property of computation or operation?
2. Can it already be expressed through Entity, State, Intent, Capability,
   Execution, Effect, Compute, Time, Resource, or Constraint?
3. Could this still make sense in 2040?
4. Could this still make sense if AI architectures change completely?
5. Could this work locally without cloud infrastructure?
6. Does it reduce conceptual complexity or add to it?
7. Does it belong in the core, or should it be an optional capability?
8. Are we solving a fundamental problem or today's ecosystem problem?
9. Are we coupling Voodoo to a vendor, protocol, or implementation?
10. Would a developer understand the abstraction without reading 500 pages of
    documentation?
