# Voodoo — Implementation Sprint Tracker

Source architecture: [`ROADMAP.md`](ROADMAP.md).

This file is the **current source of truth for implementation progress**.
Detailed historical plans live in Git history and under `docs/sprints/`.

> Updated 2026-09-13 during Sprint 27 — Runtime Convergence & 3.0 Readiness.

## North Star

**Voodoo is the programmable runtime for adaptive applications and operational
systems.**

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

`Compute`, `Time`, `Resource` and `Constraint` govern execution.

Core laws:

- exactly one Voodoo Runtime;
- `Execution` is canonical operational truth;
- AI is Compute, not a second runtime;
- authority is capability-mediated and may be narrowed by contextual Policy;
- `Observation` is evidence about what actually happened;
- an `Effect` is attempted action, not automatically observed truth;
- Edge/devices are external participants in the same Runtime;
- local-first remains the default.

## Current position

| Item | State |
|---|---|
| Latest published release | **v2.6.2** |
| Package version on `main` | **2.6.2** |
| Sprints through 23 | **DONE** |
| Sprint 24 — Agency Foundation | **DONE** |
| Sprint 25 — UI Magic | **DONE** |
| Sprint 26 — Trusted Distributed Execution Fabric | **DONE** |
| Sprint 27 — Runtime Convergence & 3.0 Readiness | **ACTIVE** |
| Release checkpoint | `main` remains ahead of published v2.6.2; release is a separate operation |

Sprint completion and public release state are intentionally separate.

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

Delivered the governed remote path:

```text
Remote participant
  ↓
Credential / participant evidence
  ↓
Resolved identity
  ↓
RemoteExecutionRequest
  ↓
Intent
  ↓
Server-side authority
  ↓
Capability + contextual Policy
  ↓
ExecutionEngine
  ↓
COMPLETED / FAILED / WAITING
  ↓
RemoteExecutionOutcome
```

Implementation path: PRs #43–#46, #49–#50.

> **The network may move an Intent. It may never move execution outside the Runtime.**

---

# Sprint 27 — Runtime Convergence & 3.0 Readiness

**Status: ACTIVE**

Execution plan:
[`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md)

Sprint 27 exists to connect the mature pieces already present rather than add
unrelated surface area.

Target closed loop:

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

| Slice | Goal | State |
|---|---|---|
| 27.1 | Edge → World semantic evidence ingestion | **IN IMPLEMENTATION** |
| 27.2 | World-aware Goal/planning convergence | **IN IMPLEMENTATION** |
| 27.3 | Protocol convergence for World/Goal/distributed semantics | **IN IMPLEMENTATION** |
| 27.4 | 3.0 public API / import law | **IN IMPLEMENTATION** |
| 27.5 | Canonical examples + operational closed-loop canary | **IN IMPLEMENTATION** |
| 27.6 | Documentation/repository truth reconciliation | **IN IMPLEMENTATION** |
| 27.7 | Warning-zero/type-check release-quality gate | **TODO** |
| 27.8 | Final acceptance, tracker closure and next-phase review | **TODO** |

### Definition of Done

Sprint 27 is complete only when a Voodoo system can:

1. ingest device evidence through Edge into the World Model;
2. preserve source/time/trace/execution lineage and duplicate safety;
3. use explicit operational World context while choosing already-authorized
   compute participants;
4. pursue a durable Goal through the canonical Runtime;
5. issue Effects without confusing attempted action with observed truth;
6. close the loop through device ACK/evidence → Observation → World;
7. expose World/Goal/remote semantics through the language-neutral Protocol;
8. teach the current callable-UI/runtime semantics through canonical examples;
9. present one truthful architecture across README, Roadmap and sprint docs;
10. pass the release-quality gates for formatting, lint, Python 3.12/3.13,
    security analysis and an explicit type-check boundary.

### Explicit next-phase work, not Sprint 27 correctness gaps

- production PKI/OIDC/mTLS identity platform;
- generated full TypeScript/Go/Rust SDK families;
- fleet scheduling / large multi-device mission orchestration;
- production cloud control plane;
- large physical robot reference implementation;
- distributed consensus or global exactly-once claims.

The semantic seams for those systems must be stable before Sprint 27 closes.

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
8. treat release cutting as an explicit operation, never as an implied side
   effect of merge.

## References

- [`ROADMAP.md`](ROADMAP.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`docs/public-api-3.md`](docs/public-api-3.md)
- [`docs/sprint-24-agency-foundation.md`](docs/sprint-24-agency-foundation.md)
- [`docs/sprints/SPRINT_25_UI_MAGIC.md`](docs/sprints/SPRINT_25_UI_MAGIC.md)
- [`docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md`](docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md)
- [`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md)
