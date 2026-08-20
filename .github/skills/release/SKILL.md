# Skill: Release

> **When to use:** When cutting a new release of the Voodoo framework.

---

## Purpose

Guide the structured release process, ensuring version bumps, changelog finalization, tag creation, and CI verification.

---

## Prerequisites

1. Read `.github/copilot-instructions.md` — Release section.
2. Ensure the current sprint's scope is complete.
3. Ensure the quality gate passes.

---

## Pre-Release Checklist

Before starting a release:

- [ ] Current sprint scope is complete (all items checked in `SPRINT_PLAN.md`).
- [ ] Quality gate passes: `just format && just lint && just test`.
- [ ] Type check passes: `uv run mypy src/voodoo`.
- [ ] `CHANGELOG.md` has entries under `[Unreleased]`.
- [ ] `SPRINT_PLAN.md` sprint is ready to mark `DONE`.
- [ ] Working tree is clean (no uncommitted changes).
- [ ] On `main` branch, up to date with remote.

---

## Version Bump Strategy

| Release Type | Version Bump | Example |
|---|---|---|
| Sprint completion | Minor | `1.16.0` → `1.17.0` |
| Bug fix | Patch | `1.16.0` → `1.16.1` |
| Breaking change | Major | `1.19.0` → `2.0.0` (Sprint 18 only) |

Check the current version:

```bash
grep __version__ src/voodoo/__init__.py
```

---

## Workflow

### Step 1: Finalize CHANGELOG.md

Move `[Unreleased]` entries to a new version section:

```markdown
## [Unreleased]

## [1.16.0] - YYYY-MM-DD

### Added
- ExecutionEngine with full lifecycle management
- SQLiteExecutionStore with WAL mode
- Checkpoint and recovery system

### Changed
- Agent now flows through ExecutionEngine

### Fixed
- PostgreSQL FK ordering in execution store
```

### Step 2: Mark Sprint as DONE

In `SPRINT_PLAN.md`:

```markdown
## Sprint 14: ModelProvider protocol
**Status:** DONE  # was TODO
```

### Step 3: Do NOT bump the version manually

`release.yml` bumps `src/voodoo/__init__.py` → `__version__` automatically
(via `sed`) at release time, then commits + tags + pushes. Leave `__version__`
at its current value — CI sets it.

### Step 4: Commit the Release Prep

```bash
git add -A
git commit -m "chore(release): prepare v0.6.0

- Finalize CHANGELOG.md1.16.0

- Finalize CHANGELOG.md
- Mark Sprint 14 as DONE"
git push origin main
```

> The version bump itself happens in CI — do **not** edit `__version__` here. Step 5: Run the Release Command
1.16.0
```

This runs `gh workflow run release.yml --ref main -f version=1.16.0`.
The GitHub Actions workflow then (fully automated):
1. Validates semver and runs the full test suite (`pytest`).
2. Bumps `__version__` in `src/voodoo/__init__.py`.
3. Commits + tags `v1.16.0` and pushes to `main` + the tag.
4. Builds distributions and publishes to PyPI.
5. Updates the Homebrew formula.
6. Creates the GitHub Release
2. Pushes the tag to GitHub.
3. Triggers the GitHub Actions release workflow.

### Step 6: Verify the Release Workflow

1. Go to GitHub → Actions → Release workflow.
2. Wait for the workflow to complete.
3. Verify:
   - [ ] Build succeeds.
   - [ ] Package is published to PyPI.
   - [ ] GitHub Release is created.
   - [ ] Release notes are populated from `CHANGELOG.md`.

```bash
# Check the workflow status
gh run list --workflow=release.yml --limit 1

# Check the release
gh release view v1.16.0

# Verify on PyPI
pip index versions voodoo-framework
```

### Step 7: Post-Release

1. **Update ROADMAP.md** — Mark the milestone as complete.
2. **Create a new `[Unreleased]` section** in `CHANGELOG.md`:

```markdown
## [Unreleased]

## [1.16.0] - YYYY-MM-DD
...
```

3. **Commit post-release updates**:

```bash
git add -A
git commit -m "docs(release): post-release updates for v1.16.0"
git push origin main
```

4. **Announce** (if applicable):
   - Update `README.md` badges with the new version.
   - Post in the project's communication channel.

---

## Rollback Procedure

If the release workflow fails or the release has a critical bug:

### Option A: Yank from PyPI

```bash
# Prevent new installs, but keep existing installs working
pip run twine upload --repository pypi dist/voodoo_framework-1.16.0* --verbose
# Then yank:
# Go to https://pypi.org/manage/project/voodoo-framework/releases/
```

### Option B: Fast Patch Release

1. Fix the bug on `main`.
2. Bump patch version: `1.16.0` → `1.16.1`.
3. Add `CHANGELOG.md` entry under `[Unreleased]` → move to `[1.16.1]`.
4. Release: `just release 1.16.1`.

### Option C: Revert and Re-release

1. Revert the problematic commit: `git revert <commit>`.
2. Delete the tag: `git tag -d v1.16.0 && git push origin :refs/tags/v1.16.0`.
3. Fix the issue.
4. Re-run: `just release 1.16.0`.

---

## Checklist

- [ ] Sprint scope complete.
- [ ] Quality gate passes.
- [ ] Type check passes.
- [ ] `CHANGELOG.md` finalized.
- [ ] `SPRINT_PLAN.md` sprint marked `DONE`.
- [ ] Version auto-bumped by `release.yml` (verified on PyPI).
- [ ] Release prep committed.
- [ ] `just release X.Y.Z` run.
- [ ] GitHub Actions release workflow succeeded.
- [ ] Package visible on PyPI.
- [ ] GitHub Release created.
- [ ] Post-release updates committed (ROADMAP, CHANGELOG `[Unreleased]`).
