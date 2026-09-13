# Voodoo — Implementation Sprint Tracker

Source architecture: [`ROADMAP.md`](ROADMAP.md).

This file is the **current source of truth for implementation progress**.
Detailed historical plans live in Git history and under `docs/sprints/`.

> Updated 2026-09-13 after completion of Sprints 24, 25 and 26.

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
| Sprint 24 — Agency Foundation | **DONE on `main`, post-v2.6.2** |
| Sprint 25 — UI Magic | **DONE on `main`, post-v2.6.2** |
| Sprint 26 — Trusted Distributed Execution Fabric | **DONE on `main`, post-v2.6.2** |
| Next implementation sprint | **Not selected — architectural review required first** |
| Release checkpoint | `main` is substantially ahead of published v2.6.2 |

Sprint completion and public release state are intentionally separate.

---

## Sprint 24 — Agency Foundation, Ontology & World Model

**Status: DONE**

Plan: [`docs/sprint-24-agency-foundation.md`](docs/sprint-24-agency-foundation.md)

Delivered the durable operational loop:

```text
World
  ↓
Goal / Intent
  ↓
Capability + contextual Policy
  ↓
Execution
  ↓
Effect
  ↓
Observation
  ↓
World
```

Key results include Ontology/World Model, durable World storage, canonical Agent
lineage, adaptive agency, contextual Policy, world-aware Execution, Goal Runtime,
durable Goal recovery and the read-only Operational Runtime projection.

Implementation evidence: PRs #20, #22–#25, #27–#28 and #31–#32.

---

## Sprint 25 — Voodoo UI Magic

**Status: DONE · closed 2026-09-13**

Plans/evidence:

- [`docs/sprints/SPRINT_25_UI_MAGIC.md`](docs/sprints/SPRINT_25_UI_MAGIC.md)
- [`docs/sprints/SPRINT_25_PROGRESS.md`](docs/sprints/SPRINT_25_PROGRESS.md)

Delivered:

- Python-callable events with opaque browser bindings;
- reactive dependency rediscovery and coalesced invalidation;
- context-preserving DOM patches and same-origin soft navigation;
- normalized Component API and Design System 2;
- Product Components;
- Voodoo Runtime/System Components;
- acceptance application with zero application JavaScript and zero custom CSS.

Implementation path: PRs #33, #37–#41.

---

## Sprint 26 — Trusted Distributed Execution Fabric

**Status: DONE · closed 2026-09-13**

Completion record:
[`docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md`](docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md)

Delivered path:

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

| Slice | Result | Evidence |
|---|---|---|
| 26.1 | Canonical remote request + lineage | PR #43 |
| 26.2 | Governed remote ingress; direct callable bypass removed | PR #43 · `37a740c7` |
| 26.3 | Remote server-side authority + Policy parity | PR #44 · `48407141` |
| 26.4 | Replay/idempotency + SQLite durability | PR #45 · `8ee68dfd` |
| 26.5 | Structured outcomes + distributed WAITING/HITL | PR #46 · `849c5e28` |
| 26.6 | Trusted participant resolver/authentication seam | PR #49 · `44e0afc6` |
| 26.7 | Zero-infrastructure two-node acceptance matrix | PR #50 · `696bf7f5` |

Sprint 26 preserves the invariant:

> **The network may move an Intent. It may never move execution outside the Runtime.**

Explicit non-claims remain: no production PKI/OIDC/mTLS platform, no global
exactly-once delivery claim, no consensus, no fleet scheduler, no ESP32 reference
firmware, no Edge→World semantic ingestion and no cloud control plane.

---

## Current known gaps for the next review

These are **review inputs, not a pre-decided Sprint 27**:

- Edge semantic events → `Observation` / World Model ingestion and closed physical
  action/observation loop;
- World intelligence beyond direct observations: temporal facts, confidence,
  beliefs/derived state and richer reasoning context;
- Goal planning/replanning beyond current bounded adaptive orchestration;
- cognitive memory retrieval/reflection/consolidation;
- protocol/SDK boundary for non-Python participants;
- multi-device/fleet/mission orchestration;
- physical reference firmware and hardware validation;
- developer experience consolidation and public API simplification;
- Voodoo Studio / Runtime operational product surface;
- release/package strategy for the large body of work now ahead of v2.6.2;
- cloud/control-plane productization only after the Runtime contract warrants it.

## Next action

**Do not start a new numbered sprint yet.**

Perform a repository-wide architectural review covering:

1. what is truly implemented versus still aspirational;
2. where Voodoo now differentiates from app frameworks, agent frameworks,
   workflow engines and IoT runtimes;
3. the highest-risk remaining architectural gaps;
4. developer experience and API complexity after Sprints 24–26;
5. the strongest software-only and physical canary systems we can build now;
6. the correct next sprint/release sequence.

Only after that review should the next implementation sprint be named.

## Quality rules

For every future implementation sprint:

1. branch from current `main`;
2. preserve one Runtime and one canonical `Execution` lifecycle;
3. add failure-path tests for every durability/security claim;
4. keep the base install local-first and zero-infrastructure;
5. run Ruff format/lint, Python 3.12, Python 3.13 and CodeQL;
6. merge only with gates green;
7. update trackers only after implementation truth exists;
8. treat release cutting as an explicit operation, never as an implied side
   effect of merge.

## References

- [`ROADMAP.md`](ROADMAP.md)
- [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
- [`docs/sprint-24-agency-foundation.md`](docs/sprint-24-agency-foundation.md)
- [`docs/sprints/SPRINT_25_UI_MAGIC.md`](docs/sprints/SPRINT_25_UI_MAGIC.md)
- [`docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md`](docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md)
- Git history for detailed legacy Sprint 1–23 scope.
