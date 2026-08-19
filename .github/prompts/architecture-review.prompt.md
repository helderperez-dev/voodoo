# Architecture Review

> **Purpose:** Perform a structured architecture review of a PR, branch, or set of changes before merging to `main`.

---

## Instructions

You are performing an architecture review of changes in the Voodoo framework. Follow this structured process to identify violations, risks, and improvements.

### 1. Gather Context

1. Identify the changes to review:
   ```bash
   # For a PR
   gh pr view <PR_NUMBER> --json title,body,files,additions,deletions

   # For a branch
   git diff main...<branch> --stat
   git log main..<branch> --oneline
   ```

2. Read the relevant instruction files:
   - `.github/instructions/architecture.instructions.md`
   - `.github/instructions/runtime.instructions.md` (if runtime changes)
   - `.github/instructions/providers.instructions.md` (if provider changes)
   - `.github/instructions/execution.instructions.md` (if persistence changes)
   - `.github/instructions/ai.instructions.md` (if AI/tool changes)
   - `.github/instructions/testing.instructions.md` (if test changes)

3. Read `.github/copilot-instructions.md` — Architectural Invariants.

### 2. Review the Diff

For each file changed:

1. **Read the full diff** for that file.
2. **Understand the intent** — What is this change trying to accomplish?
3. **Check against invariants** — Does it violate any of the 10 invariants?
4. **Check layering** — Does it respect the module boundaries?
5. **Check imports** — Are provider SDKs lazily imported? Any circular imports?
6. **Check error handling** — Uses `VoodooError` hierarchy? No silent swallowing?
7. **Check style** — `from __future__ import annotations`? `__all__`? Type hints? Double quotes?

### 3. Run the Architecture Review Checklist

#### 3.1 Architectural Invariants (all 10)

- [ ] **Zero-infra local dev** — No new required dependencies for the default install.
- [ ] **No new required deps** — Provider SDKs in optional extras.
- [ ] **Capability-based adapters** — Protocols + boolean flags. No enums for capabilities.
- [ ] **Contract tests immutable** — No changes to `tests/contracts/` mixin classes.
- [ ] **Compatibility shims** — Old import paths preserved.
- [ ] **Lazy imports** — Provider SDKs at function level.
- [ ] **Correlation IDs** — `trace_id` propagates through the stack.
- [ ] **Events namespaced** — Dotted names (`"agent.started"`).
- [ ] **Sprint discipline** — Changes match the current sprint scope.
- [ ] **Conventional Commits** — `type(scope): description` format.

#### 3.2 Layering

- [ ] UI layer doesn't import from `storage/` or `runtime/` internals.
- [ ] AI layer doesn't import from `ui/` or `routing/`.
- [ ] Runtime layer doesn't import provider SDKs directly.
- [ ] Primitives layer has zero dependencies on other layers.
- [ ] Data layer doesn't import from `ai/` or `mesh/`.

#### 3.3 Module Quality

- [ ] `from __future__ import annotations` at top of every new module.
- [ ] `__all__` present in every new module.
- [ ] Type hints on all public functions/classes.
- [ ] Section dividers used.
- [ ] Docstrings with `Parameters` sections for public API.
- [ ] Double quotes for strings.
- [ ] 4-space indentation.

#### 3.4 Error Handling

- [ ] Uses `VoodooError` hierarchy.
- [ ] Broad excepts use `# noqa: BLE001` and log context.
- [ ] No silent exception swallowing.

#### 3.5 Testing

- [ ] Tests use `MockProvider` for AI — no real API calls.
- [ ] Fresh instances per test — no shared mutable state.
- [ ] Contract tests unchanged if adapter modified.
- [ ] Failure-path tests for durability claims.
- [ ] `os.environ.get(...)` at module level (not `os.environ[...]`).

#### 3.6 Persistence (if applicable)

- [ ] ExecutionStore Protocol extended in all implementations.
- [ ] Migration registered via `register_framework_migration()`.
- [ ] PG-safe FK ordering (parent before journal events).
- [ ] Checkpoint format updated if needed.

### 4. Run the Quality Gate

```bash
just format && just lint && just test
uv run mypy src/voodoo
```

Verify all pass. If any fail, report the failures.

### 5. Identify Issues

Classify each issue:

- **Critical** — Must fix before merge. Violates an invariant, breaks tests, or introduces a security risk.
- **Warning** — Should fix before merge. Code quality, missing tests, or documentation gaps.
- **Info** — Nice to have. Style preferences, minor improvements.

For each issue, provide:
- File and line number.
- Description of the issue.
- Suggested fix.
- Severity (Critical/Warning/Info).

### 6. Check for Regressions

- Are there any existing tests that now fail?
- Are there any public API changes that break backward compatibility?
- Are there any performance regressions?
- Are there any new dependencies that increase install size?

---

## Output Format

Produce a review report:

```markdown
## Architecture Review: [PR/branch name]

### Summary
[1-2 sentence summary of the changes]

### Changes Reviewed
- [file 1]: [brief description]
- [file 2]: [brief description]

### Invariants Check
| # | Invariant | Status | Notes |
|---|---|---|---|
| 1 | Zero-infra local dev | ✅ PASS | ... |
| 2 | No new required deps | ✅ PASS | ... |
| ... | ... | ... | ... |

### Layering Check
- [✅/❌] UI → AI → Realtime → Worker → Runtime → Primitives → Data → Infrastructure

### Quality Gate
- [✅/❌] `just format`
- [✅/❌] `just lint`
- [✅/❌] `just test`
- [✅/❌] `uv run mypy src/voodoo`

### PR & Repo Rules
> See `.github/instructions/pull-request.instructions.md`
- [✅/❌] Branch follows `type/scope` naming
- [✅/❌] Commits follow Conventional Commits
- [✅/❌] PR template filled
- [✅/❌] `CHANGELOG.md` updated
- [✅/❌] No new required dependencies
- [✅/❌] `__all__` updated (if public API changed)
- [✅/❌] Zero-infra local dev works
- [✅/❌] CI will pass (Python 3.12 + 3.13)
- [✅/❌] Ready for squash merge (linear history)

### Documentation Sync
> If code behavior changed but docs didn't, request changes.
- [✅/❌] `CHANGELOG.md` has entries for all behavior changes
- [✅/❌] `docs/*.md` updated for affected source paths (see mapping table)
- [✅/❌] `README.md` updated if user-facing feature added
- [✅/❌] `SPRINT_PLAN.md` updated if sprint scope changed
- [✅/❌] `ROADMAP.md` updated if milestones changed
- [✅/❌] `ARCHITECTURE.md` updated if layer/primitive changed
- [✅/❌] `test_contract_api.py` updated if public API changed
- [✅/❌] Doc code examples are runnable (no stale imports)

### Issues

#### Critical
1. **[file:line]** — [description]
   - Fix: [suggested fix]

#### Warning
1. **[file:line]** — [description]
   - Fix: [suggested fix]

#### Info
1. **[file:line]** — [description]
   - Fix: [suggested fix]

### Regressions
- [none / list]

### Recommendation
[APPROVE / REQUEST CHANGES / BLOCK]

### Reason
[Explanation]
```
