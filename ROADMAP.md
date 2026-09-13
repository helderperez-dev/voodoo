# VOODOO — MASTER ROADMAP

## A unified architecture and engineering direction for the Voodoo Runtime

| Field | Value |
|---|---|
| Status | Living architectural source of truth |
| Repository | `helderperez-dev/voodoo` |
| Implementation tracker | [`SPRINT_PLAN.md`](SPRINT_PLAN.md) |

## North Star

> **Voodoo is the programmable runtime for adaptive applications and operational systems.**

The objective is not to build the Python framework with the most features. It
is to make a small set of durable primitives express software, AI, human
workflows, distributed participants and increasingly physical systems through
one coherent runtime.

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

`Compute`, `Time`, `Resource` and `Constraint` govern execution. Cross-cutting
concepts include `Identity`, `Event`, `Relationship`, `Policy`, `Observation`
and `Telemetry`.

An `Execution` is meaningful work worth observing, authorizing, recovering,
accounting for, waiting on or reasoning about. It is not every function call.

## Architectural thesis

Modern systems fragment one problem across frontend, backend, database, queues,
workers, AI SDKs, workflow engines, messaging, observability and device stacks.
Voodoo makes those boundaries converge when needed instead of giving each one a
private lifecycle and security model.

```text
UI / API / Worker / Agent / Human / Remote node / Device
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

AI is Compute. Devices are external participants. Humans are legitimate
participants. None of them owns a second Runtime.

## The two histories

```text
EXECUTION HISTORY
Intent → Execution → Effect → Result / Failure / Approval / Recovery

WORLD HISTORY
Entity → Observation → Relationship → projected state / source / confidence / time
```

They are linked through lineage such as `execution_id` and `trace_id`, but they
answer different questions. Execution history says what the system tried to do
and why. World history says what evidence reports actually happened.

> **Effect != Observation.**

## Current repository position

Implemented foundations include:

- reactive/server-driven Python UI and Design System 2;
- routing/APIs, data, auth/security and infrastructure adapters;
- workers, queues, scheduler, object storage and event infrastructure;
- canonical `ExecutionEngine`, durable recovery and HITL;
- capability security and contextual operational Policy;
- Agents, tools, providers, MCP integration and persistent Memory;
- Ontology/World Model with `Entity`, `Relationship` and `Observation`;
- durable Goal Runtime and bounded adaptive supervision;
- Edge device identity/auth/protocol/effect lifecycle;
- governed distributed execution with replay/idempotency and WAITING/HITL;
- language-neutral JSON Schema protocol surface;
- operational runtime/system UI components.

The repository is therefore materially beyond the earlier “Python web
framework” phase. `SPRINT_PLAN.md` remains the implementation source of truth;
this document defines direction rather than claiming future work already exists.

## Current convergence target — Sprint 27

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

Sprint 27 closes this loop and prepares the contracts for the next phase. See
[`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md).

## Developer-experience law

Voodoo must preserve progressive complexity. `voodoo create` should produce a
useful local application without requiring World, Planner, AI or distributed
infrastructure. Those capabilities compose in only when the problem needs them.

The 3.0 import law lives in [`docs/public-api-3.md`](docs/public-api-3.md).
Package-root imports are a compatibility/happy-path facade; subsystem catalogs
belong to their semantic namespaces such as `voodoo.ui`, `voodoo.runtime`,
`voodoo.world`, `voodoo.edge` and `voodoo.protocol`.

## World and operational intelligence

The World layer represents what the runtime currently believes about operational
reality using evidence and provenance rather than blind mutation.

- `Entity` — stable identity.
- `Relationship` — typed directed relationship.
- `Observation` — append-only evidence with source, confidence and event time.
- projected State — the latest accepted evidence.
- `Effect` — attempted action, not evidence.
- `WorldSnapshot` — bounded reasoning/policy projection.

Future World intelligence may add temporal facts, derived state, belief
management and richer confidence reasoning. Those are next-phase intelligence
features, not excuses to blur the direct evidence model.

## Agency

Agency is built from runtime primitives rather than privileged AI authority.

```text
Reason freely.
Act through capabilities.
Observe consequences.
Continue from state.
```

A durable autonomous participant needs identity, state/memory, goals/intents,
capabilities, constraints/policy, execution/effects, observations, time,
resources, delegation/human participation and restart recovery.

`GoalRuntime` and `AdaptiveSupervisor` provide bounded orchestration. Planner
selection may consume current World context, but authority still belongs to
Capability + Policy.

## Embodiment / Edge

Edge is a boundary into the same Runtime:

```text
Sensor / Device → Edge → Observation / Intent → World + Runtime
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

Physical actions remain traceable. Intermittent connectivity, replay and
idempotency are normal operating conditions. Large robot/fleet products remain
deferred until this semantic loop is proven by small reference systems.

## Distributed Runtime

Network transport never grants authority. Remote work resolves identity, enters
an Intent, passes server-side Capability + Policy, and executes through the same
`ExecutionEngine`. Remote outcomes preserve COMPLETED / FAILED / WAITING rather
than inventing a transport-specific lifecycle.

Voodoo does not claim distributed consensus or global exactly-once execution.

## Protocol and SDK strategy

Python remains the primary Runtime implementation, but Python internals are not
the interoperability boundary. `voodoo.protocol` provides JSON-friendly
semantic schemas for runtime, World, Goal and distributed-execution concepts.

Future TypeScript, Go, Rust and embedded SDKs should primarily be protocol
clients rather than alternative Runtime implementations.

## Memory

Memory is contextual recall, not business truth and not the World Model. Current
layers provide Working, Episodic, Durable and Semantic storage/search. Cognitive
consolidation, reflection and advanced relevance are deliberately next-phase
intelligence concerns; Voodoo should not become a vector-database framework.

## Cloud and product surfaces

Potential future products include Runtime managed infrastructure, Studio,
Identity productization, Store/ecosystem packaging, deployment, logs, domains
and rollback. These surfaces must sit **above** Runtime contracts and must not
duplicate Execution, Identity, Policy or World semantics. Cloud remains
optional.

## Long-horizon pressure test

These horizons are architecture tests, not literal predictions.

- **2030:** Voodoo should read as an application/runtime platform, not merely a
  Python web framework.
- **2050:** the primitives should still describe distributed digital and physical
  operational systems.
- **2100:** identity, intent, capability, constraint, execution, effect,
  observation and state should remain coherent even if compute participants have
  changed completely.

## Architectural lineage

Voodoo synthesizes enduring principles rather than copying products:

- Palantir — ontology and operational entities;
- Anduril/Lattice — sensors → world state → intent → execution → feedback;
- NASA/JPL — autonomy, reliability, telemetry and recovery;
- SpaceX — vertical control of critical interfaces;
- Erlang/OTP — failure and supervision as first-class concepts;
- cloud-native systems — adapters and replaceable infrastructure;
- robotics/industrial systems — closed-loop action and observation.

## What Voodoo must not become

Voodoo must not become a React clone, AI/prompt-only framework, MCP framework,
Kubernetes wrapper, IoT broker, robotics-middleware replacement, giant
miscellaneous standard library, cloud lock-in product, runtime where every
helper call is an Execution, or system where AI receives ambient unrestricted
authority.

## Candidate phases after convergence

The exact next numbered sprint is selected only after Sprint 27 acceptance.
Candidate directions, roughly by dependency, are:

1. protocol/SDK productization;
2. small real ESP32/robot reference canary;
3. multi-device mission/fleet orchestration;
4. Studio / operational product surface;
5. managed Cloud/control plane.

These are directions, not implementation claims.

## Architectural invariants

1. No subsystem invents its own execution lifecycle.
2. `Execution` is canonical operational truth.
3. Capabilities are explicit.
4. Policy narrows authority using runtime/world context.
5. Infrastructure remains behind adapters.
6. AI is Compute, never ambient authority.
7. Effects are traceable attempted actions.
8. Observations are evidence, not commands.
9. State is explicit.
10. Retries are safe or explicitly non-idempotent.
11. Human waiting/approval is first-class Runtime state.
12. Edge/devices remain external participants in the same Runtime.
13. Network transport never bypasses identity/capability/policy enforcement.
14. Local development remains zero-infrastructure by default.
15. Cloud remains optional.
16. Protocol semantics survive infrastructure and language changes.
17. The developer surface remains smaller than the implementation surface.
18. Failure and restart are normal conditions.
19. Physical actions require observed evidence before World truth changes.
20. Every new primitive requires recurring architectural justification.

## Final principle

> Are we adding another feature, or discovering a primitive/composition that
> makes many future features simpler?

The second is the objective.

**Build the Runtime first. Build the ecosystem second. Let the primitives
outlive the implementations.**
