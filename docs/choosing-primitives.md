# Choosing Voodoo primitives

Voodoo intentionally has several kinds of state, events, and executable units. They exist at different semantic levels and should not be used interchangeably.

## Decision table

| Need | Use | Do not use it as |
|---|---|---|
| UI-local mutable value | `state()` | business persistence |
| Persistent business entity | `Model` | reactive UI cell |
| Long-term contextual recall | Memory | authoritative business database |
| Browser interaction | `@event` | cross-service event bus |
| Decoupled application notification | Mesh / event bus | durable job by itself |
| Retryable background work | `@task` | arbitrary helper function |
| Meaningful durable/observable operation | `Execution` | wrapper around every function call |
| LLM reasoning and tool loop | `Agent` | universal execution primitive |
| Reusable callable action | `@tool` | authorization policy |
| Authorization to produce an effect | `Capability` | callable implementation |
| Human decision inside work | HITL approval | ad-hoc polling |
| Future/recurring work | Scheduler | request-time delay |

## State: reactive state, Model, Memory, execution state

**Reactive state** exists to drive a rendered UI. It is ephemeral application/UI state.

**Model** is persistent domain data. If losing the value on process restart would corrupt business truth, it probably belongs in a Model or another durable store.

**Memory** is contextual recall for agents/runtime behavior. It is not the source of truth for orders, users, permissions, money, or other business records.

**Execution state** describes the lifecycle and observable consequences of a unit of runtime work. It is not a replacement for domain models.

## Events: UI events, application events, execution telemetry

A **UI event** represents browser interaction and is coupled to the reactive UI boundary.

An **application event** represents a fact or notification that other application participants may react to. Use Mesh/event-bus semantics when producers and consumers should be decoupled.

**Execution telemetry** records what happened while meaningful work ran. Do not use telemetry as the application event bus, and do not turn every event into a durable Execution.

## Tool, Capability, Task, Agent, Execution

A **Tool** answers: *what callable action is available?*

A **Capability** answers: *is this participant authorized/able to produce this effect under these conditions?*

A **Task** answers: *what work should run asynchronously with worker semantics such as retry/timeout?*

An **Agent** answers: *what model-driven participant can reason and choose/use tools?*

An **Execution** answers: *what meaningful unit of work do we need to observe, authorize, recover, account for, or reason about?*

These concepts compose. They are not aliases.

## When should something become an Execution?

Create an Execution when one or more of these properties matter:

- durability or crash recovery;
- capability/authorization enforcement;
- parent-child delegation and traceability;
- effect or state-change recording;
- resource/cost accounting;
- retries, timeout, scheduling or waiting;
- human approval;
- operational observability at a user/business boundary.

Do not create an Execution solely because a Python function ran. Helper calls, render passes, state reads, serialization and internal callbacks should normally remain implementation details.

## Progressive complexity

Start with the smallest primitive that expresses the problem. A page does not need the adaptive supervisor. A simple function does not need to become a Task. A Task does not need an Agent. An Agent does not need a Planner unless capability resolution or adaptive behavior is useful.

Voodoo's unified runtime means these pieces can converge when needed; it does not mean every application must use every subsystem.
