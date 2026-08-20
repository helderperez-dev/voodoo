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
| Sprint completion | Minor | `0.5.0` → `0.6.0` |
| Bug fix | Patch | `0.6.0` → `0.6.1` |
| Breaking change | Major | `0.6.1` → `1.0.0` |

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

## [0.6.0] - 2025-01-15

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
## Sprint 5: Runtime & Persistence
**Status:** DONE  # was IN_PROGRESS
```

### Step 3: Update Version

In `src/voodoo/__init__.py`:

```python
__version__ = "0.6.0"  # was "0.5.0"
```

### Step 4: Commit the Release Prep

```bash
git add -A
git commit -m "chore(release): prepare v0.6.0

- Finalize CHANGELOG.md
- Mark Sprint 5 as DONE
- Bump version to 0.6.0"
```

### Step 5: Run the Release Command

```bash
just release 0.6.0
```

This command:
1. Creates a git tag `v0.6.0`.
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
gh release view v0.6.0

# Verify on PyPI
pip index versions voodoo-framework
```

### Step 7: Post-Release

1. **Update ROADMAP.md** — Mark the milestone as complete.
2. **Create a new `[Unreleased]` section** in `CHANGELOG.md`:

```markdown
## [Unreleased]

## [0.6.0] - 2025-01-15
...
```

3. **Commit post-release updates**:

```bash
git add -A
git commit -m "docs(release): post-release updates for v0.6.0"
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
pip run twine upload --repository pypi dist/voodoo_framework-0.6.0* --verbose
# Then yank:
# Go to https://pypi.org/manage/project/voodoo-framework/releases/
```

### Option B: Fast Patch Release

1. Fix the bug on `main`.
2. Bump patch version: `0.6.0` → `0.6.1`.
3. Add `CHANGELOG.md` entry under `[Unreleased]` → move to `[0.6.1]`.
4. Release: `just release 0.6.1`.

### Option C: Revert and Re-release

1. Revert the problematic commit: `git revert <commit>`.
2. Delete the tag: `git tag -d v0.6.0 && git push origin :refs/tags/v0.6.0`.
3. Fix the issue.
4. Re-run: `just release 0.6.0`.

---

## Checklist

- [ ] Sprint scope complete.
- [ ] Quality gate passes.
- [ ] Type check passes.
- [ ] `CHANGELOG.md` finalized.
- [ ] `SPRINT_PLAN.md` sprint marked `DONE`.
- [ ] Version bumped in `src/voodoo/__init__.py`.
- [ ] Release prep committed.
- [ ] `just release X.Y.Z` run.
- [ ] GitHub Actions release workflow succeeded.
- [ ] Package visible on PyPI.
- [ ] GitHub Release created.
- [ ] Post-release updates committed (ROADMAP, CHANGELOG `[Unreleased]`).
