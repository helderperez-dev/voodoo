# Runtime Engine Instructions

> **Read this before:** touching anything in `src/voodoo/runtime/`, adding execution flows, modifying the planner, or working with durable persistence.

---

## The ExecutionEngine (`voodoo.runtime.engine`)

The `ExecutionEngine` is the unified execution model. Every meaningful operation — HTTP request, agent run, tool call, MCP dispatch, worker job, workflow step, human approval, event handler — flows through it and produces an `Execution` record.

### Core API

```python
from voodoo.runtime import engine, execute, ExecutionContext

# Execute an intent
result = await engine.execute(
    intent="notify.customer",
    params={"user_id": 42, "message": "Order shipped"},
    capabilities=["email.send", "sms.send"],
)

# Checkpoint state for recovery
engine.checkpoint(execution)

# Recover unfinished executions after a crash
await engine.recover()

# Attach a durable store
engine.use_store(store)
```

### Singleton

`engine` is a module-level singleton. Never instantiate `ExecutionEngine()` directly in production code — always use the imported `engine`. In tests, create fresh instances per test to avoid cross-test state leakage.

---

## Execution Lifecycle

```
created → planned → authorized → running → waiting → completed
                    ↓               ↓           ↓
                rejected      cancelled    failed / timed_out
```

### Status transitions (enforced)

| From | To | Trigger |
|---|---|---|
| `created` | `planned` | Planner resolves participants |
| `planned` | `authorized` | CapabilityResolver allows |
| `planned` | `rejected` | CapabilityResolver denies |
| `authorized` | `running` | Compute begins |
| `running` | `waiting` | Human approval needed |
| `waiting` | `running` | Approval granted |
| `waiting` | `cancelled` | Approval denied / timeout |
| `running` | `completed` | All effects applied |
| `running` | `failed` | Error / constraint violation |
| `running` | `timed_out` | Deadline exceeded |

Never skip states. Never transition backward (except `running → waiting` for HITL).

---

## ExecutionContext (`voodoo.runtime.context`)

Every execution runs inside a context that carries:

| Field | Purpose |
|---|---|
| `execution_id` | Unique ID for this execution |
| `trace_id` | Correlation ID (propagates through entire stack) |
| `parent_execution_id` | For nested executions (tool calls within agent runs) |
| `actor` | Who/what initiated this (`"user:42"`, `"agent:run_abc"`, `"system"`) |
| `capabilities` | List of granted capability strings |
| `deadline` | Optional `datetime` for timeout enforcement |
| `cancel` | `asyncio.Event` for cooperative cancellation |

### Accessing the current context

```python
from voodoo.runtime.context import current_context, use_context

ctx = current_context()  # Get current context (or None)
```

### Trace ID propagation

`trace_id_var` is a `ContextVar` that propagates through `asyncio` tasks. The `TelemetryMiddleware` sets it per HTTP request. Agent runs, tool calls, and worker jobs inherit it automatically.

**Never override `trace_id`** unless creating a new top-level execution (e.g., a background worker picking up a queued job).

---

## Capability Resolution (`voodoo.runtime.capability`)

```python
from voodoo.runtime.capability import CapabilityResolver, Resolution

resolver = CapabilityResolver()
resolution = resolver.resolve(intent, capabilities)

if resolution == Resolution.ALLOWED:
    # proceed
elif resolution == Resolution.DENIED:
    # reject
elif resolution == Resolution.APPROVAL_REQUIRED:
    # pause for human approval
```

Capabilities are **strings** (e.g., `"email.send"`, `"database.write"`). They map to `Capability` primitives and are checked against the execution's granted capabilities.

---

## Constraint Enforcement (`voodoo.runtime.constraint`)

```python
from voodoo.runtime.constraint import ConstraintEnforcer, ResourceAccountant

enforcer = ConstraintEnforcer()
decision = enforcer.evaluate(execution, constraints)

if decision == Decision.CONTINUE:
    # proceed
elif decision == Decision.FAIL:
    # constraint violated — fail the execution
elif decision == Decision.STOP:
    # soft stop — checkpoint and pause
```

`ResourceAccountant` tracks cumulative cost, latency, and token usage against a budget. When the budget is exceeded, the enforcer returns `Decision.STOP`.

---

## Planner (`voodoo.runtime.planner`)

The `Planner` resolves an `Intent` into a `Plan` — a sequence of `PlanStep`s, each with a `ComputeParticipant` (agent, tool, model, or human).

```python
from voodoo.runtime.planner import Planner

planner = Planner()
plan = planner.plan(intent, capabilities, constraints)

for step in plan.steps:
    participant = step.participant  # ComputeParticipant
    # execute step...
```

### ComputeParticipant types

| Type | Description |
|---|---|
| `agent` | An AI agent run |
| `tool` | A tool execution |
| `model` | Direct LLM call |
| `human` | Human-in-the-loop approval |

---

## Adaptive Supervisor (`voodoo.runtime.adaptive`)

```python
from voodoo.runtime.adaptive import AdaptiveSupervisor, SupervisorConfig

supervisor = AdaptiveSupervisor(
    config=SupervisorConfig(
        max_retries=3,
        fallback_model="mock:default",
        enable_delegation=True,
    )
)

decision = supervisor.decide(execution, error)
# SupervisorDecision: RETRY, FALLBACK, DELEGATE, STEER, CANCEL
```

The supervisor makes retry/fallback/delegate/steer/cancel decisions when executions fail or degrade.

---

## Human-in-the-Loop (`voodoo.runtime.human`)

```python
from voodoo.runtime.human import ask_human, Approval, ApprovalStatus

# Request human approval
approval = await ask_human(
    prompt="Approve payment of $5000?",
    capabilities=["payment.authorize"],
)

if approval.status == ApprovalStatus.APPROVED:
    # proceed
elif approval.status == ApprovalStatus.DENIED:
    # cancel execution
elif approval.status == ApprovalStatus.PENDING:
    # execution enters waiting state
```

### Approval Registry

Approvals are persisted in the `ApprovalRegistry`. The `voodoo recover` command restores pending approvals. CLI commands:

```bash
voodoo approvals                    # list approvals
voodoo approvals approve <id>      # approve
voodoo approvals deny <id>         # deny
voodoo inspect approvals --pending # inspect pending
```

---

## Workflows & Tasks (`voodoo.runtime.task`, `voodoo.runtime.workflow`)

```python
from voodoo.runtime.workflow import Workflow, WorkflowStrategy

workflow = Workflow(
    name="order.fulfillment",
    steps=[...],
    strategy=WorkflowStrategy.SEQUENTIAL,
)

run = await workflow.run(params)
```

`Task` represents a single unit of work within a workflow. `WorkflowRun` tracks the overall progress.

---

## Execution Graph (`voodoo.runtime.graph`)

`ExecutionGraph` and `ExecutionNode` model the causal relationships between executions. Each node knows its parent, children, and causal links. This enables:

- **Causation tracking** — Why did this execution happen?
- **Impact analysis** — What will break if this execution is cancelled?
- **Lineage queries** — What's the full history of this trace?

---

## When Adding Runtime Features

1. **Identify the concept** — Does your feature touch Entity, State, Intent, Capability, Execution, Effect, Compute, Time, Resource, or Constraint?
2. **Extend the engine** — New compute kinds, new constraint types, new adaptive strategies go in the appropriate module.
3. **Update the planner** — If your feature introduces a new participant type, register it in the planner.
4. **Add persistence** — If your feature produces durable state, extend the `ExecutionStore` Protocol and implementations.
5. **Test with fresh engine** — Use `ExecutionEngine()` per test, never the singleton.
6. **Add CLI inspection** — If users need to observe your feature, add a `voodoo` subcommand.
7. **Update docs** — Add to `docs/runtime.md` and relevant instruction files.

---

## Runtime Error Hierarchy (`voodoo.runtime.errors`)

```
ExecutionError (base)
├── CapabilityDenied
├── ConstraintViolation
├── ResourceExceeded
├── ExecutionTimeout
├── ExecutionCancelled
├── ToolExecutionError
├── AgentExecutionError
├── ValidationError
├── ApprovalRequired
└── WorkflowFailure
```

Always raise the most specific error. Catch `ExecutionError` for broad handling. Never swallow — log context and re-raise or convert to a user-facing error.
