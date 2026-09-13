# Sprint 27 — Runtime Convergence & 3.0 Readiness

**Status:** COMPLETE · closed 2026-09-13

## Purpose

Sprint 27 closed the architectural/product gaps found in the post-Sprint-26
review. It was a convergence sprint, not feature accumulation.

> **Voodoo is the programmable runtime for adaptive applications and operational systems.**

```text
World → Observation → Goal → Intent → Plan → Capability + Policy
     → Execution → Effect → Participant → ACK → Observation → World
```

The loop is now represented by runtime contracts, tests, examples, protocol
schemas, documentation and release-quality gates.

## Completion evidence

- Integration PR: **#52**
- Squash merge: **`e73a718eb90830bc0594a28be3443d13375089c3`**
- Ruff format/lint: **PASS**
- Enforced mypy convergence boundary: **PASS**
- Python 3.12 full service-backed suite: **PASS**
- Python 3.13 full service-backed suite: **PASS**
- CodeQL: **PASS**
- Operational closed-loop acceptance: **PASS**
- Project-owned `RuntimeWarning` / unhandled-thread warning gates: **PASS**

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
- compatibility for existing no-context Planner calls;
- equal ranked candidates preserve registration order and existing fallback semantics.

This intentionally does **not** invent an unconstrained autonomous/symbolic
planner. Rich goal decomposition remains a later intelligence layer.

## 27.3 — Protocol convergence

**Status: DONE**

The stable protocol boundary now includes the semantic concepts introduced by
Sprints 24–26:

- `Entity`, `Relationship`, `Observation`, `WorldSnapshot`;
- `Goal`, Goal status/run records;
- `RemoteExecutionRequest` and `RemoteExecutionOutcome`.

The public protocol registry and JSON Schema export now describe the same
complete canonical surface. The change is additive, so existing entity shapes
did not require a breaking schema-version bump.

## 27.4 — Public API and developer-experience convergence

**Status: DONE**

- `docs/public-api-3.md` defines the 3.0 namespace/import law;
- 2.x compatibility is preserved instead of silently shrinking `voodoo.__all__`;
- subsystem namespaces are canonical for catalogs (`voodoo.ui`,
  `voodoo.runtime`, `voodoo.world`, `voodoo.edge`, `voodoo.protocol`);
- README/examples teach canonical imports;
- actual package-root contraction remains a deliberate 3.0 migration rather
  than an accidental breaking change.

## 27.5 — Canonical examples and executable canary

**Status: DONE**

- modernized the AI SaaS example to Python-callable UI actions;
- removed fake MCP-chain claims;
- added zero-infrastructure `examples/operational_closed_loop` canary:

```text
simulated device → Edge → Observation → World → Goal/Intent
  → Capability + Policy → Execution → Effect → device
  → ACK/evidence → Observation → World
```

The acceptance proves that issuing an Effect does not mutate World truth; only
returned evidence does.

## 27.6 — Documentation and repository truth

**Status: DONE for repository-controlled truth**

- reconciled `ROADMAP.md`, `SPRINT_PLAN.md`, README and protocol docs;
- removed obsolete sprint/entity statements;
- documented cognitive Memory, fleet, SDK and Cloud work as future initiatives;
- canonical public repository description/topics are documented below.

Desired repository metadata:

- description: `The programmable runtime for adaptive applications and operational systems — software, AI, humans, distributed nodes and physical systems in one execution model.`
- topics: `python`, `runtime`, `durable-execution`, `agents`, `world-model`,
  `distributed-systems`, `edge`, `reactive`, `async`, `mcp`.

The available GitHub connector has read-only repository-metadata access, so this
single host-level setting cannot be mutated from the implementation workflow.
It does not affect runtime or release readiness and remains an explicit manual
GitHub repository-setting action.

## 27.7 — Release-quality gate and warning-zero baseline

**Status: DONE**

Delivered:

- invalid pytest asyncio marking cleanup;
- CI gates project-owned `RuntimeWarning` and pytest unhandled-thread warnings;
- removed the AsyncMock coroutine leak exposed by the stricter gate;
- fixed aiosqlite event-loop ownership in test lifecycle paths instead of
  suppressing the warning;
- enforced mypy on the converged semantic boundary;
- preserved historical full-repository mypy debt as explicit debt rather than
  pretending it disappeared;
- Ruff, Python 3.12/3.13 and CodeQL all green.

Current enforced typed boundary begins with:

```text
runtime/planner.py
edge/world.py
protocol/operational.py
```

## 27.8 — Sprint closure / next-phase readiness

**Status: DONE**

Verified before integration merge:

- full service-backed Python 3.12/3.13 suite green;
- CodeQL green;
- operational closed-loop acceptance green;
- duplicate/evidence semantics green;
- protocol export/round-trip green;
- public import compatibility verified;
- repository documentation reconciled;
- convergence code type-gated.

## Explicitly deferred beyond Sprint 27

These are future product/scale/intelligence initiatives, not unresolved Sprint
27 correctness gaps:

- production PKI/OIDC/mTLS identity platform;
- cognitive Memory consolidation/reflection/belief strategies;
- richer goal decomposition and mission planning;
- generated full TypeScript/Go/Rust SDK families;
- fleet scheduler and large multi-device mission orchestration;
- production Voodoo Cloud/control plane;
- large physical robot reference implementation;
- distributed consensus/global exactly-once claims.

The semantic seams required by those systems are now stable enough for the next
architectural review.

## Completion statement

Sprint 27 demonstrates this statement in executable tests and examples:

> A Voodoo system can observe a changing operational world, pursue a durable
> goal, choose already-authorized compute using current World context, execute
> software/device Effects through the canonical Runtime, ingest resulting
> evidence back into World state, preserve lineage across protocol boundaries,
> survive duplicate/restart conditions, and teach that architecture consistently
> through its API, examples and documentation.

**Next action:** perform a post-convergence architectural/product review and
select the next phase from implementation truth. No Sprint 28 is selected by
this closure document.
