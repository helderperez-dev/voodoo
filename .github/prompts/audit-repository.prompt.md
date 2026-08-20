# Audit Repository

> **Purpose:** Perform a comprehensive audit of the Voodoo repository to identify architectural violations, missing tests, documentation gaps, and process issues.

---

## Instructions

You are auditing the Voodoo framework repository. Perform a thorough review and produce a structured report.

### 1. Architectural Invariants Audit

Review each of the 10 Architectural Invariants (see `.github/copilot-instructions.md`):

1. **Zero-infra local dev** — Does the default install require any external services?
2. **No new required dependencies** — Are there provider SDKs in the base install?
3. **Capability-based adapters** — Do all adapters use Protocols + boolean flags? Any enums for capabilities?
4. **Contract tests immutable** — Have any mixin classes in `tests/contracts/` been modified?
5. **Compatibility shims** — Are old import paths preserved? Check `sys.modules` replacements and PEP 562 `__getattr__`.
6. **Lazy imports** — Are provider SDKs (`openai`, `anthropic`, `psycopg`, `redis`, `boto3`) imported at function level?
7. **Correlation IDs** — Does `trace_id` propagate through HTTP → agent → tool → queue → mesh?
8. **Events namespaced** — Do all events use dotted namespaces? Search for bare event names.
9. **Sprint discipline** — Is the current sprint in `SPRINT_PLAN.md` being followed?
10. **Conventional Commits** — Do recent commits follow `type(scope): description`?

For each invariant, report: PASS/FAIL + evidence.

### 2. Code Quality Audit

- **`from __future__ import annotations`** — Is it at the top of every Python module?
- **Type hints** — Are all public functions/classes type-hinted?
- **`__all__`** — Is it present in every module?
- **Section dividers** — Are `# ---...` dividers used?
- **Docstrings** — Do public APIs have docstrings with `Parameters` sections?
- **Double quotes** — Are strings using double quotes?
- **Error handling** — Are `VoodooError` subclasses used? Any silent exception swallowing?

### 3. Test Coverage Audit

- Run: `uv run pytest --cov=voodoo --cov-report=term-missing`
- Identify modules with < 80% coverage.
- Check for missing failure-path tests (durability claims without crash/recover tests).
- Verify contract tests exist for all adapters.
- Verify `MockProvider` is used for all AI tests (no real API calls).

### 4. Documentation Audit

- Are all `docs/*.md` files up to date with the current codebase?
- Does `README.md` have accurate quick start?
- Is `CHANGELOG.md` maintained under `[Unreleased]`?
- Is `SPRINT_PLAN.md` accurate?
- Is `ROADMAP.md` aligned with `SPRINT_PLAN.md`?
- Are instruction files (`.github/instructions/`) accurate?

### 5. Dependency Audit

- Run: `uv pip list` and review all dependencies.
- Are all provider SDKs in optional extras (`[ai]`, `[postgres]`, `[s3]`, `[redis]`)?
- Are there any unused dependencies?
- Are versions pinned appropriately?

### 6. CI/CD Audit

- Review `.github/workflows/`.
- Does CI run `just format && just lint && just test`?
- Does CI test on Python 3.12 and 3.13?
- Are service containers (PostgreSQL, MinIO, Redis) configured?
- Does the release workflow trigger on tags?
- Is branch protection configured on `main`? (See `.github/instructions/pull-request.instructions.md` for expected config: enforce_admins=true, 1 review required, Code Owner reviews, required status check "CI", required_linear_history=true, required_conversation_resolution=true.)
- Is the PR template (`.github/PULL_REQUEST_TEMPLATE.md`) being used?
- Is `.github/CODEOWNERS` up to date with the source tree?

### 7. Security Audit

- Are there any hardcoded secrets or API keys?
- Is `.env` in `.gitignore`?
- Are auth tokens properly hashed/encrypted?
- Is CORS configured securely?
- Is CSRF protection enabled?
- Are security headers set?

---

## Output Format

Produce a report with the following structure:

```markdown
# Repository Audit Report

**Date:** [date]
**Auditor:** AI Agent
**Repository:** voodoo

## Summary

- **Overall Health:** [EXCELLENT/GOOD/NEEDS IMPROVEMENT/CRITICAL]
- **Invariants Passed:** X/10
- **Test Coverage:** X%
- **Critical Issues:** N
- **Warnings:** N
- **Info:** N

## 1. Architectural Invariants

| # | Invariant | Status | Evidence |
|---|---|---|---|
| 1 | Zero-infra local dev | PASS | ... |
| 2 | No new required deps | PASS | ... |
| ... | ... | ... | ... |

## 2. Code Quality

[Findings]

## 3. Test Coverage

[Findings with coverage numbers]

## 4. Documentation

[Findings]

## 5. Dependencies

[Findings]

## 6. CI/CD

[Findings]

## 7. Security

[Findings]

## Issues

### Critical
1. [issue]

### Warnings
1. [issue]

### Info
1. [issue]

## Recommendations

1. [recommendation]
2. [recommendation]

## Next Steps

1. [action item]
2. [action item]
```
