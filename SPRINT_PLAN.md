# Voodoo — Implementation Sprint Tracker

Source architecture: [`ROADMAP.md`](ROADMAP.md).

This file is the **current source of truth for implementation progress**.
Detailed historical plans live in Git history and under `docs/sprints/`.

> Updated 2026-10-06. Sprint 30 — Production Readiness is active after a
> cross-repository audit selected correctness, security, durability, component
> quality and release evidence as the next product phase.

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
- Voodoo Store is the zero-config durable application substrate;
- local-first remains the default;
- scaling changes deployment topology, not application architecture.

## Current position

| Item | State |
|---|---|
| Latest repository release | **v3.2.1** |
| Package version on `main` | **3.2.1** |
| Sprints through 23 | **DONE** |
| Sprint 24 — Agency Foundation | **DONE** |
| Sprint 25 — UI Magic | **DONE** |
| Sprint 26 — Trusted Distributed Execution Fabric | **DONE** |
| Sprint 27 — Runtime Convergence & 3.0 Readiness | **DONE** |
| Sprint 28 — Runtime Infrastructure Convergence | **DONE** |
| Post-Sprint 28 | **Design System 4 + Application Graph + repository convergence DONE** |
| 3.0 clean architecture | **DONE and released** |
| Store 0.3 native convergence + modern Model contract | **DONE and released (v3.2.1)** |
| Sprint 29 — Experience Convergence | **DONE · closed 2026-09-30** |
| Sprint 30 — Production Readiness | **IN PROGRESS · started 2026-10-06** |
| Next release target | **Determined by verified Sprint 30 compatibility impact** |
| Release checkpoint | **No Sprint 30 release claim until every mandatory gate passes** |

Release evidence: tag `v3.2.1` points at the Store 0.3 native convergence
release. The release workflow passed the test suite, clean Store-first
distribution gate, package build, PyPI publication, Homebrew update and GitHub
Release creation.

---

## Sprint 30 — Production Readiness

**Status: IN PROGRESS · started 2026-10-06**

Plan: [`docs/sprints/SPRINT_30_PRODUCTION_READINESS.md`](docs/sprints/SPRINT_30_PRODUCTION_READINESS.md)

Sprint 30 was selected at the post-Sprint-29 product gate. It hardens the
existing Runtime, Store, UI and developer experience rather than adding another
major subsystem.

Production Profile 1 is deliberately bounded to one Runtime process, one local
Store writer, multiple isolated authenticated browser sessions, durable local
state and tested backup/restore. Multi-writer Store operation, consensus and
global exactly-once execution remain out of scope.

Current progress:

- [x] Production-aware CORS/CSRF defaults, fail-closed startup validation,
  application-owned security configuration, validated CSRF/rate-limit identity,
  encrypted local secrets, and security regression coverage;
- [x] Session-owned UI events, state, bindings and targeted WebSocket patches,
  including two-user isolation and readiness/shutdown lifecycle contracts;
- [x] One executable public API, resource-backed `voodoo new` scaffold,
  documentation/skills/template convergence, and generated-application smoke
  coverage;
- [x] Store-first Runtime durability across data, jobs, events, objects,
  workflows, execution state, backup/restore, migrations, quotas, health and
  bounded object streaming;
- [x] Stable component metadata, semantic/accessibility contracts, 102-control
  state coverage, deterministic render checks, browser behavior gates and
  committed visual PNG/signature baselines;
- [x] Cross-repository governance, dependency/security automation, trusted
  publishing workflows, SBOM/provenance contracts, release manifests and
  release preflight;
- [ ] Hosted Store fault/recovery/backup certification and external security
  review;
- [ ] Full catalog-wide component standardization plus hosted browser,
  accessibility and visual approval;
- [ ] Final artifact-signing/attestation verification, clean-install matrix,
  historical compatibility certification, and GA release claim.

Verified checkpoint (2026-10-10): the production-readiness plan is **112
 complete / 36 open**. Sprint 30's execution checklist is **44 complete / 4
 open**. Framework tests pass **2,364 passed, 133 skipped, 2
warnings**; Site has **421 passing tests**; the root release contract passes for
Framework `3.2.1` and Store `0.3.0`. The sprint remains intentionally open until
the external/hosted gates above produce evidence.

The local supply-chain gate now audits pinned `uv.lock` exports directly, so
unpublished editable application packages no longer create a false-positive
`pip-audit` skip while all resolved third-party dependencies remain covered.
The Site hosted workflow now exports and audits that same locked dependency set
and generates its SBOM from it.

---

## Sprint 29 — Experience Convergence

**Status: DONE · closed 2026-09-30**

Plan: [`docs/sprints/SPRINT_29_EXPERIENCE_CONVERGENCE.md`](docs/sprints/SPRINT_29_EXPERIENCE_CONVERGENCE.md)

Sprint 29 introduced no new major Runtime capability. It closed the gap between
Voodoo's architecture and the experience of building real applications with it.

Delivered:

- one Store-first truth across Runtime, CLI, scaffolding and AI guidance;
- `voodoo new` as the canonical project-creation path;
- zero accidental SQLite files in the default application journey;
- a complete Component Lab covering every renderable public UI component;
- Design System 4 convergence across primitive, extended, product, workspace
  and Runtime/system components;
- mandatory Chromium interaction, accessibility and responsive acceptance;
- component-by-component behavior and visual hardening;
- Store-first `status --json` and side-effect-free `doctor --json`;
- a 3.2 release gate based on real developer journeys, including light/dark
  visual artifacts and 20 real-browser acceptance tests.

Implementation: PR #79. Detailed completion record:
[`docs/sprints/SPRINT_29_EXPERIENCE_CONVERGENCE.md`](docs/sprints/SPRINT_29_EXPERIENCE_CONVERGENCE.md).

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

Design System 2 remains the historical Sprint 25 delivery. The current native visual
layer on `main` is Design System 4, integrated after Sprint 28.

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

## Sprint 28 — Runtime Infrastructure Convergence

**Status: DONE · closed 2026-09-14**

Completion record:
[`docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`](docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)

Sprint 28 made the Store-first architecture operational and established the path from
one local Runtime to multiple governed Voodoo Nodes without changing application
semantics.

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Identity -> Capability + Policy -> Execution
    +-- Data / Jobs / Scheduler / Events / Objects
    +-- Goal / Workflow / HITL
    +-- Edge / World / Agency
    |
    v
application.vstore
```

Multi-node topology remains node-local Store ownership plus Runtime routing:

```text
same application semantics
        |
        v
   Runtime Fabric
     /    |    \
 node-a node-b node-c
   |      |      |
 a.vstore b.vstore c.vstore
```

All slices 28.1–28.23 are closed. The implemented contract includes:

- one application-owned/process-shared `RuntimeStore`;
- Store-backed Data/Model, Queue/Jobs, Scheduler, Events, Objects and Runtime state;
- canonical durable Execution, Goal, Workflow and HITL recovery;
- Runtime Identity with Principal → Capability + Policy → Execution authority;
- local Store transaction + durable outbox boundary;
- authenticated node membership, health, discovery, placement, leases and bounded
  failover;
- protocol schemas for node-fabric semantics;
- Store-backed Edge state;
- explicit SQLite/PostgreSQL/Redis/S3 compatibility adapters;
- single-node, multi-node and Edge acceptance paths;
- Store-first CLI/DX and migration guidance.

Sprint 28 deliberately does **not** claim Store replication, distributed consensus,
global exactly-once, globally serializable transactions, production PKI/OIDC/mTLS or
a managed cloud control plane.

### Post-closure 2.7.x hardening

The first real clean-install path exposed accidental SQL coupling that subsystem tests
had not caught. The 2.7.x line therefore hardened the Store-first contract:

- public/core imports no longer require SQLite adapters;
- SQLite/PostgreSQL/Redis/S3 remain optional/explicit;
- the scheduler SQLite adapter is lazy-loaded;
- default Runtime startup/shutdown does not import `aiosqlite`;
- release CI builds a clean wheel without extras, scaffolds an app, boots its full
  Runtime lifecycle and verifies `application.vstore` durability.
1
Historical hardening baseline at that point: **v2.7.2**. This is superseded by
the published **v3.0.0** architecture baseline.

---

## Post-Sprint 28 — Design System 4

**Status: DONE · included in the published v3.0.0 baseline**

Design System 4 moves the approved Voodoo visual identity into the framework rather
than a template. Native VoodooCSS applications now receive premium light/dark defaults,
a Voodoo purple brand language, stronger page geometry and production-quality controls
with zero custom CSS.

The follow-up Theme-contract hardening preserves the public theming law:

- DS3 purple remains the zero-config default;
- explicit `Theme` primary/secondary values control brand color;
- background/surface/text/border overrides propagate into premium surfaces;
- explicit light-mode Theme overrides remain authoritative;
- regression tests cover both the DS3 defaults and custom branded themes.

Implementation: PR #60 plus follow-up PR #61.

---

## Voodoo 3.0 — Clean architecture and release

**Status: DONE · released 2026-09-21**

The 3.0 convergence closed the major-version cleanup that Sprint 27 prepared:

- package-root API contracted to `Agent`, `App`, `Model`, `page`, `state`,
  `task` and `tool`;
- task/worker orchestration converged under `voodoo.runtime.scheduling`;
- Runtime execution, agency, reconciliation, distributed and inspection concepts
  moved to their canonical semantic owners;
- MCP and OpenTelemetry vendor integration moved under `voodoo.integrations`;
- observability moved to `voodoo.observability`;
- 2.x compatibility-only namespaces and import shims were intentionally removed;
- repository architecture invariants prevent removed duplicate owners from returning;
- tests, examples and documentation were migrated to the canonical 3.0 imports.

Implementation/release evidence: PRs #68, #69, #70, #72 and #73; commit
`2c6c7a6`; GitHub Release/tag `v3.0.0`.

---

## Selection record

Sprint 29 closed at a selection gate. The cross-repository production-readiness
audit on 2026-10-06 selected hardening and convergence as Sprint 30. The former
candidate directions remain deferred until Production Profile 1 passes its gates.

Deferred directions already supported by the architecture:

1. protocol/SDK productization;
2. real Edge/ESP32 reference canary;
3. multi-device mission/fleet orchestration;
4. Studio / operational product surface;
5. managed Runtime/cloud control plane;
6. a product/reference application that pressure-tests the 3.0 Runtime end to end.

Selection criteria:

- recurring user/product demand;
- validates existing Runtime primitives rather than duplicating them;
- keeps local-first progressive complexity;
- produces a strong end-to-end acceptance canary;
- preserves Capability + Policy + canonical Execution authority;
- makes future product work simpler.

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
- [`docs/design_system.md`](docs/design_system.md)
- [`docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`](docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md)
- [`docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md`](docs/sprints/SPRINT_28_RUNTIME_INFRASTRUCTURE_CONVERGENCE.md)
