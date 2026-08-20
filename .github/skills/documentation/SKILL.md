# Skill: Documentation

> **When to use:** When updating docs, writing new guides, or updating README/CHANGELOG/ROADMAP.

---

## Purpose

Ensure documentation stays accurate, comprehensive, and aligned with the codebase.

---

## Prerequisites

1. Read the existing documentation in `docs/`.
2. Read `.github/copilot-instructions.md` — File Organization and conventions.

---

## Documentation Structure

```
docs/
├── architecture.md       # System architecture overview
├── agents.md             # AI agents guide
├── adaptive.md           # Adaptive execution
├── auth.md               # Authentication
├── components.md         # UI components
├── data.md               # Async ORM
├── deployment.md         # Deployment guide
├── design_system.md      # Design system
├── events.md             # Event system
├── hello_world.md        # Getting started
├── hitl.md               # Human-in-the-loop
├── installation.md       # Installation guide
├── mcp.md                # MCP server/client
├── mesh.md               # Realtime mesh
├── primitives.md         # 8 architectural primitives
├── routing.md           # Page registry, API routing
├── runtime.md            # Execution engine
├── state.md              # State primitive
├── telemetry.md          # Telemetry
├── tools.md              # Tool registry
└── workers.md            # Background workers
```

Root-level docs:
- `README.md` — Project overview, quick start, links
- `CHANGELOG.md` — Versioned change log
- `ROADMAP.md` — High-level milestones
- `SPRINT_PLAN.md` — Detailed sprint breakdown
- `ARCHITECTURE.md` — Architecture reference (root-level)
- `AGENTS.md` — AI agent instructions (root-level)

---

## Workflow

> **This is mandatory.** A PR with code changes but no doc updates is incomplete and will be blocked in review. See `.github/instructions/pull-request.instructions.md` → "Documentation Sync" for the full source-path-to-doc mapping table.

### Step 1: Identify What to Update

Use the **source-path-to-doc mapping** in `.github/instructions/pull-request.instructions.md` → "Documentation Sync" to determine which docs to update based on which source files changed.

| Change | Update |
|---|---|
| New feature | `docs/<feature>.md`, `README.md`, `CHANGELOG.md`, `SPRINT_PLAN.md` |
| Bug fix | `CHANGELOG.md` (and `docs/<area>.md` if behavior changed) |
| API change | `docs/<area>.md`, `test_contract_api.py`, `CHANGELOG.md` |
| Sprint completed | `SPRINT_PLAN.md`, `CHANGELOG.md`, `ROADMAP.md` |
| New sprint | `SPRINT_PLAN.md`, `ROADMAP.md` |
| Behavior change | `docs/<area>.md`, `CHANGELOG.md` |
| New provider | `docs/deployment.md`, `CHANGELOG.md`, `SPRINT_PLAN.md` |
| New architectural layer/primitive | `ARCHITECTURE.md`, `docs/primitives.md`, `CHANGELOG.md` |
| New optional extra | `docs/installation.md`, `README.md`, `CHANGELOG.md` |

### Step 2: Update CHANGELOG.md

Follow the [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
# Changelog

## [Unreleased]

### Added
- New feature X
- New provider Y

### Changed
- Behavior of Z is now...

### Fixed
- Bug in module W

### Deprecated
- Old API path (will be removed in v1.0)

### Removed
- Removed deprecated feature V

### Security
- Fixed vulnerability in auth
```

Rules:
- Entries under `[Unreleased]` until a release.
- Use Conventional Commit-style descriptions.
- Group by: Added, Changed, Fixed, Deprecated, Removed, Security.

### Step 3: Update docs/*.md

Each doc file should have:

1. **Title** — `# Feature Name`
2. **Overview** — 1-2 sentence description.
3. **Installation** — If the feature needs optional extras.
4. **Quick Start** — Minimal working example.
5. **API Reference** — Classes, functions, methods.
6. **Examples** — Common use cases.
7. **Advanced** — Configuration, edge cases.
8. **See Also** — Links to related docs.

### Step 4: Update README.md

The README should have:
1. **Project name + tagline**
2. **Badges** (CI, version, license)
3. **Quick start** — Install + hello world in < 10 lines.
4. **Features** — Bullet list of key features.
5. **Documentation** — Links to `docs/*.md`.
6. **Development** — Quick reference (quality gate, sprint protocol).
7. **License**

### Step 5: Update SPRINT_PLAN.md

```markdown
## Sprint N: Sprint Name
**Status:** IN_PROGRESS  # TODO → IN_PROGRESS → DONE
**Goal:** ...

### Scope
- [x] Completed item
- [ ] Pending item

### Deliverables
- Deliverable 1
- Deliverable 2
```

### Step 6: Update ROADMAP.md

High-level milestones:

```markdown
## v0.6 — Runtime & Persistence
- [x] ExecutionEngine
- [x] SQLiteExecutionStore
- [ ] PostgresExecutionStore

## v0.7 — AI Agents
- [x] Agent class
- [x] Tool registry
- [ ] MCP integration
```

### Step 7: Quality Gate

```bash
just format && just lint && just test
```

Documentation changes don't affect tests, but run the gate to ensure nothing else broke.

### Step 8: Commit

```bash
git commit -m "docs(scope): update documentation for X"
```

---

## Style Guide

- **Markdown** — Use ATX headers (`#`, `##`, `###`).
- **Code blocks** — Specify language: ` ```python `, ` ```bash `, ` ```sql `.
- **Tables** — For structured data (APIs, comparisons).
- **Links** — Relative links to other docs: `[Runtime](runtime.md)`.
- **Examples** — Runnable code that works with `uv run python -c "..."` or in a file.
- **Tone** — Clear, concise, technical. No marketing language.

---

## Checklist

- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] `docs/*.md` updated for changed behavior (use source-path-to-doc mapping).
- [ ] `README.md` updated for user-facing changes.
- [ ] `SPRINT_PLAN.md` updated for sprint progress.
- [ ] `ROADMAP.md` updated for milestone changes.
- [ ] `ARCHITECTURE.md` updated if layer/primitive changed.
- [ ] `test_contract_api.py` updated if public API changed.
- [ ] Code examples are runnable (no stale imports or removed APIs).
- [ ] Links are relative and valid.
- [ ] Quality gate passes.
