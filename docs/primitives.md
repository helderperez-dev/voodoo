# Architectural Primitives

## What it is

Voodoo is built on eight fundamental computational primitives that remain valid regardless of how computation evolves. These are architectural primitives, not application features.

The goal is not to predict what applications will look like. The goal is to provide primitives that remain valid regardless of what applications become.

## The eight primitives

| Primitive | Concept |
|---|---|
| **State** | What the system knows to be true — durable, versioned, inspectable |
| **Capability** | What an entity is explicitly allowed to do — composable, revocable, delegatable |
| **Intent** | What the system is trying to accomplish — outcome-oriented, lifecycle-managed |
| **Effect** | A change caused outside pure computation — explicit, traceable, reversible/irreversible |
| **Time** | First-class temporal concept — deadlines, expiration, scheduling, retry |
| **Compute** | The act of performing computation — AI is one class, not a separate subsystem |
| **Resource** | Something consumed or depended upon — cost, latency, energy, tokens |
| **Constraint** | What the system must or must not do — part of execution semantics |

## The execution model

```
STATE → INTENT → CAPABILITY → COMPUTE → EFFECT → STATE
TIME + CONSTRAINTS surround the entire lifecycle.
RESOURCE determines how execution should be performed.
```

- **State** describes the current truth
- **Intent** says what outcome to achieve
- **Capability** permits the execution
- **Compute** performs the computation
- **Effect** changes the world (and thus State)
- **Time** and **Constraints** govern every stage
- **Resource** determines how execution should be performed

## Usage

```python
from voodoo.primitives import (
    State,
    Capability,
    Intent,
    Effect,
    TimeSpec,
    ComputeSpec,
    Resource,
    Constraint,
)
```

### State

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

### Capability

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

### Intent

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

### Effect

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

### Time

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

### Compute

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

### Resource

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

## Progressive complexity

The complexity comes from composition, not from framework magic:

| Application type | Primitives used |
|---|---|
| Small app | State, Effect |
| Distributed app | State, Intent, Effect, Time |
| AI application | State, Intent, Compute, Capability, Effect |
| Autonomous system | State, Intent, Capability, Compute, Constraint, Effect, Time |
| Physical-world system | All eight |

## Design philosophy

- **Small primitives** — each is a focused, composable model
- **Explicit semantics** — clear meaning, no magic
- **Composability** — primitives compose naturally
- **Inspectability** — every primitive has `describe()` for machine-readable semantics
- **Minimal developer surface** — Voodoo should feel almost boring at first
- **The sophistication is in the model, not in the API surface**

## The Voodoo test

Every proposed feature must pass:

1. Is this a fundamental property of computation?
2. Could this still make sense in 2040?
3. Could this still make sense if AI architectures change completely?
4. Could this work locally without cloud infrastructure?
5. Does this reduce conceptual complexity or add to it?
6. Can it be expressed through existing primitives?
7. Does it belong in the core, or should it be an optional capability?
8. Are we solving a fundamental problem or today's ecosystem problem?
9. Are we coupling Voodoo to a vendor, protocol, or implementation?
10. Would a developer understand the abstraction without reading 500 pages of documentation?
