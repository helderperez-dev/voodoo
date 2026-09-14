# Voodoo — Implementation Sprint Tracker

Source architecture: [`ROADMAP.md`](ROADMAP.md).

This file is the **current source of truth for implementation progress**.
Detailed historical plans live in Git history and under `docs/sprints/`.

> Updated 2026-09-13 after starting Sprint 28 — Runtime Infrastructure Convergence.

## North Star

**Voodoo is the programmable runtime for adaptive applications and operational
systems.**

```text
World → Observation → Goal → Intent → Plan → Capability + Policy
     → Execution → Effect → Participant → ACK → Observation → World
```

Core laws:

- exactly one Voodoo Runtime;
- `Execution` is canonical operational truth;
- AI is Compute, not a second runtime;
- authority is capability-mediated and may be narrowed by contextual Policy;
- `Observation` is evidence about what actually happened;
- an `Effect` is attempted action, not automatically observed truth;
- Edge/devices and remote nodes are governed participants in the same Runtime model;
- Voodoo Store is the target default durable application infrastructure;
- local-first remains the default;
- scaling changes deployment topology, not application architecture.

## Current position

| Item | State |
|---|---|
| Latest published release | **v2.6.2** |
| Package version on `main` | **2.6.2** |
| Sprints through 23 | **DONE** |
| Sprint 24 — Agency Foundation | **DONE** |
| Sprint 25 — UI Magic | **DONE** |
| Sprint 26 — Trusted Distributed Execution Fabric | **DONE** |
| Sprint 27 — Runtime Convergence & 3.0 Readiness | **DONE** |
| Sprint 28 — Runtime Infrastructure Convergence | **ACTIVE — 28.1 Store provider foundation** |
| Release checkpoint | release cutting remains a separate explicit operation |

Sprint 28 execution plan:
[`docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`](docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)

---

## Sprint 24 — Agency Foundation, Ontology & World Model

**Status: DONE**

Plan: [`docs/sprint-24-agency-foundation.md`](docs/sprint-24-agency-foundation.md)

Delivered Ontology/World Model, durable World storage, Agent/runtime truth,
adaptive agency, contextual Policy, world-aware Execution, Goal Runtime,
durable Goal recovery and read-only Operational Runtime projection.

Implementation evidence: PRs #20, #22–#25, #27–#28 and #31–#32.

---

## Sprint 25 — Voodoo UI Magic

**Status: DONE · closed 2026-09-13**

Plans/evidence:

- [`docs/sprints/SPRINT_25_UI_MAGIC.md`](docs/sprints/SPRINT_25_UI_MAGIC.md)
- [`docs/sprints/SPRINT_25_PROGRESS.md`](docs/sprints/SPRINT_25_PROGRESS.md)

Delivered Python-callable browser events, reactive dependency rediscovery,
context-preserving DOM patches, same-origin soft navigation, Design System 2,
Product Components, Runtime/System Components and an acceptance application
with zero application JavaScript and zero custom CSS.

Implementation path: PRs #33, #37–#41.

---

## Sprint 26 — Trusted Distributed Execution Fabric

**Status: DONE · closed 2026-09-13**

Completion record:
[`docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md`](docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md)

Delivered governed remote execution where network transport can move an Intent but
cannot move execution outside the Runtime authority boundary.

Implementation path: PRs #43–#46, #49–#50.

---

## Sprint 27 — Runtime Convergence & 3.0 Readiness

**Status: DONE · closed 2026-09-13**

Execution/completion record:
[`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md)

Delivered Edge → World evidence ingestion, context-aware planning, Protocol
convergence, 3.0 public API law, canonical operational closed-loop acceptance,
documentation truth reconciliation and release-quality gates.

Primary implementation: PR #52 (`e73a718`).

---

# Sprint 28 — Runtime Infrastructure Convergence

**Status: ACTIVE · started 2026-09-13**

Execution plan:
[`docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`](docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)

Sprint 28 connects the infrastructure seams deliberately left open by prior sprints.
Its target is a Voodoo application that starts with one Runtime and one local
`.vstore`, while retaining an architecture that can transparently grow into multiple
authenticated Voodoo Nodes.

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Identity -> Capability -> Policy -> Execution
    +-- Data / Jobs / Scheduler / Events / Objects / Workflow
    |
    v
Voodoo Store (default)
    |
application.vstore
```

SQLite, PostgreSQL, Redis, S3 and future infrastructure become explicit adapters.
Store owns durable mechanics; Runtime owns semantics, authority and intelligence.

Multi-node direction:

```text
same application semantics
        |
        v
   Runtime Router
     /    |    \
 node-a node-b node-c
   |      |      |
 a.vstore b.vstore c.vstore
```

Distributed ownership comes before distributed Store replication. Sprint 28 does not
claim shared-file multi-writer semantics, distributed consensus or global
exactly-once.

| Slice | Goal | State |
|---|---|---|
| 28.1 | Store provider foundation and lifecycle boundary | **ACTIVE** |
| 28.2 | Voodoo Store zero-config default / legacy defaults become adapters | TODO |
| 28.3 | Data/Model Store integration | TODO |
| 28.4 | Durable Jobs/Queues Store integration | TODO |
| 28.5 | Scheduler/Cron/Triggers Store integration | TODO |
| 28.6 | Events/Streams/Outbox Store integration | TODO |
| 28.7 | ObjectStore integration | TODO |
| 28.8 | Execution/Workflow/HITL durability | TODO |
| 28.9 | Voodoo Identity semantic foundation | TODO |
| 28.10 | Identity/Actor/Capability/Policy convergence | TODO |
| 28.11 | Unified cross-domain transactions | TODO |
| 28.12 | Node Identity and authenticated membership | TODO |
| 28.13 | Node discovery/health/membership lifecycle | TODO |
| 28.14 | Transparent routing and distributed ownership | TODO |
| 28.15 | Capability/Policy/load-aware placement | TODO |
| 28.16 | Failure detection, leases and bounded failover | TODO |
| 28.17 | Mesh/Protocol node-fabric convergence | TODO |
| 28.18 | External adapter compatibility | TODO |
| 28.19 | CLI/DX | TODO |
| 28.20 | Legacy migration/compatibility | TODO |
| 28.21 | Single-node zero-infrastructure acceptance | TODO |
| 28.22 | Multi-node topology-transparent acceptance | TODO |
| 28.23 | Edge/distributed closed-loop acceptance and closure | TODO |

### Current work — 28.1

- audit current provider/default assumptions;
- audit actual `voodoo-store` Python binding coverage;
- define a Runtime-owned Store/provider contract;
- implement deterministic provider lifecycle;
- add contract/failure tests before switching defaults.

---

## Quality rules

For every implementation sprint:

1. branch from current `main`;
2. preserve one Runtime and one canonical `Execution` lifecycle;
3. add failure-path tests for durability/security claims;
4. keep the base install local-first and zero-infrastructure;
5. run Ruff format/lint, Python 3.12, Python 3.13, security analysis and the
   declared type-check boundary;
6. merge only with required gates green;
7. update trackers only after implementation truth exists;
8. treat release cutting as an explicit operation, never as an implied side effect
   of merge.

## References

- [`ROADMAP.md`](ROADMAP.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`docs/public-api-3.md`](docs/public-api-3.md)
- [`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md)
- [`docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`](docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)
