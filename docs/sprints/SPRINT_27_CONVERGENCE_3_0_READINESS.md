# Sprint 27 — Runtime Convergence & 3.0 Readiness

**Status:** DONE · closed 2026-09-13

## Purpose

Sprint 27 closed the architectural/product gaps found in the post-Sprint-26
review. It was a convergence sprint, not feature accumulation.

> **Voodoo is the programmable runtime for adaptive applications and operational systems.**

```text
World → Observation → Goal → Intent → Plan → Capability + Policy
     → Execution → Effect → Participant → ACK → Observation → World
```

That loop is now represented by runtime contracts, tests, examples, protocol
schemas, documentation and release-quality gates.

Primary implementation: PR #52, squash-merged into `main` as `e73a718`.

## Architectural invariants preserved

1. Exactly one Voodoo Runtime and one canonical `Execution` lifecycle.
2. AI is Compute, never a privileged authority boundary.
3. Edge/device code is an external participant, not a second runtime.
4. Effects are attempted actions; Observations are evidence.
5. Capability grants a class of authority; Policy may narrow it.
6. World state preserves evidence provenance, confidence and event time.
7. Remote/physical work enters the same authorization/execution path as local work.
8. Local-first remains the default.
9. Protocol schemas are the semantic boundary for non-Python participants.
10. The public developer surface becomes more coherent as internals grow.

## 27.1 — Edge → World semantic ingestion

**Status: DONE**

Delivered:

- optional World-aware Edge gateway;
- stable device → World entity identity;
- device state and explicit event evidence → `Observation`;
- heartbeat remains telemetry;
- Effect ACK changes World only when it contains actual observed evidence;
- trace/execution/message/source lineage;
- duplicate-safe observation IDs;
- stale evidence retained without regressing projection.

Acceptance proves a simulated device updates World state through the normal Edge
path and the resulting evidence remains traceable to its source.

## 27.2 — World-aware Goal/planning convergence

**Status: DONE**

Delivered:

- structured `PlanningContext`;
- deterministic context-aware participant ranking;
- capability remains prerequisite — planning context never grants authority;
- target-entity/World conditions, priority and pluggable bounded ranker;
- `AdaptiveSupervisor` passes runtime context to Planner automatically;
- `GoalRuntime` refreshes target World state before each Intent;
- prior results available to later bounded planning decisions;
- compatibility for existing no-context Planner calls.

This deliberately does **not** invent an unconstrained autonomous/symbolic
planner. Rich goal decomposition and cognitive strategy remain a later
intelligence layer.

## 27.3 — Protocol convergence

**Status: DONE**

The original protocol omitted semantic concepts added in Sprints 24–26.
Sprint 27 added protocol models for:

- `Entity`, `Relationship`, `Observation`, `WorldSnapshot`;
- `Goal`, Goal status/run records;
- `RemoteExecutionRequest` and `RemoteExecutionOutcome`.

The additions preserve the existing compatibility law: adding entity families
is additive; breaking shape changes to an existing schema still require an
explicit protocol version change.

Non-Python participants can now represent World evidence and governed remote
work without importing Python runtime classes.

## 27.4 — Public API and developer-experience convergence

**Status: DONE**

Delivered:

- `docs/public-api-3.md` defines the 3.0 import law;
- 2.x compatibility remains intact instead of silently shrinking
  `voodoo.__all__`;
- subsystem namespaces are canonical for larger catalogs (`voodoo.ui`,
  `voodoo.runtime`, `voodoo.world`, `voodoo.edge`, `voodoo.protocol`);
- README/examples teach the canonical direction;
- actual package-root contraction is reserved for a deliberate 3.0 migration.

## 27.5 — Canonical examples and executable canary

**Status: DONE**

Delivered:

- stale AI SaaS example migrated to Python-callable UI actions;
- fake MCP participation claim removed;
- zero-infrastructure `examples/operational_closed_loop` canary added:

```text
simulated device → Edge → Observation → World → Goal/Intent
  → Capability + Policy → Execution → Effect → device
  → ACK/evidence → Observation → World
```

Acceptance proves World remains unchanged by the Effect itself and changes only
when device evidence returns. Operational inspection uses real Runtime/World
sources of truth instead of invented counters.

## 27.6 — Documentation and repository truth

**Status: DONE**

Delivered:

- `ROADMAP.md`, `SPRINT_PLAN.md`, README and protocol docs reconciled with the
  current runtime architecture;
- obsolete statements such as Entity not existing or Sprint 15 being next
  removed;
- cognitive Memory, fleet, generated SDK and Cloud work identified as future
  product/intelligence initiatives rather than existing implementation;
- repository metadata target documented where connector permissions cannot
  mutate GitHub repository settings directly.

`CHANGELOG.md` remains intentionally release-oriented. The latest published
release is still v2.6.2, while `main` is ahead of that release. Sprint completion
evidence is tracked here and in `SPRINT_PLAN.md`; a future explicit release cut
must add the corresponding published-version changelog entry rather than
inventing an unreleased version number during sprint closure.

Repository metadata target remains:

- description: `The programmable runtime for adaptive applications and operational systems — software, AI, humans, distributed nodes and physical systems in one execution model.`
- suggested topics: `python`, `runtime`, `durable-execution`, `agents`,
  `world-model`, `distributed-systems`, `edge`, `reactive`, `async`, `mcp`.

The current GitHub connector does not expose repository-description/topic
mutation, so this remains an explicit repository-setting action outside code.

## 27.7 — Release-quality gate and warning-zero baseline

**Status: DONE**

Delivered:

- invalid pytest asyncio marking removed from project-owned tests;
- CI promotes `RuntimeWarning` and
  `pytest.PytestUnhandledThreadExceptionWarning` to errors;
- project-owned aiosqlite/AsyncMock lifecycle warnings exposed by the gate were
  fixed rather than suppressed;
- mypy is enforced on the newly converged Sprint 27 semantic boundary;
- the historical full-repository type debt remains explicit rather than being
  hidden behind blanket suppression;
- Ruff format/lint, Python 3.12/3.13 and CodeQL remained green.

The enforced Sprint 27 type boundary is:

```text
runtime/planner.py
edge/world.py
protocol/operational.py
```

This is a deliberate typed frontier, not a false claim that the entire legacy
repository is already strict-mypy-clean.

## 27.8 — Sprint closure / next-phase readiness

**Status: DONE**

Final acceptance evidence on PR #52 head `1e742a3`:

- Ruff format: green;
- Ruff lint: green;
- scoped mypy boundary: green;
- full service-backed Python 3.12 suite: green;
- full service-backed Python 3.13 suite: green;
- CodeQL: green;
- operational closed-loop canary acceptance: merged and green;
- duplicate/evidence semantics: merged and green;
- protocol export/round-trip: merged and green;
- public import compatibility: merged and green;
- runtime/unhandled-thread warning classes are enforced as CI errors;
- repository architecture/tracker no longer claims a stale next sprint.

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

The semantic seams required by those systems are stable enough for the next
architecture/product review to select the next phase deliberately.

## Sprint 27 completion statement

The acceptance statement is now demonstrably true:

> A Voodoo system can observe a changing operational world, pursue a durable
> goal, choose already-authorized compute using current World context, execute
> software/device Effects through the canonical Runtime, ingest resulting
> evidence back into World state, preserve lineage across protocol boundaries,
> survive duplicate/restart conditions, and teach that architecture consistently
> through its API, examples and documentation.

No Sprint 28 is selected by this document. The next action is a fresh
post-convergence review of product direction, release strategy and the next
highest-leverage system milestone.
