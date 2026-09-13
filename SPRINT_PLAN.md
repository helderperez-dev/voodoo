# Voodoo — Implementation Sprint Tracker

Source architecture: [`ROADMAP.md`](ROADMAP.md).

This file is the **current source of truth for implementation progress**. Detailed
historical scope for the older runtime sprints remains available in Git history;
new large initiatives keep their executable plans under `docs/sprints/` or a
purpose-specific sprint document.

> Reconciled on 2026-09-13 after the Agency Foundation and UI Magic work landed.
> The previous version of this tracker still described Sprint 24 as a future
> ESP32-only sprint and therefore no longer represented the repository.

## North Star

**Voodoo is the programmable runtime for adaptive applications and operational
systems.**

The runtime model is:

```text
Entity → State → Intent → Capability → Execution → Effect → State
```

with `Compute`, `Time`, `Resource`, and `Constraint` governing execution.

The operational rules are:

- there is exactly one Voodoo Runtime;
- `Execution` is the canonical operational source of truth;
- AI is a form of Compute, not a second runtime;
- authority is capability-mediated and may be narrowed by contextual policy;
- `Observation` is evidence about what actually happened in the world;
- an `Effect` records an attempted side effect and does not automatically become
  observed truth;
- Edge devices are external participants in the same runtime, not a second
  execution engine;
- local-first remains the default: SQLite/local filesystem with production
  adapters behind contracts.

## Current Position

| Item | State |
|---|---|
| Latest published release | **v2.6.2** |
| Package version on `main` | **2.6.2** |
| Sprints through 23 | **DONE** |
| Sprint 24 — Agency Foundation | **DONE on `main`, post-v2.6.2** |
| Sprint 25 — UI Magic | **DONE on `main`, post-v2.6.2** |
| Next implementation sprint | **Sprint 26 — Trusted Distributed Execution Fabric** |
| Release checkpoint | Sprints 24/25 are implemented but not yet included in a release newer than v2.6.2 |

Do not infer release state from sprint completion. A sprint may be merged into
`main` before the next public release is cut.

---

## Recent completed work

### Sprint 23 — Edge Protocol

**Status: DONE · released in the 2.6.x line**

Delivered the transport-independent external-device boundary: enrollment,
credentials, sessions, capabilities, heartbeat, events, state sync, Effects,
ACKs, idempotency and HTTP/MQTT semantic parity.

Important invariant: Edge is a participant in the Runtime. It does not own a
second `ExecutionEngine`.

Physical ESP32 firmware remains a reference implementation concern, not the
architectural definition of Edge.

### Sprint 24 — Agency Foundation, Ontology & World Model

**Status: DONE on `main`**

Execution plan: [`docs/sprint-24-agency-foundation.md`](docs/sprint-24-agency-foundation.md)

| Milestone | Delivered | PR |
|---|---|---:|
| 24.1 | Ontology + World Model kernel (`Entity`, `Relationship`, `Observation`) | #20 |
| 24.2 | Agent/runtime truth, canonical lineage and Task upstream propagation | #23 |
| 24.3 | Durable SQLite World Store | #22 |
| 24.4 | Bounded adaptive agency | #24 |
| 24.5 | Contextual operational policy | #25 |
| 24.6 | World-aware execution and observed-outcome lineage | #27 |
| 24.7 | Goal-driven operational runtime | #28 |
| 24.8 | Durable Goal agency and restart recovery | #31 |
| 24.9 | Read-only operational runtime projection/UI | #32 |

The resulting control loop now has durable first-class pieces for:

```text
World state
  ↓
Goal / Intent
  ↓
Capability + Policy
  ↓
Execution
  ↓
Effect
  ↓
Observed outcome
  ↓
World state
```

Two histories remain intentionally distinct:

```text
EXECUTION HISTORY
Intent → Execution → Effect → Result / Failure / Approval / Recovery

WORLD HISTORY
Entity → Observation → Relationship → projected state / source / confidence / time
```

### Sprint 25 — Voodoo UI Magic

**Status: DONE on `main` · closed 2026-09-13**

Plans and evidence:

- [`docs/sprints/SPRINT_25_UI_MAGIC.md`](docs/sprints/SPRINT_25_UI_MAGIC.md)
- [`docs/sprints/SPRINT_25_PROGRESS.md`](docs/sprints/SPRINT_25_PROGRESS.md)

Delivered:

- Python-callable event bindings with opaque browser identities;
- semantic `data-vd-*` interaction bindings instead of inline JavaScript;
- reactive dependency rediscovery and coalesced state invalidation;
- context-preserving DOM patching;
- same-origin soft navigation with browser history;
- normalized component APIs and Design System 2;
- product components (`DataTable`, `Timeline`, `InspectorPanel`, `CommandBar`,
  metrics/status/empty states, etc.);
- Voodoo runtime/system components for Execution, Agent, Device, World,
  Observation, Policy, Capability and telemetry concepts;
- the `examples/ui_magic/main.py` acceptance application with zero application
  JavaScript and zero custom CSS.

Final implementation path: PRs #33, #37, #38, #39, #40 and documentation close
PR #41. CI validated Ruff format/lint, Python 3.12, Python 3.13 and CodeQL.

---

# NEXT — Sprint 26: Trusted Distributed Execution Fabric

**Status: PLANNING**

Detailed execution plan:
[`docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md`](docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md)

## Why this is next

The Runtime, World Model, Goal/Intent lifecycle, policy boundary and Edge
protocol now exist, but distributed Mesh operations still need one canonical
security/execution path.

The target remote path is:

```text
Remote participant
  ↓
Authenticated identity
  ↓
Remote Intent envelope
  ↓
Capability + contextual Policy
  ↓
ExecutionEngine
  ↓
Effect / Result
  ↓
correlated remote response + telemetry
```

A remote call must never become a privileged shortcut around the same Runtime
boundary used by local execution.

## Sprint 26 architectural laws

1. **No second execution lifecycle.** Remote work enters the existing
   `ExecutionEngine`.
2. **Identity before authority.** Every governed remote execution has an actor.
3. **Capability before compute.** Mesh transport does not grant authority.
4. **Policy sees the same World.** Remote actions use the same contextual policy
   path as local actions.
5. **Transport is not semantics.** HTTP/WebSocket/MQTT/other transports may carry
   messages, but the protocol contract is stable above them.
6. **Replay is explicit.** Stable message IDs, correlation IDs and idempotency are
   required before distributed side effects can be trusted.
7. **Lineage survives the network.** Trace, parent execution, actor and target
   identity remain inspectable end-to-end.
8. **Local-first remains valid.** A developer can exercise the complete contract
   without external infrastructure.

## Planned slices

| Slice | Goal | Status |
|---|---|---|
| 26.1 | Canonical remote Intent/request envelope + actor/correlation lineage | TODO |
| 26.2 | Mesh ingress adapter that always enters `ExecutionEngine` | TODO |
| 26.3 | Remote capability and contextual Policy enforcement | TODO |
| 26.4 | Idempotency, replay protection and duplicate-delivery semantics | TODO |
| 26.5 | Structured remote Result/Failure/WAITING propagation | TODO |
| 26.6 | Trusted participant/session seam for signing/authentication adapters | TODO |
| 26.7 | End-to-end local two-node acceptance test | TODO |

## Definition of Done

Sprint 26 is complete only when:

- a remote participant cannot invoke governed application work by bypassing
  `ExecutionEngine`;
- local and remote execution share capability, policy, approval and failure
  semantics;
- duplicate request delivery cannot duplicate a completed governed execution;
- remote lineage is visible from request through Execution and result;
- WAITING/HITL can cross the distributed boundary without being reported as
  success;
- disconnect/retry behavior has deterministic tests;
- the default test path remains zero-infrastructure;
- CI and CodeQL are green.

---

## Known work after Sprint 26

These are deliberately **not** collapsed into Sprint 26:

- Edge semantic events → `Observation` / World Model ingestion loop;
- richer cognitive memory retrieval, belief/reflection/consolidation;
- generated/stable multi-language protocol SDK boundary;
- fleet scheduling and multi-device mission orchestration;
- physical reference firmware and hardware validation;
- cloud/control-plane productization;
- Voodoo Studio / Store / Identity product surfaces where they belong above the
  Runtime rather than duplicating it.

## Quality rules

For every implementation sprint:

1. create a focused branch from current `main`;
2. preserve one Runtime and one canonical `Execution` lifecycle;
3. add failure-path tests for every durability/security claim;
4. keep the base install local-first and zero-infrastructure;
5. run format, lint, Python 3.12, Python 3.13 and security analysis;
6. merge only with required checks green;
7. update the sprint document/tracker only after the implementation is true;
8. cut releases as an explicit release operation rather than silently treating
   a merge as a published version.

## Historical references

- [`ROADMAP.md`](ROADMAP.md) — master architecture and long-range engineering plan.
- [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — early completed milestone history.
- [`docs/sprint-24-agency-foundation.md`](docs/sprint-24-agency-foundation.md) —
  Agency/World implementation plan.
- [`docs/sprints/SPRINT_25_UI_MAGIC.md`](docs/sprints/SPRINT_25_UI_MAGIC.md) — UI
  Magic architecture and acceptance criteria.
- [`docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md`](docs/sprints/SPRINT_26_TRUSTED_DISTRIBUTED_RUNTIME.md) —
  distributed execution architecture and implementation slices.
- Repository Git history — detailed legacy Sprint 1–23 tracker that preceded
  this reconciliation.
