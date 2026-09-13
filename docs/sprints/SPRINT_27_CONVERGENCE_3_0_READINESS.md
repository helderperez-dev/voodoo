# Sprint 27 — Runtime Convergence & 3.0 Readiness

**Status:** ACTIVE

## Purpose

Sprint 27 closes the architectural and product gaps found in the post-Sprint-26 repository review. This is not a feature-accumulation sprint. Its job is to make the existing Voodoo architecture converge into one coherent, testable operational runtime and leave the repository ready for the next major phase.

North Star:

> **Voodoo is the programmable runtime for adaptive applications and operational systems.**

Operational law:

```text
World → Observation → Goal → Intent → Plan → Capability + Policy
     → Execution → Effect → Participant → ACK → Observation → World
```

Sprint 27 is complete only when this loop is represented by real runtime contracts, protocol schemas, tests, examples, documentation, and release-quality quality gates.

---

## Architectural invariants

1. Exactly one Voodoo Runtime and one canonical `Execution` lifecycle.
2. AI is Compute, never a privileged authority boundary.
3. Edge/device code is an external participant; it does not own a second runtime.
4. Effects are attempted actions. Observations are evidence about what actually happened.
5. Capability grants a class of authority; contextual Policy may narrow it.
6. World state is projected from evidence and must preserve provenance, confidence, and event time.
7. Remote and physical work must enter the same authorization and execution path as local work.
8. Local-first remains the default; the complete acceptance path must work without external infrastructure.
9. The protocol is the stable semantic boundary for non-Python participants.
10. The public developer surface must become smaller and more coherent, not grow with every subsystem.

---

## 27.1 — Edge → World semantic ingestion

### Problem

The Edge Gateway already authenticates devices, receives events/state, creates governed executions, delivers effects, and receives ACKs, while the World Model already supports append-only observations with source, confidence, event time, trace and execution lineage. The two are not yet one loop.

### Deliver

- Optional World binding on the Edge gateway/runtime boundary.
- Stable device → World entity identity mapping.
- Semantic device state/event ingestion as `Observation` records.
- Heartbeat remains telemetry only.
- Effect ACK/result can become an observation only when it contains actual observed state/evidence.
- Preserve `trace_id`, `execution_id`, message/source identity and event time.
- Duplicate device messages must not duplicate observations.
- Stale evidence remains history and must not regress projected state.

### Definition of Done

A simulated device can produce evidence that updates World state through the normal Edge path, and the resulting observation can be traced to the originating device message/execution.

---

## 27.2 — World-aware Goal and planning convergence

### Problem

`GoalRuntime` is durable but its default decomposition is intentionally simple. `Planner` is deterministic capability routing rather than operational planning.

### Deliver

- Introduce an explicit planning context containing Goal, Intent, World snapshot, prior results, constraints and participant metadata.
- Keep deterministic planning as the default.
- Allow world-aware participant selection/ranking through a bounded strategy seam without delegating authority to AI.
- Goal decomposition receives structured World context rather than ad-hoc `Any` only.
- Replanning is triggered only by explicit observed state/result changes and remains bounded.
- Preserve compatibility for existing planner/decomposer call sites.

### Non-goal

Do not invent an unconstrained autonomous agent or general-purpose symbolic planner.

---

## 27.3 — Protocol v2 convergence

### Problem

The runtime has evolved beyond the current protocol surface. The canonical protocol currently omits the World/Goal/distributed execution concepts added in Sprints 24–26.

### Deliver

- Add protocol schemas for `Entity`, `Relationship`, `Observation`, `WorldSnapshot`, `Goal`, Goal status/run records, remote execution request/outcome and lineage fields required by the distributed runtime.
- Align status vocabulary with runtime truth.
- Bump the protocol schema major version because the claimed stable semantic boundary changes materially.
- Add compatibility/migration helpers where useful.
- Update JSON Schema export and protocol documentation.
- Add round-trip/schema contract tests for all new protocol entities.

### Definition of Done

A non-Python participant can understand the semantic data required to observe the World and request/inspect governed remote work without importing runtime internals.

---

## 27.4 — Public API and developer-experience convergence

### Problem

The package describes a deliberately small public API while the top-level `voodoo.__all__` is large and mixes runtime, AI, data, style and UI component catalogs.

### Deliver

- Define the intended 3.0 public import law.
- Keep source compatibility during Sprint 27 through deprecation shims; do not silently break 2.x applications.
- Move catalog-style surfaces to their defining namespaces (`voodoo.ui`, `voodoo.runtime`, `voodoo.world`, `voodoo.protocol`, etc.).
- Make the recommended happy path obvious in README/docs/examples.
- Add contract tests for canonical imports and compatibility imports.
- Document what is scheduled to leave the top-level namespace in 3.0.

### Definition of Done

A developer can understand the canonical import surface without reading implementation internals, while existing 2.x imports still resolve with explicit migration guidance.

---

## 27.5 — Canonical examples and executable canary

### Problem

Older examples teach superseded UI/event semantics and overstate chains such as MCP participation. The UI Magic demo uses synthetic runtime state rather than the real operational loop.

### Deliver

- Rewrite stale examples to use Python-callable events and current UI APIs.
- Remove false architecture claims from example documentation/comments.
- Add a zero-infrastructure `operational_closed_loop` canary:

```text
simulated sensor/device
  → Edge
  → Observation
  → World
  → Goal/Intent
  → Capability + Policy
  → Execution
  → Effect
  → simulated actuator
  → ACK/evidence
  → Observation
  → World
```

- The canary must expose the real runtime through Voodoo UI/system components rather than hand-built fake counters.
- Add an acceptance test proving the full loop.

---

## 27.6 — Documentation and repository truth

### Problem

`ROADMAP.md`, repository metadata, examples, and implementation truth have drifted apart.

### Deliver

- Rewrite/reconcile the master roadmap so current repository position is true.
- Remove obsolete statements such as Entity not existing or Sprint 15 being next.
- Reconcile `SPRINT_PLAN.md`, `ROADMAP.md`, `ARCHITECTURE.md`, README and protocol docs.
- Update GitHub repository positioning/topics if connector permissions allow; otherwise record the exact remaining repository-setting action.
- Update CHANGELOG with all Sprint 27 user-visible behavior.
- Ensure no document calls aspirational work implemented.

---

## 27.7 — Release-quality gate and warning-zero baseline

### Problem

The suite is green but still emits warnings, including async resource cleanup issues. Mypy is configured but is not part of CI.

### Deliver

- Eliminate project-owned pytest/async warnings identified in the Sprint 26 acceptance run.
- Fix `aiosqlite` lifecycle/resource cleanup warnings rather than suppressing them globally.
- Fix un-awaited `AsyncMock` warnings.
- Add mypy to CI after bringing the checked surface to green; if legacy modules require staged strictness, encode the boundary explicitly rather than silently skipping type checking.
- Keep Ruff format/lint, Python 3.12/3.13 and CodeQL green.
- Add a warning gate for owned warnings so regressions fail CI.

### Definition of Done

The release gate is green with no known project-owned runtime/resource warnings and type checking is an enforced CI contract.

---

## 27.8 — Sprint closure / next-phase readiness

Before closing Sprint 27:

- run the full zero-infra and service-backed test matrix;
- run the operational closed-loop canary;
- verify restart/durability and duplicate-delivery paths;
- verify public import compatibility and protocol export;
- verify docs contain no known stale sprint state;
- update `SPRINT_PLAN.md` to mark Sprint 27 DONE only after implementation evidence is merged;
- do not name the next implementation sprint until the final Sprint 27 review confirms the remaining gaps.

---

## Explicitly deferred beyond Sprint 27

These are next-phase product/scale initiatives, not unresolved Sprint 27 correctness gaps:

- production PKI/OIDC/mTLS identity platform;
- fleet scheduler and large multi-device mission orchestration;
- generated full TypeScript/Go/Rust SDK families beyond the stable Protocol boundary;
- production cloud control plane / managed Voodoo Cloud;
- large physical robot firmware/reference hardware validation;
- distributed consensus/global exactly-once claims.

The semantic seams required for these future systems must be ready by Sprint 27, but those products are not built here.

---

## Sprint 27 completion test

Sprint 27 is DONE only if this statement is demonstrably true:

> A Voodoo system can observe a changing operational world, pursue a durable goal, choose governed capabilities using current world context, execute software or device effects through the canonical runtime, ingest resulting evidence back into the World, expose the complete lineage through the protocol/UI, survive duplicate/restart boundaries, and teach that architecture consistently through its public API, examples and documentation.
