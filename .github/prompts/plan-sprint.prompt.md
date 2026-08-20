# Plan Sprint

> **Purpose:** Analyze the current state of the Voodoo project and plan the next sprint's scope, deliverables, and task breakdown.

---

## Instructions

You are planning the next sprint for the Voodoo framework. Follow this structured process to define the sprint scope.

### 1. Assess Current State

1. Read `SPRINT_PLAN.md` — identify the last completed sprint and the next planned sprint.
2. Read `ROADMAP.md` — identify the current milestone and what remains.
3. Read `CHANGELOG.md` — understand what was recently delivered.
4. Run the quality gate to verify the codebase is healthy:
   ```bash
   just format && just lint && just test
   ```
5. Check for open issues and PRs:
   ```bash
   gh issue list --state open
   gh pr list --state open
   ```

### 2. Define Sprint Goal

Based on the ROADMAP milestone and the next sprint in `SPRINT_PLAN.md`:

- What is the primary outcome of this sprint?
- What user-facing capability does this unlock?
- What architectural foundation does this lay?

Write a 1-2 sentence sprint goal.

### 3. Define Scope Items

Break the sprint goal into concrete, checkable scope items:

- Each item should be independently implementable.
- Each item should be testable.
- Each item should map to a specific module or set of modules.
- Items should build on each other logically.

For each scope item, identify:
- **What:** The feature or change.
- **Where:** Which modules/files are affected.
- **How:** High-level implementation approach.
- **Tests:** What tests need to be written.
- **Dependencies:** Does this depend on other scope items?

### 4. Identify Deliverables

What concrete artifacts will exist at the end of this sprint?

- New modules or classes.
- New tests.
- New documentation.
- New CLI commands.
- New examples.
- Updated public API.

### 5. Identify Risks

- **Technical risks:** Circular imports, performance, compatibility.
- **Dependency risks:** New SDK versions, missing optional deps.
- **Testing risks:** Hard-to-test features, missing service containers.
- **Documentation risks:** Outdated docs, missing examples.

For each risk, define a mitigation.

### 6. Estimate Effort

For each scope item, estimate:
- **Complexity:** S/M/L (Small/Medium/Large)
- **Files touched:** Approximate count
- **New tests needed:** Approximate count
- **Dependencies:** On other items or external work

### 7. Define Sprint Exit Criteria

What must be true for the sprint to be considered complete?

- [ ] All scope items implemented.
- [ ] Quality gate passes (`just format && just lint && just test`).
- [ ] Type check passes (`uv run mypy src/voodoo`).
- [ ] `CHANGELOG.md` updated.
- [ ] `SPRINT_PLAN.md` updated.
- [ ] `docs/*.md` updated if behavior changed.
- [ ] `test_contract_api.py` updated if public API changed.
- [ ] PR merged to `main`.
- [ ] Release published.

### 8. Update SPRINT_PLAN.md

Write the sprint plan in `SPRINT_PLAN.md`:

```markdown
## Sprint N: Sprint Name
**Status:** TODO
**Goal:** [1-2 sentence goal]

### Scope
- [ ] Scope item 1
- [ ] Scope item 2
- [ ] Scope item 3

### Deliverables
- Deliverable 1
- Deliverable 2

### Risks
| Risk | Mitigation |
|---|---|
| Risk 1 | Mitigation 1 |

### Effort
| Item | Complexity | Files | Tests |
|---|---|---|---|
| Item 1 | S | 2 | 3 |
| Item 2 | M | 5 | 8 |

### Exit Criteria
- [ ] All scope items implemented
- [ ] Quality gate passes
- [ ] ...
```

---

## Output Format

Produce:

1. **Updated `SPRINT_PLAN.md`** — with the new sprint defined.
2. **Sprint planning summary** — A brief message to the team:

```markdown
## Sprint N Planning Complete

**Sprint:** N — [Name]
**Goal:** [goal]
**Scope items:** X
**Estimated effort:** [S/M/L breakdown]
**Key risks:** [top 2-3 risks]

### Next Steps
1. Create branch: `git checkout -b feat/sprint-N`
2. Start with scope item 1
3. Follow the implement-sprint skill
```
