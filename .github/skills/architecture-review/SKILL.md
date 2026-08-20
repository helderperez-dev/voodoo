# Skill: Architecture Review

> **When to use:** Before merging major changes, adding new subsystems, or refactoring core modules.

---

## Purpose

Ensure changes respect Voodoo's architectural invariants, layering rules, and compatibility patterns before they land in `main`.

---

## Prerequisites

1. Read `.github/copilot-instructions.md` — especially the 10 Architectural Invariants.
2. Read `.github/instructions/architecture.instructions.md` — layering and module boundaries.
3. Have the diff or PR open for review.

---

## Review Checklist

### 1. Architectural Invariants (all 10)

- [ ] **Zero-infra local dev** — No new required dependencies. Provider SDKs in optional extras.
- [ ] **No new required deps** — Base install stays minimal. New SDK? Add to `[extra]`.
- [ ] **Capability-based adapters** — Protocol + boolean flags. No enums for capabilities.
- [ ] **Contract tests immutable** — No changes to `tests/contracts/` mixin classes.
- [ ] **Compatibility shims** — Old import paths preserved (`sys.modules` or PEP 562).
- [ ] **Lazy imports** — Provider SDKs imported at function level.
- [ ] **Correlation IDs** — `trace_id` propagates through the stack.
- [ ] **Events namespaced** — Dotted names (`"agent.started"` not `"started"`).
- [ ] **Sprint discipline** — Changes match the current sprint scope.
- [ ] **Conventional Commits** — `type(scope): description` format.

### 2. Layering

- [ ] UI layer doesn't import from `storage/` or `runtime/` internals.
- [ ] AI layer doesn't import from `ui/` or `routing/`.
- [ ] Runtime layer doesn't import provider SDKs directly.
- [ ] Primitives layer has zero dependencies on other layers.
- [ ] Data layer doesn't import from `ai/` or `mesh/`.

### 3. Module Boundaries

- [ ] No circular imports (use function-level imports if needed).
- [ ] `__all__` present in every new module.
- [ ] `from __future__ import annotations` at top of every new module.
- [ ] Section dividers (`# ---...`) used to separate logical sections.

### 4. Error Handling

- [ ] Uses `VoodooError` hierarchy (`voodoo.core.errors`).
- [ ] Broad excepts use `# noqa: BLE001` and log context.
- [ ] No silent exception swallowing.

### 5. Testing

- [ ] Tests use `MockProvider` for AI — no real API calls.
- [ ] Fresh instances per test — no shared mutable state.
- [ ] Contract tests unchanged if adapter modified.
- [ ] Failure-path tests for durability claims.

### 6. Quality Gate

- [ ] `just format` passes.
- [ ] `just lint` passes (ruff).
- [ ] `just test` passes.
- [ ] `uv run mypy src/voodoo` passes (not in lint gate, but required for type safety).

### 7. PR & Repo Rules

> See `.github/instructions/pull-request.instructions.md` for full details.

- [ ] Branch follows `type/scope` naming.
- [ ] Commits follow Conventional Commits.
- [ ] PR template filled completely.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] No new required dependencies (optional extras only).
- [ ] `__all__` updated if public exports changed.
- [ ] Zero-infra local dev still works.
- [ ] CI will pass on Python 3.12 + 3.13.
- [ ] Ready for Code Owner review (1 approval required).
- [ ] Squash merge will be used (linear history required).

### 8. Documentation Sync (Mandatory)

> If code behavior changed but docs didn't, **request changes**. See `.github/instructions/pull-request.instructions.md` → "Documentation Sync" for the full mapping table.

- [ ] `CHANGELOG.md` has entries under `[Unreleased]` for all behavior changes.
- [ ] `docs/*.md` updated for the affected source paths (use the source-path-to-doc mapping).
- [ ] `README.md` updated if user-facing feature added or CLI changed.
- [ ] `SPRINT_PLAN.md` updated if sprint scope changed.
- [ ] `ROADMAP.md` updated if milestones changed.
- [ ] `ARCHITECTURE.md` updated if architectural layer or primitive changed.
- [ ] `test_contract_api.py` updated if public API changed.
- [ ] Code examples in docs are runnable (no stale imports or removed APIs).

---

## Review Report Template

```markdown
## Architecture Review: [PR/branch name]

### Summary
[1-2 sentence summary of the changes]

### Invariants Check
- [PASS/FAIL] Zero-infra local dev
- [PASS/FAIL] No new required deps
- [PASS/FAIL] Capability-based adapters
- [PASS/FAIL] Contract tests immutable
- [PASS/FAIL] Compatibility shims
- [PASS/FAIL] Lazy imports
- [PASS/FAIL] Correlation IDs
- [PASS/FAIL] Events namespaced
- [PASS/FAIL] Sprint discipline
- [PASS/FAIL] Conventional Commits

### Layering Check
- [PASS/FAIL] UI → AI → Realtime → Worker → Runtime → Primitives → Data → Infrastructure

### Issues Found
1. [issue description + file:line]
2. ...

### Recommendation
[APPROVE / REQUEST CHANGES / BLOCK]
```

---

## Post-Review

1. If issues found, create review comments on the PR.
2. If blocking issues, request changes.
3. If all pass, approve.
4. Update `CHANGELOG.md` if the review surfaces behavioral changes.
