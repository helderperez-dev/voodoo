# VOODOO — MASTER ROADMAP

## A unified architecture and engineering direction for the Voodoo Runtime

| Field | Value |
|---|---|
| Status | Living architectural source of truth |
| Repository | `helderperez-dev/voodoo` |
| Current implementation tracker | [`SPRINT_PLAN.md`](SPRINT_PLAN.md) |

---

## 1. North Star

> **Voodoo is the programmable runtime for adaptive applications and operational systems.**

The goal is not to make a Python framework with the most features. The goal is
to make a small set of primitives express software, AI, human workflows,
distributed systems and increasingly physical systems through one coherent
runtime.

The computational model is:

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

`Compute`, `Time`, `Resource` and `Constraint` govern execution.

Cross-cutting concepts include `Identity`, `Event`, `Relationship`, `Policy`,
`Observation` and `Telemetry`.

An `Execution` is not every function call. It is an operation worth observing,
authorizing, recovering, accounting for, waiting on or reasoning about.

---

## 2. Architectural thesis

Modern systems fragment one problem across frontend, backend, database, queues,
workers, AI SDKs, workflow engines, messaging, observability and device stacks.
Each subsystem tends to invent its own lifecycle, security model and failure
semantics.

Voodoo's thesis is that much of that fragmentation is accidental.

Different participants should converge on one runtime model:

```text
UI
API
Worker
Agent
Human
External service
Remote node
Device
Robot
Sensor
        ↓
      Intent
        ↓
Capability + Policy
        ↓
    Execution
        ↓
      Effect
        ↓
 observed evidence
        ↓
      World
```

AI is one form of Compute. Devices are external participants. Humans are valid
participants. None of them receives a private execution architecture.

---

## 3. The two histories

Voodoo deliberately keeps operational history and world evidence distinct.

```text
EXECUTION HISTORY
Intent → Execution → Effect → Result / Failure / Approval / Recovery

WORLD HISTORY
Entity → Observation → Relationship → projected state / source / confidence / time
```

They are linked through lineage such as `execution_id` and `trace_id`, but they
answer different questions:

- **Execution history:** what did the system try to do and why?
- **World history:** what evidence says actually happened?

An Effect never becomes observed truth merely because the runtime issued it.

---

## 4. Current repository position

The repository is now materially beyond the earlier "Python web framework"
phase.

Implemented foundations include:

- reactive/server-driven Python UI and Design System 2;
- routing/APIs, data models, auth/security and infrastructure adapters;
- workers, queues, scheduler, object storage and event infrastructure;
- canonical `ExecutionEngine`, durable checkpoints/recovery and HITL;
- capability security and contextual operational Policy;
- Agents, tools, providers, MCP integration and persistent Memory;
- Ontology/World Model with `Entity`, `Relationship` and append-only
  `Observation` evidence;
- Goal Runtime and bounded adaptive supervision;
- Edge device identity/auth/protocol/effect lifecycle;
- governed distributed execution with replay/idempotency and WAITING/HITL;
- language-neutral JSON Schema protocol surface;
- operational runtime/system UI components.

Implementation status lives in [`SPRINT_PLAN.md`](SPRINT_PLAN.md); this document
sets architectural direction rather than pretending every long-term idea is
already complete.

---

## 5. Current convergence target

Sprint 27 closes the loop between the foundations already present:

```text
World
  ↓
Observation
  ↓
Goal / Intent
  ↓
Context-aware planning
  ↓
Capability + Policy
  ↓
Execution
  ↓
Effect
  ↓
Software / Human / Device
  ↓
ACK / observed evidence
  ↓
Observation
  └──────────────→ World
```

The significance of this loop is larger than any individual subsystem: it is
the point at which Voodoo stops being a collection of integrated framework
features and becomes a coherent operational runtime.

Sprint 27 plan:
[`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md)

---

## 6. Developer-experience law

Voodoo should support progressive complexity.

A simple application should remain simple:

```python
from voodoo import App, page

app = App()

@page("/")
def home():
    return "Hello"
```

Operational systems may add World, Goals, policy and devices without replacing
the underlying runtime.

The 3.0 import law is defined in [`docs/public-api-3.md`](docs/public-api-3.md):
package-root imports are a compatibility/happy-path facade; subsystem catalogs
belong to their semantic namespaces such as `voodoo.ui`, `voodoo.runtime`,
`voodoo.world`, `voodoo.edge` and `voodoo.protocol`.

---

## 7. World and operational intelligence

The World layer exists to represent what the runtime currently believes about
operational reality, with evidence and provenance rather than blind mutation.

Core semantics:

- `Entity` — stable identity;
- `Relationship` — typed directed relationship;
- `Observation` — append-only evidence with source, confidence and event time;
- projected State — the latest accepted evidence;
- Effect — attempted action, not evidence;
- WorldSnapshot — bounded reasoning/policy projection.

Future World intelligence may include temporal facts, derived state, belief
management and richer confidence reasoning, but only after the direct evidence
model remains clear and inspectable.

---

## 8. Agency

Agency is built from runtime primitives rather than privileged AI authority.

```text
Reason freely.
Act through capabilities.
Observe consequences.
Continue from state.
```

A durable autonomous participant needs:

- identity;
- state and memory;
- goal/intent;
- capabilities;
- constraints and policy;
- execution/effects;
- observations;
- time and resources;
- delegation/human participation;
- restart recovery.

`GoalRuntime` and `AdaptiveSupervisor` provide bounded orchestration. The
Planner remains deterministic-first; contextual ranking may choose among
already-authorized participants but never grants authority.

---

## 9. Embodiment / Edge

Edge is a boundary into the same Runtime, not a second Runtime.

```text
Sensor / device
  ↓
Edge protocol
  ↓
Observation / Intent
  ↓
World + Runtime
  ↓
Capability + Policy
  ↓
Execution
  ↓
Effect
  ↓
Device
  ↓
ACK / evidence
```

Physical actions must remain traceable and safety constraints must be explicit.
Intermittent connectivity, replay and idempotency are normal operating
conditions, not exceptional cases.

Large robot/fleet products are deliberately deferred until this semantic loop
is proven by small reference systems.

---

## 10. Distributed Runtime

Network transport never grants authority.

Remote work follows:

```text
Remote participant
  ↓
Identity evidence
  ↓
Remote request
  ↓
Intent
  ↓
Capability + Policy
  ↓
ExecutionEngine
  ↓
COMPLETED / FAILED / WAITING
  ↓
correlated outcome
```

Replay protection, idempotency and lineage are part of the semantic contract.
Voodoo does not claim global exactly-once execution or distributed consensus.

---

## 11. Protocol and SDK strategy

Python remains the primary implementation runtime, but Python internals are not
the interoperability boundary.

`voodoo.protocol` defines JSON-friendly schemas for application/runtime
concepts. Sprint 27 extends that boundary to World, Goal and distributed
execution semantics.

Future TypeScript, Go, Rust and embedded SDKs should primarily be protocol
clients rather than alternative copies of the Runtime.

---

## 12. Memory

Memory is contextual recall, not business truth and not the World Model.

Current layers provide Working, Episodic, Durable and Semantic storage/search.
Future work may add consolidation, reflection and relevance strategies, but the
runtime should not become a vector-database framework.

---

## 13. Cloud and product surfaces

Potential future products include:

- Voodoo Runtime managed infrastructure;
- Studio / operational control surface;
- Identity productization;
- Store/ecosystem packaging;
- managed database/storage/queue/Mesh/workers/telemetry;
- deployment, domains, logs and rollback.

These products must sit **above** the Runtime contracts. They must not duplicate
Execution, Identity, Policy or World semantics.

Cloud remains optional.

---

## 14. Long-horizon thought experiment

These horizons are architectural pressure tests, not literal predictions.

**2030:** Voodoo should read as an application/runtime platform rather than a
Python web framework.

**2050:** the same primitives should still make sense for distributed digital
and physical operational systems.

**2100:** concepts such as identity, intent, capability, constraint, execution,
effect, observation and state should still be coherent even if the compute
participants have changed completely.

---

## 15. Architectural lineage

Voodoo draws enduring ideas from systems rather than copying products:

- Palantir — ontology and operational entities;
- Anduril/Lattice — sensors → world state → intent → task/execution → feedback;
- NASA/JPL — autonomy, reliability, telemetry and recovery;
- SpaceX — vertical control of critical interfaces;
- Erlang/OTP — failure and supervision as first-class concepts;
- cloud-native systems — adapters, replaceable infrastructure and elastic
  compute;
- robotics/industrial systems — closed-loop action and observation.

The synthesis matters more than any single inspiration.

---

## 16. What Voodoo must not become

Voodoo must not become:

- a React clone;
- an AI-only or prompt framework;
- an MCP framework;
- a Kubernetes wrapper;
- an IoT broker;
- a robotics middleware replacement;
- a giant miscellaneous standard library;
- a cloud lock-in product;
- a system where every helper call becomes an Execution;
- a system where AI receives ambient unrestricted authority.

---

## 17. Next phases after convergence

The exact numbered sprint after Sprint 27 is selected only after Sprint 27's
acceptance review. Candidate next-phase initiatives, in rough dependency order,
are:

1. **Protocol/SDK productization** — generated clients and non-Python
   participation against stable contracts.
2. **Physical reference system** — small real ESP32/robot canary proving the
   closed operational loop outside simulation.
3. **Mission/fleet orchestration** — multi-device Goals only after single-device
   semantics are stable.
4. **Studio / operational product surface** — make World, Goals, Executions,
   Effects, Policies and devices inspectable/manageable as a product.
5. **Cloud/control plane** — managed deployment and infrastructure after the
   Runtime contract warrants it.

These are directions, not implementation claims.

---

## 18. Architectural invariants

1. No subsystem invents its own execution lifecycle.
2. `Execution` is the canonical operational source of truth.
3. Capabilities are explicit.
4. Policy narrows authority using runtime/world context.
5. Infrastructure remains behind adapters.
6. AI is Compute, never ambient authority.
7. Effects are traceable attempted actions.
8. Observations are evidence, not commands.
9. State is explicit.
10. Retries are safe or explicitly non-idempotent.
11. Human waiting/approval is first-class runtime state.
12. Edge/devices remain external participants in the same Runtime.
13. Network transport never bypasses identity/capability/policy enforcement.
14. Local development remains zero-infrastructure by default.
15. Cloud remains optional.
16. Protocol semantics survive infrastructure and language changes.
17. The developer surface remains smaller than the implementation surface.
18. Failure and restart are normal conditions.
19. Physical actions are governed Effects and require observed evidence before
    World truth changes.
20. Every new primitive requires recurring architectural justification.

---

## 19. Final principle

> Are we adding another feature, or discovering a primitive/composition that
> makes many future features simpler?

The second is the objective.

**Build the Runtime first. Build the ecosystem second. Let the primitives
outlive the implementations.**
