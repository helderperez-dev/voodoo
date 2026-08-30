# Execution Model

> **The central technical specification for the Voodoo Execution Runtime.**
>
> This document answers one question: **How does any Voodoo operation move
> from an Intent to an observable, recoverable outcome?**

---

## What Execution is

An **Execution** is the first-class runtime unit through which every meaningful
operation flows. An HTTP request, an API operation, a task, a worker job, an
agent run, a tool invocation, an MCP call, a human approval, a scheduled job, a
device operation, and a robot action are all different forms of the same thing:
an Execution.

Executions converge the subsystems — UI, API, agents, workers, tools, MCP,
humans, and devices — onto one lifecycle, one identity model, one telemetry
model, and one recovery model. There is no separate execution model per
subsystem.

## The conceptual model

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

- An **Entity** (with **State**) pursues an **Intent**.
- The intent resolves to a **Capability** — the ability and authorization to
  produce an effect.
- The capability is performed as an **Execution**, governed by **Compute**
  (how), **Time** (when / how long), **Resource** (what is consumed), and
  **Constraint** (what must hold).
- The execution produces an **Effect**, which changes **State**.

## Execution Lifecycle

### Implemented states (v2.5.0)

The happy path:

```text
Created → Authorized → Running → Completed
```

Alternative and terminal states:

```text
Planned     Waiting      Failed
Cancelled   Timed Out
```

Total: **9 states**. Transitions are validated — illegal transitions raise
`ValueError`. See `LEGAL_TRANSITIONS` in `voodoo.runtime.execution`.

### Aspirational states (not yet implemented)

The following states are part of the long-term model but are not yet
implemented in the code:

```text
Validated   Blocked      Paused
Recovering  Compensating
```

These will be added when their semantics are fully defined. Do not reference
them as if they exist in the current runtime.

### State transitions (implemented)

| From | To | Trigger |
|---|---|---|
| `created` | `authorized` | Engine authorizes capability (default path) |
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

States move forward. The only backward move is `running → waiting` (human in
the loop).

### The execution fields (conceptual)

```text
id
parent_execution
entity
intent
capabilities
compute
constraints
resources
time
effects
events
state
telemetry
checkpoint
status
outcome
error
recovery
```

Not every field is materialized today. Fields are added when their semantics
are defined — never to complete a checklist.

## Parent / child executions

Executions nest. A tool call inside an agent run is a child execution; the
agent run is its parent. This gives full traceability:

- `id` — this execution.
- `parent_execution_id` — the execution that caused this one.
- `trace_id` — the correlation ID linking the whole chain.

Cancelling a parent propagates to children. Completing a parent requires its
children to have completed, failed, or been cancelled.

## Agents and executions (Sprint 17)

Agents are durable entities registered in an `AgentRegistry`. Every agent
run **is** an Execution — there is no separate agent execution model. The
registry links the two:

- `AgentEntity` — durable agent identity (id, model, tools, capabilities,
  state) stored in the registry.
- `AgentRunRecord` — persisted after every run/stream, linking `agent_id` →
  `execution_id` with prompt, output, tokens, cost, and `trace_id`.

Because runs are executions, agent history is queryable through the normal
execution views (`voodoo inspect executions`) **and** per-agent via the
registry (`registry.get_runs(agent_id)` / `voodoo agents show <id>`). Two
agents collaborating via events produce linked, parented executions — no
bespoke agent RPC (ROADMAP §47).

See [agents.md](agents.md) for the registry API and CLI.

## Durable human approvals (Sprint 18)

A `WAITING_FOR_HUMAN` execution is a first-class durable state — not a live
callback. The approval record persists a **participant name**; any process
that registers that participant can resume the work after a decision:

- On wait: journal `approval.requested`, persist the approval (with
  participant) to the store.
- On decide (`approve`/`deny`): journal `approval.granted`/`approval.denied`,
  re-resolve the compute from the participant registry (falling back to the
  waiting execution's persisted intent), and re-run it under a child context
  carrying the decision.

Because the resume path normalizes through `engine.execute`, a resumed
approval is itself an Execution — cancel, retry, and telemetry behave
identically. See [hitl.md](hitl.md) for the CLI workflow.

## Cancellation

Cancellation is cooperative. An execution carries a `cancel` signal
(`asyncio.Event`). Cancelling:

1. Marks the execution `cancelled`.
2. Signals children to cancel.
3. Records an `execution.cancelled` event.
4. Leaves already-applied effects in place — they are not silently undone
   (see Compensation).

## Retry

Retries are governed by **Time** and **Constraint**:

- `max_attempts` — how many times.
- `retry_after` / backoff — how long to wait.
- Retry eligibility — whether the failure is transient and whether the effect
  is idempotent.

A retry creates a new attempt within the same execution, not a new execution.

## Timeout

Timeouts are a **Time** dimension. A deadline converts to a timeout; when it
passes, the execution transitions to `timed_out`. Timeouts are enforced, not
advisory.

## Idempotency

An effect carries an `idempotency_key`. A resumed or retried execution must
not blindly re-run a non-idempotent effect. On resume:

- If the effect already succeeded (recorded in the journal), it is skipped.
- Otherwise it runs, keyed by `idempotency_key`.

## Checkpointing

Checkpoints are durable snapshots at meaningful boundaries:

- after model completion;
- after tool completion;
- after a state mutation;
- after task scheduling;
- before waiting (human approval).

A checkpoint records JSON-serializable state — never live Python objects —
with deterministic ids.

## Recovery

On restart, `recover` loads unfinished executions from durable storage and
re-drives them from their last checkpoint. Completed steps are not
re-executed. Waiting executions are restored with their pending approvals.

## Failure handling

Failures are structured (`ExecutionError` hierarchy) and recorded. A failure:

1. Records the error and context.
2. Emits an `execution.failed` event.
3. Either retries, falls back, delegates, or fails — per the adaptive
   supervisor.
4. Never silently swallows the error.

## Compensation

When a failed execution has already applied reversible effects, it may
**compensate** — undo those effects. Only reversible effects can be rolled
back; irreversible effects must be handled by policy, not silence.

## Human intervention

An execution that requires human approval enters `waiting` and persists the
pending approval. A decision (grant / deny) is a durable event that resumes or
cancels the execution — even from a different process.

## Resource accounting

Executions track what they consume (cost, latency, tokens, energy) against a
budget via **Resource**. Exceeding the budget is a constraint violation.

## Constraint evaluation

Constraints are evaluated before and during execution. A violated constraint
fails or pauses the execution (soft stop → checkpoint → pause).

## Telemetry & events

Every execution emits namespaced events (`execution.created`,
`execution.completed`, `tool.completed`, ...) and carries a `trace_id` through
the whole stack. Telemetry is the sensory system: what is happening, and what
actually happened.

## Local vs distributed execution

The same model runs locally (single process, SQLite) or distributed (multiple
workers, PostgreSQL / Redis) behind capability-based adapters. The lifecycle
and recovery semantics do not change; only the transport and storage provider
do.

## Relationship to the implementation

| Concept | Where it lives |
|---|---|
| `Execution`, `ExecutionStatus` | `voodoo.runtime.execution` |
| `ExecutionEngine` | `voodoo.runtime.engine` |
| `ExecutionContext` | `voodoo.runtime.context` |
| `CapabilityResolver` | `voodoo.runtime.capability` |
| `ConstraintEnforcer`, `ResourceAccountant` | `voodoo.runtime.constraint` |
| `Planner`, `ComputeParticipant` | `voodoo.runtime.planner` |
| `AdaptiveSupervisor` | `voodoo.runtime.adaptive` |
| Durable store (`SQLiteExecutionStore`) | `voodoo.storage.execution` |

## See also

- [Voodoo Computational Model](primitives.md)
- [Runtime Engine](runtime.md)
- [Planner & Adaptive Runtime](adaptive.md)
- [Human-in-the-Loop](hitl.md)
- [Architecture](../ARCHITECTURE.md)
