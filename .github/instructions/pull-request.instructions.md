# Pull Request & Repository Rules

> **Read this before:** creating a PR, merging to `main`, or modifying GitHub repository settings.

---

## Branch Protection Rules (`main`)

The `main` branch is protected. The following rules are enforced:

| Rule | Value | Effect |
|---|---|---|
| **Require a pull request before merging** | ✅ Enabled | No direct pushes to `main` |
| **Required approvals** | 1 | At least one reviewer must approve |
| **Require review from Code Owners** | ✅ Enabled | CODEOWNERS rules enforced (see `.github/CODEOWNERS`) |
| **Enforce for administrators** | ✅ Enabled | Rules apply to admins too — no `--admin` bypass |
| **Required status checks** | `CI` | The CI workflow must pass before merge |
| **Require linear history** | ✅ Enabled | No merge commits — squash or rebase only |
| **Require conversation resolution** | ✅ Enabled | All review comments must be resolved before merge |
| **Allow force pushes** | ❌ Disabled | No force pushes to `main` |
| **Allow deletions** | ❌ Disabled | `main` cannot be deleted |

### Implications

1. **No direct commits to `main`** — All changes go through a PR.
2. **No `--admin` bypass** — Even repository admins must follow the rules. If you need to bypass (e.g., fixing a broken CI), temporarily disable `enforce_admins`, merge, then re-enable.
3. **Squash merge only** — Linear history is required. Use `gh pr merge --squash`.
4. **All conversations must be resolved** — Don't leave unresolved review comments.
5. **CI must be green** — The `CI` status check must pass before the merge button is available.

---

## Code Owners (`.github/CODEOWNERS`)

Code Owners are automatically requested for review on PRs touching their paths:

| Path | Owner |
|---|---|
| `src/voodoo/__init__.py`, `core/`, `api.py`, `config.py`, `components.py`, `routing/` | `@helderperez-dev` |
| `src/voodoo/primitives/` | `@helderperez-dev` |
| `src/voodoo/data/`, `storage/`, `adapters/` | `@helderperez-dev` |
| `src/voodoo/ai/`, `agent.py`, `tools/`, `mcp/` | `@helderperez-dev` |
| `src/voodoo/mesh/`, `workers/`, `queue.py`, `schedule.py` | `@helderperez-dev` |
| `src/voodoo/auth/`, `security/`, `telemetry/` | `@helderperez-dev` |
| `src/voodoo/ui/`, `theme.py`, `i18n.py`, `seo.py` | `@helderperez-dev` |
| `src/voodoo/cli/` | `@helderperez-dev` |
| `tests/` | `@helderperez-dev` |

When adding new top-level directories under `src/voodoo/`, add them to `.github/CODEOWNERS`.

---

## PR Creation Process

### Step 1: Create a Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feat/<scope>
# or
git checkout -b fix/<scope>
git checkout -b docs/<scope>
git checkout -b refactor/<scope>
git checkout -b chore/<scope>
```

**Branch naming:** `type/scope` (e.g., `feat/agent-memory`, `fix/pg-fk-ordering`, `docs/runtime`).

### Step 2: Implement Changes

Follow the architectural rules in `.github/copilot-instructions.md` and the relevant instruction files in `.github/instructions/`.

### Step 3: Quality Gate (Local)

```bash
just format && just lint && just test
```

All three must pass locally before pushing. Also run:

```bash
uv run mypy src/voodoo
```

### Step 4: Commit with Conventional Commits

```bash
git add -A
git commit -m "feat(scope): concise description

- Detail 1
- Detail 2

Closes #issue"
```

**Format:** `type(scope): description`

| Type | When |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructuring, no behavior change |
| `test` | Add or fix tests |
| `chore` | Dependency updates, config, tooling |
| `ci` | CI/CD changes |
| `perf` | Performance improvement |
| `style` | Formatting, no code change |

**Common scopes:** `core`, `runtime`, `ai`, `ui`, `data`, `mesh`, `mcp`, `workers`, `auth`, `security`, `telemetry`, `cli`, `config`, `ci`, `docs`.

### Step 5: Push and Create PR

```bash
git push -u origin feat/<scope>
```

Create the PR using the template (`.github/PULL_REQUEST_TEMPLATE.md`):

```bash
gh pr create \
  --title "feat(scope): concise description" \
  --body "## Description
...
## Type of change
- [ ] Bug fix
- [ ] New feature
...
## Quality gate
- [x] just format
- [x] just lint
- [x] just test
..."
```

### Step 6: Fill the PR Template

The PR template (`.github/PULL_REQUEST_TEMPLATE.md`) requires:

1. **Description** — What and why. Link related issues (`Closes #N`).
2. **Type of change** — Check the appropriate box.
3. **Changes** — List key changes.
4. **Quality gate** — Confirm `just format`, `just lint`, `just test` pass.
5. **Testing** — Describe how you tested. Check for unit tests, contract tests, failure-path tests.
6. **Checklist** — Conventional Commits, no new required deps, `__all__` updated, `CHANGELOG.md` updated, docs updated, zero-infra works.

---

## CI Requirements

The CI workflow (`.github/workflows/ci.yml`) runs on every PR to `main`:

### Jobs

| Job | What it does | Timeout |
|---|---|---|
| **Lint & Format Check** | `ruff format --check .` + `ruff check .` | 5 min |
| **Test Suite (Python 3.12)** | Full pytest suite with service containers | 15 min |
| **Test Suite (Python 3.13)** | Same suite on 3.13 | 15 min |

### Service Containers

CI spins up real services for contract tests:

| Service | Image | Env var | Tests |
|---|---|---|---|
| PostgreSQL | `postgres:16` | `VOODOO_TEST_DATABASE_URL` | `test_database_postgres.py`, `test_queue_postgres.py`, `test_eventbus_postgres.py`, `test_execution_postgres.py` |
| MinIO (S3) | `minio/minio` | `VOODOO_TEST_S3_ENDPOINT` | `test_objectstore_s3.py` |
| Redis | `redis:7` | `VOODOO_TEST_REDIS_URL` | `test_queue_redis.py`, `test_cache_redis.py` |

### What CI Checks

1. **Formatting** — `ruff format --check .` (must match `just format` output).
2. **Linting** — `ruff check .` (must match `just lint` output).
3. **Tests** — `uv run pytest --tb=short` (must match `just test` output).
4. **Both Python versions** — 3.12 and 3.13 must both pass.

### CI Failure Recovery

If CI fails:

1. **Read the failure** — Check the Actions tab or `gh run view`.
2. **Fix locally** — Reproduce with `just format && just lint && just test`.
3. **Push the fix** — CI re-runs automatically on push.
4. **Don't bypass** — Don't disable branch protection to merge a failing PR. Fix the issue.

---

## Merge Process

### Before Merging

1. **CI is green** — Both Python 3.12 and 3.13 jobs pass.
2. **Review approved** — At least one Code Owner has approved.
3. **Conversations resolved** — All review comments are marked resolved.
4. **Linear history** — No merge commits on the branch (rebase if needed).

### Merge Command

```bash
gh pr merge --squash --delete-branch
```

**Why squash?** Branch protection requires linear history. Squash merges compress all commits into one, keeping `main`'s history clean.

### After Merging

1. **Delete the branch** — `--delete-branch` in the merge command, or manually:
   ```bash
   git branch -d feat/<scope>
   git push origin --delete feat/<scope>
   ```
2. **Pull main** — Update local main:
   ```bash
   git checkout main
   git pull origin main
   ```
3. **Release** (if sprint is complete):
   ```bash
   just release X.Y.Z
   ```
4. **Update trackers** — `SPRINT_PLAN.md`, `CHANGELOG.md`, `ROADMAP.md`.

---

## Emergency Bypass (Use Sparingly)

If branch protection blocks a critical fix (e.g., CI is broken and the fix can't pass the check it's fixing):

### Option A: Temporarily Relax Rules

```bash
# Disable enforce_admins
gh api repos/helderperez-dev/voodoo/branches/main/protection \
  -X PUT \
  -f required_pull_request_reviews_enforce_admins=false

# Merge with --admin
gh pr merge <PR_NUMBER> --squash --admin

# RE-ENABLE immediately
gh api repos/helderperez-dev/voodoo/branches/main/protection \
  -X PUT \
  -f required_pull_request_reviews_enforce_admins=true
```

### Option B: Hotfix Branch

1. Create a `hotfix/<scope>` branch from `main`.
2. Fix the issue.
3. Create a PR with minimal scope.
4. Get a fast review.
5. Merge normally.

**Never leave `enforce_admins` disabled.** Always re-enable immediately after the emergency merge.

---

## Other Repository Rules

### Issue Templates

- `.github/ISSUE_TEMPLATE/bug_report.md` — Bug reports
- `.github/ISSUE_TEMPLATE/feature_request.md` — Feature requests

Use these templates when opening issues. Link issues in PRs with `Closes #N`.

### Stale Bot

`.github/workflows/stale.yml` automatically marks issues and PRs as stale after 30 days of inactivity, and closes them after 7 more days. To keep an issue/PR alive, comment or add the `pinned` label.

### CodeQL Analysis

`.github/workflows/codeql.yml` runs GitHub's security analysis on every push to `main` and every PR. This is separate from the CI workflow.

### Labeler

`.github/workflows/labeler.yml` automatically labels PRs based on changed file paths (`.github/labeler.yml`). Labels include `type:bug`, `type:feature`, `type:docs`, `area:core`, `area:ai`, etc.

### Release Workflow

`.github/workflows/release.yml` triggers on tag push (`v*`). It:
1. Builds the package.
2. Publishes to PyPI.
3. Creates a GitHub Release with notes from `CHANGELOG.md`.

Trigger with:
```bash
just release X.Y.Z
```

---

## Documentation Sync (Mandatory)

> **Every feature, behavior change, or API change MUST be accompanied by documentation updates.** A PR with code changes but no doc updates is incomplete and should be blocked in review.

### What to Update — by Change Type

| Change type | `CHANGELOG.md` | `docs/*.md` | `README.md` | `SPRINT_PLAN.md` | `ROADMAP.md` | `test_contract_api.py` | `ARCHITECTURE.md` |
|---|---|---|---|---|---|---|---|
| New feature | ✅ Added | ✅ Create/update `docs/<feature>.md` | ✅ If user-facing | ✅ Sprint scope | ✅ If milestone | ✅ If public API | ✅ If new layer/primitive |
| Bug fix | ✅ Fixed | ⚠️ If behavior changed | ❌ | ❌ | ❌ | ❌ | ❌ |
| Breaking change | ✅ Changed | ✅ All affected | ✅ | ✅ | ✅ | ✅ | ⚠️ If architectural |
| Refactor (no behavior change) | ⚠️ If notable | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| New provider/adapter | ✅ Added | ✅ `docs/deployment.md` + area doc | ⚠️ If major | ✅ | ✅ | ✅ Contract tests | ❌ |
| New public API | ✅ Added | ✅ Area doc | ⚠️ If user-facing | ✅ | ❌ | ✅ | ❌ |
| New optional extra | ✅ Added | ✅ `docs/installation.md` | ✅ Features list | ✅ | ❌ | ❌ | ❌ |
| Sprint completion | ✅ Released | ⚠️ If behavior changed | ❌ | ✅ Mark DONE | ✅ Check milestone | ❌ | ❌ |
| Docs-only change | ❌ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |

Legend: ✅ = required, ⚠️ = conditional, ❌ = not needed.

### Documentation Mapping by Source Path

| Source path changed | Doc to update |
|---|---|
| `src/voodoo/__init__.py` | `docs/architecture.md`, `README.md` (public API), `test_contract_api.py` |
| `src/voodoo/core/` | `docs/architecture.md`, `docs/routing.md` |
| `src/voodoo/primitives/` | `docs/primitives.md`, `docs/architecture.md` |
| `src/voodoo/runtime/` | `docs/runtime.md`, `docs/adaptive.md`, `docs/hitl.md` |
| `src/voodoo/ai/` | `docs/agents.md`, `docs/tools.md` |
| `src/voodoo/agent.py` | `docs/agents.md` |
| `src/voodoo/tools/` | `docs/tools.md` |
| `src/voodoo/mcp/` | `docs/mcp.md` |
| `src/voodoo/mesh/` | `docs/mesh.md`, `docs/events.md` |
| `src/voodoo/workers/` | `docs/workers.md` |
| `src/voodoo/queue.py` | `docs/workers.md` |
| `src/voodoo/schedule.py` | `docs/workers.md` |
| `src/voodoo/data/` | `docs/data.md` |
| `src/voodoo/storage/` | `docs/data.md`, `docs/deployment.md` |
| `src/voodoo/adapters/` | `docs/deployment.md` |
| `src/voodoo/ui/` | `docs/components.md`, `docs/design_system.md` |
| `src/voodoo/components.py` | `docs/components.md` |
| `src/voodoo/theme.py` | `docs/design_system.md` |
| `src/voodoo/routing/` | `docs/routing.md` |
| `src/voodoo/auth/` | `docs/auth.md` |
| `src/voodoo/security/` | `docs/deployment.md` |
| `src/voodoo/telemetry/` | `docs/telemetry.md` |
| `src/voodoo/cli/` | `README.md` (CLI commands) |
| `src/voodoo/config.py` | `docs/installation.md`, `docs/deployment.md` |
| `src/voodoo/i18n.py` | `docs/components.md` |
| `src/voodoo/seo.py` | `docs/components.md` |
| `src/voodoo/status.py` | `docs/deployment.md` |
| `tests/contracts/` | `docs/deployment.md` (provider matrix) |

### CHANGELOG.md Format

Follow [Keep a Changelog](https://keepachangelog.com/). Entries go under `## [Unreleased]`:

```markdown
## [Unreleased]

### Added
- New feature X with brief description
- New provider Y for Z

### Changed
- Behavior of X is now Y
- API signature changed: `func(a)` → `func(a, b)`

### Fixed
- Bug in module W causing Z

### Deprecated
- Old API path (will be removed in v1.0)

### Removed
- Removed deprecated feature V

### Security
- Fixed vulnerability in auth
```

### Doc File Structure (Required Sections)

Every `docs/*.md` file should have:

1. **Title** (`# Feature Name`)
2. **Overview** (1-2 sentences)
3. **Installation** (if optional extras needed)
4. **Quick Start** (minimal working example, < 20 lines)
5. **API Reference** (classes, functions, methods with signatures)
6. **Examples** (common use cases)
7. **Advanced** (configuration, edge cases)
8. **See Also** (relative links to related docs)

### Reviewer Rule

**If a PR adds or changes code behavior but doesn't update the relevant docs, request changes.** The only exception is a pure refactor with no behavior change — and even then, `CHANGELOG.md` should note it under `Changed` if notable.

---

## Checklist: Before Creating a PR

- [ ] Branch follows `type/scope` naming.
- [ ] Quality gate passes: `just format && just lint && just test`.
- [ ] Type check passes: `uv run mypy src/voodoo`.
- [ ] Commits follow Conventional Commits.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] `SPRINT_PLAN.md` updated if sprint scope changed.
- [ ] `docs/*.md` updated for changed behavior (see Documentation Sync table above).
- [ ] `README.md` updated if user-facing feature added.
- [ ] `ROADMAP.md` updated if milestones changed.
- [ ] `ARCHITECTURE.md` updated if architectural layer or primitive changed.
- [ ] `test_contract_api.py` updated if public API changed.
- [ ] PR template filled completely.
- [ ] No new required dependencies (optional extras only).
- [ ] Zero-infra local dev still works.

## Checklist: Before Merging

- [ ] CI is green (Python 3.12 + 3.13).
- [ ] At least one Code Owner approved.
- [ ] All review comments resolved.
- [ ] No merge commits on the branch (linear history).
- [ ] Branch is up to date with `main` (rebase if needed).
