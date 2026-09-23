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

The post-Sprint-28 repository now includes:

- reactive/server-driven Python UI and **Design System 3** with premium light/dark
  zero-custom-CSS defaults and Theme-authoritative branding;
- routing/APIs, data, auth/security and explicit infrastructure adapters;
- Voodoo Store as the zero-config durable application substrate;
- Store-backed data/models, jobs/queues, scheduling, events, objects and Runtime state;
- canonical `ExecutionEngine`, durable recovery and HITL;
- capability security and contextual operational Policy;
- Agents, tools, providers, MCP integration and persistent Memory;
- Ontology/World Model with `Entity`, `Relationship` and `Observation`;
- durable Goal Runtime and bounded adaptive supervision;
- Edge device identity/auth/protocol/effect lifecycle backed by the Runtime Store;
- governed distributed execution with replay/idempotency and WAITING/HITL;
- authenticated node membership, discovery, health, placement, leases and bounded
  failover;
- language-neutral JSON Schema protocol surface;
- operational runtime/system UI components;
- clean-install release gates proving the default Runtime lifecycle does not require
  optional SQL infrastructure.

The latest published release is **v3.0.0** (2026-09-21), and the current
`main` architecture baseline is the same 3.0 release commit. The 3.0 clean break
removed compatibility-only 2.x facades, contracted the package-root API, and completed
repository semantic-ownership convergence. `SPRINT_PLAN.md` remains the implementation
source of truth; this document defines direction rather than claiming future work already
exists.

## Completed convergence — Sprints 27 and 28

Sprint 27 closed the adaptive operational loop:

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

Sprint 28 then made the infrastructure model operational:

```text
Application
    ↓
Voodoo Runtime
    ↓
Identity → Capability + Policy → Execution
    ↓
Data / Jobs / Scheduler / Events / Objects / Goal / Workflow / HITL
    ↓
application.vstore
```

and established topology-transparent multi-node execution:

```text
                         Application
                             ↓
                       Voodoo Runtime
                             ↓
                       Runtime Fabric
                    /           |           \
                 Node A       Node B       Node C
                    |           |           |
                A.vstore    B.vstore    C.vstore
```

Each Store remains node-local. Voodoo does not claim Store-file multi-writer semantics,
distributed consensus, global exactly-once execution or globally serializable
transactions.

Completion records:

- [`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md)
- [`docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`](docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)

## Developer-experience law

Voodoo must preserve progressive complexity. `voodoo create` should produce a
useful local application without requiring World, Planner, AI or distributed
infrastructure. Those capabilities compose in only when the problem needs them.

A fresh default application should require no external database, queue, object service or
event server. Its durable substrate is `.voodoo/application.vstore`. External
PostgreSQL/SQLite/Redis/S3 infrastructure is an explicit adapter choice, not a hidden
fallback.

The 3.0 import law lives in [`docs/public-api-3.md`](docs/public-api-3.md).
The package root is the intentionally small application happy path; it is not a
compatibility catalog. Subsystem APIs belong to their semantic namespaces such as
`voodoo.ui`, `voodoo.runtime`, `voodoo.world`, `voodoo.edge` and
`voodoo.protocol`. Compatibility-only 2.x paths removed by 3.0 must not be
reintroduced as duplicate owners.

## UI and Design System

Voodoo UI is part of the Runtime developer experience, not a separate frontend
framework. The native visual layer is Design System 3:

- intentional Voodoo purple identity by default;
- premium light/dark surfaces;
- responsive page geometry and component defaults;
- accessible focus and reduced-motion behavior;
- Theme-authoritative customization for branded applications;
- no custom CSS required for the normal application path.

Themes remain semantic. DS3 visual tokens derive from the public `Theme` contract rather
than becoming a second, hard-coded theming system. Tailwind remains an opt-in adapter,
not a framework dependency.

## Store-first infrastructure

Store owns durable mechanics; Runtime owns semantics, authority and intelligence.

```text
Voodoo Runtime
    |
    +-- Model / Data
    +-- Jobs / Queue
    +-- Scheduler / Cron / Triggers
    +-- Events / durable outbox
    +-- Objects
    +-- Execution / Goal / Workflow / HITL
    +-- Identity
    +-- Edge state
    |
    v
RuntimeStore
    |
application.vstore
```

The Store-first path must remain clean of accidental optional-adapter imports. Release
quality therefore includes a wheel-level clean-install gate with optional SQLite blocked.

Future Store evolution may expose richer native Topics/Streams, Objects and replication,
but Framework semantics must not pretend unsupported guarantees exist.

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

Sprint 28 adds governed node membership, health, discovery, placement, ownership,
leases and bounded retry/failover while preserving node-local Stores.

Voodoo still does not claim distributed consensus or global exactly-once execution.

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

## Next-phase selection gate

No Sprint 29 is declared merely because Voodoo 3.0 is published. The next numbered
sprint should be chosen after a product/architecture review that applies real pressure
to the 3.0 Runtime and identifies the smallest coherent capability set that unlocks the
next class of products.

Candidate directions, roughly by dependency and validation value, are:

1. **Protocol/SDK productization** — prove the language-neutral boundary with a real
   non-Python client.
2. **Real Edge reference canary** — run the closed loop against an ESP32/robot and expose
   operational gaps in identity, reconnect, replay, telemetry and evidence.
3. **Multi-device mission/fleet orchestration** — only after the single-device canary is
   reliable.
4. **Studio / operational product surface** — inspect and operate World, Goals,
   Executions, devices and nodes without inventing parallel semantics.
5. **Managed Runtime / cloud control plane** — deployment/fleet/operator services above
   the existing Runtime contracts.
6. **3.x reference product validation** — build a real application that pressure-tests
   the public Runtime model end to end and exposes the smallest next capability gap.

A candidate wins only if it validates existing primitives, has recurring product value,
creates a strong end-to-end acceptance target and makes later work simpler.

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
21. Scaling changes deployment topology, not application architecture.
22. Store mechanics never become a second authority model.

## Final principle

> Are we adding another feature, or discovering a primitive/composition that
> makes many future features simpler?

The second is the objective.

**Build the Runtime first. Build the ecosystem second. Let the primitives
outlive the implementations.**
