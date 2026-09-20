# Architecture governance

This document is the maintenance contract for Voodoo's repository architecture.
It applies to every new feature, refactor, integration, public API, and release.

## Architectural center

Dependencies must point toward stable semantics:

```text
primitives / protocol
        ↑
world / core contracts
        ↑
runtime
        ↑
application surfaces (ui, data, auth, ai, edge)
        ↑
integrations / cli
```

The runtime has one execution authority. Distributed execution, workers, mesh
transport, agents, and edge participants feed or extend that authority; they do
not create parallel execution models.

## Canonical ownership

- `primitives/`: stable semantic value objects and contracts.
- `protocol/`: transport/language-neutral contracts.
- `world/`: entities, observations, and operational state.
- `core/`: application facade and framework lifecycle.
- `runtime/execution/`: canonical execution authority and execution model.
- `runtime/reconciliation/`: deterministic world/reconciliation mechanics.
- `runtime/scheduling/`: work, dispatch, handoff, and durable worker orchestration.
- `runtime/agency/`: goals and adaptive agency.
- `runtime/distributed/`: distributed participation, membership, and fabric.
- `runtime/inspection/`: lineage and runtime inspection.
- `ui/`, `data/`, `auth/`, `ai/`, `edge/`: application-facing domains.
- `observability/`: native telemetry/inspection state and middleware.
- `integrations/`: optional external-system/vendor implementations.
- `cli/`: developer tooling.
- `_internal/`: implementation details with no compatibility promise.

Compatibility namespaces such as `mcp/`, `telemetry/`, legacy Runtime modules,
and public workers/mesh paths may delegate to canonical owners. A compatibility
facade is not a second semantic owner.

## Placement decision

Before adding or moving a module, answer in order:

1. What semantic concept does it implement?
2. Which existing domain owns that concept?
3. Does it depend on a vendor SDK? If yes, can the semantic contract stay in its
   domain while the vendor implementation moves to `integrations/`?
4. Is a public import already documented or used? Preserve it with a facade
   unless a deliberate major-version migration removes it.
5. Does the change introduce a second execution, scheduling, reconciliation,
   identity, or observability authority? If yes, redesign it around the
   canonical owner instead.

Creating a new top-level `src/voodoo/<domain>/` requires an explicit architecture
decision and documentation update in the same PR.

## Hard invariants

CI and review must preserve these rules:

1. One canonical ExecutionEngine authority.
2. No vendor SDK dependency in `core`, `runtime`, `primitives`, `protocol`,
   or `world`.
3. No new package-root convenience modules without an explicit public API decision.
4. No source `# noqa` suppressions. Fix the underlying lint/complexity problem.
5. No silent break of a documented/public import.
6. New unit tests live under a semantic test domain, not flat under `tests/`.
7. Durability claims require failure-path tests.
8. Provider-specific dependencies remain optional extras.
9. Moves preserve behavior unless the PR explicitly declares a behavioral change.
10. Architecture exceptions must be documented, narrow, and tested.

## Test ownership

```text
tests/
├── unit/          semantic unit ownership
├── integration/   cross-domain behavior
├── e2e/           developer/user journeys
├── contracts/     provider/protocol contracts
└── architecture/  repository invariants
```

Compatibility behavior may be tested in the closest unit/integration domain.
Do not recreate a flat `tests/test_*.py` layout.

## Pull-request architecture checklist

For any structural or cross-domain change:

- [ ] semantic owner is explicit;
- [ ] dependency direction still points inward;
- [ ] public imports are preserved or a breaking change is declared;
- [ ] vendor code is outside semantic Core;
- [ ] no parallel execution/scheduling authority was introduced;
- [ ] tests live with the correct ownership;
- [ ] architecture tests were updated when a deliberate boundary changes;
- [ ] Ruff, type check, Python 3.12/3.13, Store-first install, and CodeQL pass;
- [ ] changelog and architecture docs describe material changes.

## Release rule

A release is architecture-ready only when the final `main` commit passes the
same gates used by the PR. Release automation may bump the version, but it must
not be used to hide an unvalidated architectural change.
