# Skill: Release

> **When to use:** When cutting a published Voodoo framework release.

---

## Purpose

Run the repository's explicit release workflow without confusing merged work,
sprint completion, source version state, and a version that is actually published.

The source of truth is `.github/workflows/release.yml`. The convenience command is:

```bash
just release X.Y.Z
```

This dispatches the Release workflow on `main` with the requested semantic version.

---

## Preconditions

Before triggering a release:

1. `main` is the exact code you intend to publish and required CI/security gates are green.
2. The requested version is valid SemVer and does not already exist on PyPI/GitHub.
3. `CHANGELOG.md` describes the release truth.
4. `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `SPRINT_PLAN.md` and
   public API docs are already reconciled when the release changes their claims.
5. There is no unmerged release-critical fix sitting on another branch.

Sprint completion does **not** automatically imply a release, and a merge does
**not** make a version published.

---

## Version selection

Choose the version from compatibility impact, not from sprint number:

| Change | SemVer |
|---|---|
| Backward-compatible feature/capability | Minor |
| Backward-compatible bug fix | Patch |
| Intentional incompatible public contract change | Major |

Voodoo 3.0.0 is the current major architecture baseline. A future major bump
requires an explicit breaking-contract decision; it is never tied to a hardcoded sprint.

Check the current source version:

```bash
grep __version__ src/voodoo/__init__.py
```

The release workflow can update `src/voodoo/__init__.py` to the requested version.
Do not create a second manual bump path.

---

## Release preparation

### 1. Finalize changelog truth

Keep an `[Unreleased]` section and add/finalize the version section being released:

```markdown
## [Unreleased]

## [3.1.0] — YYYY-MM-DD

### Added
- ...

### Changed
- ...
```

Use a PR for release-preparation documentation changes when needed. Do not
direct-push ordinary prep work to protected `main`.

### 2. Verify the release baseline

From up-to-date `main`:

```bash
just format
just lint
just test
uv run mypy src/voodoo
```

The Release workflow runs its own test suite and clean Store-first distribution
gate again; local success does not replace that gate.

---

## Trigger the release

```bash
just release X.Y.Z
```

`just release` runs:

```bash
gh workflow run release.yml --ref main -f version=X.Y.Z
```

The GitHub Actions workflow then:

1. validates the requested SemVer;
2. installs dependencies and runs the full test suite;
3. builds a clean wheel and proves a fresh Store-first application works without
   accidental optional SQLite coupling;
4. updates `src/voodoo/__init__.py` when necessary;
5. commits the version state and creates/pushes `vX.Y.Z`;
6. builds wheel and source distributions;
7. publishes to PyPI;
8. updates the Homebrew formula when credentials are configured;
9. creates the GitHub Release and uploads distribution assets.

Only after all required publishing steps succeed should docs call the version
"published."

---

## Verification

Check the workflow:

```bash
gh run list --workflow=release.yml --limit 1
```

Then verify all applicable artifacts:

```bash
gh release view vX.Y.Z
pip index versions voodoo-framework
```

Confirm:

- [ ] Release workflow concluded successfully.
- [ ] Git tag `vX.Y.Z` points at the intended release commit.
- [ ] PyPI exposes `voodoo-framework==X.Y.Z`.
- [ ] GitHub Release exists with wheel/source assets.
- [ ] Homebrew formula was updated when that integration was enabled.
- [ ] `SPRINT_PLAN.md` / `ROADMAP.md` do not claim an older release as current.

---

## Failure / rollback policy

If publishing fails **before** PyPI/tag creation, fix the workflow or source
problem and retry only after confirming what artifacts were created.

If a broken version is already published, do not silently reuse the same version
or rewrite release history. Prefer:

1. fix the defect through the normal PR/CI path;
2. cut a new patch release;
3. yank the broken PyPI release only when appropriate for users, while keeping
   the historical artifact/version identity intact;
4. document any migration or incident that materially affects users.

Never delete/recreate a published tag merely to make a failed release look clean.

---

## Release checklist

- [ ] Intended `main` commit is green.
- [ ] Version follows SemVer and is unused.
- [ ] Changelog/docs describe release truth.
- [ ] `just release X.Y.Z` dispatched the workflow.
- [ ] Test suite passed in the release workflow.
- [ ] Clean Store-first distribution gate passed.
- [ ] Tag created.
- [ ] PyPI publication succeeded.
- [ ] GitHub Release/assets created.
- [ ] Homebrew update verified when applicable.
- [ ] Trackers updated to the actually published version.
