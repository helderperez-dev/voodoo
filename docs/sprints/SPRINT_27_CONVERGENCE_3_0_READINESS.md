# Sprint 27 — Runtime Convergence & 3.0 Readiness

**Status:** ACTIVE

## Purpose

Sprint 27 closes the architectural/product gaps found in the post-Sprint-26
review. It is a convergence sprint, not feature accumulation.

> **Voodoo is the programmable runtime for adaptive applications and operational systems.**

```text
World → Observation → Goal → Intent → Plan → Capability + Policy
     → Execution → Effect → Participant → ACK → Observation → World
```

Sprint 27 is complete only when that loop is represented by runtime contracts,
tests, examples, protocol schemas, documentation and release-quality gates.

## Architectural invariants

1. Exactly one Voodoo Runtime and one canonical `Execution` lifecycle.
2. AI is Compute, never a privileged authority boundary.
3. Edge/device code is an external participant, not a second runtime.
4. Effects are attempted actions; Observations are evidence.
5. Capability grants a class of authority; Policy may narrow it.
6. World state preserves evidence provenance, confidence and event time.
7. Remote/physical work enters the same authorization/execution path as local work.
8. Local-first remains the default.
9. Protocol schemas are the semantic boundary for non-Python participants.
10. The public developer surface should become more coherent as internals grow.

## 27.1 — Edge → World semantic ingestion

**Implementation:** in progress on PR #52.

Deliver:

- optional World-aware Edge gateway;
- stable device → World entity identity;
- device state and explicit event evidence → `Observation`;
- heartbeat remains telemetry;
- Effect ACK changes World only when it contains actual observed evidence;
- trace/execution/message/source lineage;
- duplicate-safe observation IDs;
- stale evidence retained without regressing projection.

Definition of Done: a simulated device updates World state through the normal
Edge path and the resulting evidence remains traceable to its source.

## 27.2 — World-aware Goal/planning convergence

**Implementation:** in progress on PR #52.

Deliver:

- structured `PlanningContext`;
- deterministic context-aware participant ranking;
- capability remains prerequisite — planning context never grants authority;
- target-entity/World conditions, priority and pluggable bounded ranker;
- `AdaptiveSupervisor` passes runtime context to Planner automatically;
- `GoalRuntime` refreshes target World state before each Intent;
- prior results available to later bounded planning decisions;
- compatibility for existing no-context Planner calls.

This does **not** invent an unconstrained autonomous/symbolic planner. Rich goal
decomposition and cognitive strategy remain a later intelligence layer.

## 27.3 — Protocol convergence

**Implementation:** in progress on PR #52.

The original protocol omitted semantic concepts added in Sprints 24–26.
Sprint 27 adds protocol models for:

- `Entity`, `Relationship`, `Observation`, `WorldSnapshot`;
- `Goal`, Goal status/run records;
- `RemoteExecutionRequest` and `RemoteExecutionOutcome`.

This is additive to the existing wire contracts, so Sprint 27 does **not** bump
`SCHEMA_VERSION` solely for the presence of new entity families. Breaking shape
changes to an existing entity still require an explicit version bump.

Definition of Done: non-Python participants can represent World evidence and
governed remote work without importing Python runtime classes.

## 27.4 — Public API and developer-experience convergence

**Implementation:** in progress on PR #52.

- define `docs/public-api-3.md`;
- preserve 2.x compatibility instead of silently shrinking `voodoo.__all__`;
- make subsystem namespaces canonical for catalogs (`voodoo.ui`,
  `voodoo.runtime`, `voodoo.world`, `voodoo.edge`, `voodoo.protocol`);
- update README/examples to teach canonical imports;
- reserve actual package-root contraction for a deliberate 3.0 migration.

## 27.5 — Canonical examples and executable canary

**Implementation:** in progress on PR #52.

- update stale AI SaaS example to Python-callable UI actions;
- remove fake MCP participation claims;
- add zero-infrastructure `examples/operational_closed_loop` canary:

```text
simulated device → Edge → Observation → World → Goal/Intent
  → Capability + Policy → Execution → Effect → device
  → ACK/evidence → Observation → World
```

- acceptance test proves World remains unchanged by the Effect itself and only
  changes when device evidence is returned;
- operational inspection must use real Runtime/World sources of truth rather
  than invented counters.

## 27.6 — Documentation and repository truth

**Implementation:** in progress on PR #52.

- reconcile `ROADMAP.md`, `SPRINT_PLAN.md`, README and protocol docs;
- remove obsolete statements such as Entity not existing or Sprint 15 being next;
- document cognitive Memory, fleet, SDK and Cloud work as future rather than implemented;
- update CHANGELOG before closure;
- repository description/topics should become:
  - description: `The programmable runtime for adaptive applications and operational systems — software, AI, humans, distributed nodes and physical systems in one execution model.`
  - suggested topics: `python`, `runtime`, `durable-execution`, `agents`,
    `world-model`, `distributed-systems`, `edge`, `reactive`, `async`, `mcp`.

The current GitHub connector exposes repository metadata read access but no
repository-metadata mutation action. Therefore the description/topics change is
an explicit repository-setting action outside code; it is not represented as a
fake code change.

## 27.7 — Release-quality gate and warning-zero baseline

**Implementation:** active.

Sprint 26 exposed existing project-owned async/resource warnings and showed that
strict mypy configuration existed without an enforced CI boundary.

Deliver:

- remove invalid pytest asyncio marking;
- gate `RuntimeWarning` and pytest unhandled-thread warnings in CI;
- investigate/fix owned aiosqlite/AsyncMock lifecycle warnings exposed by that gate;
- enforce mypy on the newly converged Sprint 27 semantic boundary;
- keep the historical full-repository mypy debt explicit rather than pretending
  278 pre-existing errors were solved by configuration suppression;
- expand the typed boundary in subsequent hardening work instead of silently
  claiming the entire legacy repository is strict-typed;
- Ruff format/lint, Python 3.12/3.13 and CodeQL must remain green.

The enforced Sprint 27 type boundary is initially:

```text
runtime/planner.py
edge/world.py
protocol/operational.py
```

Definition of Done: new convergence code is type-gated and project-owned runtime
warning classes fail CI.

## 27.8 — Sprint closure / next-phase readiness

Before closing Sprint 27:

- full service-backed Python 3.12/3.13 suite green;
- CodeQL green;
- operational closed-loop canary acceptance green;
- duplicate/evidence semantics green;
- protocol export/round-trip green;
- public import compatibility verified;
- docs contain no known stale sprint state;
- `SPRINT_PLAN.md` marks DONE only after implementation evidence is merged.

## Explicitly deferred beyond Sprint 27

These are product/scale/intelligence initiatives, not unresolved Sprint 27
correctness gaps:

- production PKI/OIDC/mTLS identity platform;
- cognitive Memory consolidation/reflection/belief strategies;
- generated full TypeScript/Go/Rust SDK families;
- fleet scheduler and large multi-device mission orchestration;
- production Voodoo Cloud/control plane;
- large physical robot reference implementation;
- distributed consensus/global exactly-once claims.

The semantic seams required by those systems must be stable when Sprint 27
closes.

## Sprint 27 completion test

Sprint 27 is DONE only when this statement is demonstrably true:

> A Voodoo system can observe a changing operational world, pursue a durable
> goal, choose already-authorized compute using current World context, execute
> software/device Effects through the canonical Runtime, ingest resulting
> evidence back into World state, preserve lineage across protocol boundaries,
> survive duplicate/restart conditions, and teach that architecture consistently
> through its API, examples and documentation.
