# Skill: Implement Sprint

> **When to use:** When starting work on a new sprint from `SPRINT_PLAN.md`.

---

## Purpose

Guide the structured implementation of a sprint's scope, ensuring all items are completed, tested, and released following the Voodoo development process.

---

## Prerequisites

1. Read `SPRINT_PLAN.md`.
2. Continue only if the tracker explicitly declares a sprint `TODO` or `IN_PROGRESS`.
   If the tracker is at a selection gate, stop: do not invent the next sprint number.
3. Read `.github/copilot-instructions.md` and the relevant instruction files for the declared scope.

---

## Workflow

### Step 1: Identify Sprint Scope

1. Open `SPRINT_PLAN.md`.
2. Find the explicitly declared sprint with status `TODO` or `IN_PROGRESS`.
3. If none exists, return to the product/architecture selection gate instead of creating one.
4. Read the sprint's scope items, goals, deliverables and acceptance criteria.
5. Note dependencies on previous sprints and the current published architecture baseline.

### Step 2: Create Branch

```bash
git checkout main
git pull origin main
git checkout -b feat/sprint-N
```

### Step 3: Plan Implementation

1. Break the sprint scope into tasks.
2. For each task, identify:
   - Files to create/modify.
   - Instruction files to read.
   - Tests to write.
   - Contract tests to update (if adapter changes).
   - Public API changes (update `test_contract_api.py`).

### Step 4: Implement

For each task in the sprint scope:

1. **Read the relevant instruction file** (architecture, runtime, providers, execution, ai, testing).
2. **Implement the change** following architectural rules:
   - `from __future__ import annotations` at top.
   - Type hints everywhere.
   - `__all__` export list.
   - Section dividers.
   - Docstrings with `Parameters` sections.
3. **Write tests** alongside implementation:
   - Test classes group related tests.
   - Fresh instances per test.
   - MockProvider for AI tests.
   - Failure-path tests for durability.
4. **Update contract tests** if adapter changes (never modify mixin — add provider-specific).
5. **Update public API** if exports changed → update `test_contract_api.py`.

### Step 5: Quality Gate

```bash
just format && just lint && just test
```

All three must pass. If any fail:

1. Fix formatting: `just format`.
2. Fix lint errors: `just lint` (ruff).
3. Fix test failures.
4. Run type check: `uv run mypy src/voodoo` (not in lint gate, but required).
5. Re-run the full gate.

### Step 6: Update Documentation

> **Mandatory:** Every feature or behavior change MUST be accompanied by documentation updates. A PR with code changes but no doc updates is incomplete and will be blocked in review. See `.github/instructions/pull-request.instructions.md` → "Documentation Sync" for the full mapping table.

1. Update `CHANGELOG.md` — add entries under `[Unreleased]` (Added/Changed/Fixed/Deprecated/Removed/Security).
2. Update `SPRINT_PLAN.md`:
   - Mark completed scope items.
   - If sprint is complete, mark status `DONE`.
3. Update `ROADMAP.md` if milestones changed.
4. Update `README.md` if user-facing features changed (features list, quick start, CLI commands).
5. Update relevant `docs/*.md` if behavior changed. Canonical examples:
   - `src/voodoo/runtime/scheduling/` → workers/scheduling/runtime docs
   - `src/voodoo/runtime/agency/` → adaptive/goal/runtime docs
   - `src/voodoo/runtime/distributed/` → protocol/deployment/runtime docs
   - `src/voodoo/world/` → World/ontology docs
   - `src/voodoo/edge/` → Edge/protocol/deployment docs
   - `src/voodoo/ai/` → `docs/agents.md`, `docs/tools.md`
   - `src/voodoo/integrations/mcp/` → `docs/mcp.md`
   - `src/voodoo/observability/` → observability/telemetry docs
   - `src/voodoo/data/`, `storage/`, `adapters/` → data/deployment docs
   - `src/voodoo/ui/` → component/design-system docs
   - (Full table in `.github/instructions/pull-request.instructions.md`)
6. Update `ARCHITECTURE.md` if a new architectural layer or primitive was added.
7. Update `tests/integration/test_contract_api.py` and `docs/public-api-3.md` if the public API changed.

### Step 7: Commit

Use Conventional Commits:

```bash
git add -A
git commit -m "feat(scope): implement sprint N scope item

- Detail 1
- Detail 2

Closes #issue"
```

Common scopes: `core`, `runtime`, `scheduling`, `world`, `edge`, `protocol`, `ai`, `integrations`, `observability`, `ui`, `data`, `mesh`, `auth`, `security`, `cli`, `config`, `ci`, `docs`.

### Step 8: Push and PR

> **Read `.github/instructions/pull-request.instructions.md`** for full PR governance rules, branch protection config, and the PR template.

```bash
git push -u origin feat/sprint-N
gh pr create --title "feat(scope): Sprint N — <sprint name>" --body "$(cat .github/PULL_REQUEST_TEMPLATE.md)"
```

**PR template requirements** (`.github/PULL_REQUEST_TEMPLATE.md`):
- Description with `Closes #N` issue link.
- Type of change checked.
- Key changes listed.
- Quality gate checkboxes confirmed.
- Testing approach described.
- Checklist completed (Conventional Commits, no new required deps, `__all__`, `CHANGELOG.md`, docs, zero-infra).

### Step 9: CI and Review

**Branch protection on `main`:**
- 1 approval required (Code Owner review enforced).
- Required status check: `CI` (lint + test on Python 3.12 + 3.13).
- Linear history required (squash merge only).
- Conversation resolution required (all comments resolved).
- Follow the protection policy documented in
  `.github/instructions/pull-request.instructions.md`; do not assume an admin
  bypass is available or appropriate.

**CI jobs:**
| Job | What | Timeout |
|---|---|---|
| Lint & Format Check | `ruff format --check .` + `ruff check .` | 5 min |
| Test Suite (Python 3.12) | Full pytest with PostgreSQL, MinIO, Redis | 15 min |
| Test Suite (Python 3.13) | Same suite on 3.13 | 15 min |

1. Wait for CI to pass (all jobs green).
2. Get at least one Code Owner approval.
3. Address all review comments.
4. Resolve all conversations (mark as resolved).
5. Rebase if needed to maintain linear history.

### Step 10: Merge and Release

```bash
# After PR approved, CI green, all conversations resolved
gh pr merge N --squash --delete-branch

# Release (if sprint is complete) — release.yml auto-bumps __version__,
# tags vX.Y.Z, pushes, builds, and publishes PyPI + Homebrew + GitHub Release.
just release X.Y.Z
# Choose the version from the actual compatibility/feature impact.
# Sprint completion does not automatically imply a release or a fixed bump type.
```

**Merge strategy:** Squash merge only (linear history required). The `--delete-branch` flag cleans up the remote branch automatically.

### Step 11: Verify Release

1. Check GitHub Actions release workflow succeeded.
2. Verify the new version is on PyPI: `pip index versions voodoo-framework`.
3. Reconcile `SPRINT_PLAN.md` and `ROADMAP.md` with the published release checkpoint.
4. Do not describe a version as published until the release workflow succeeds.

---

## Sprint Scope Checklist

Before marking a sprint `DONE`, verify:

- [ ] All checked scope items implemented.
- [ ] Quality gate passes (`just format && just lint && just test`).
- [ ] `uv run mypy src/voodoo` passes.
- [ ] `CHANGELOG.md` updated.
- [ ] `SPRINT_PLAN.md` updated.
- [ ] `ROADMAP.md` updated if milestones changed.
- [ ] `README.md` updated if user-facing features changed.
- [ ] `docs/*.md` updated if behavior changed.
- [ ] `tests/integration/test_contract_api.py` and `docs/public-api-3.md` updated if public API changed.
- [ ] PR merged to `main`.
- [ ] Release published (`just release X.Y.Z`).
- [ ] Release workflow succeeded.
- [ ] Sprint marked `DONE` in `SPRINT_PLAN.md`.
