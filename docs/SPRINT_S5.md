# Sprint 5 — Auth Hardening & CLI

> Implementation tracking for S5. Derived from IMPLEMENTATION_PLAN.md §3.2, §3.5.
> **Status**: Planned

---

## Goal

Harden auth and security against the threat model (§10), reduce auth public
surface, and deliver `voodoo new` scaffolding + file-based pages + CLI trim.

---

## Workstreams

### S5-1: Auth & security hardening (no new features)
- [ ] Audit pass over §10 threat model: cookie flags, JWT expiry/validation,
      CSRF, CORS, rate limiting, secret handling, error leakage, password
      hashing parameters
- [ ] Reduce auth public surface to subpackage; document kept essentials
- [ ] Route guards (`login_required`, role/permission decorators) verified
      against new `page`/`api` routing
- [ ] **Files**: `voodoo/auth.py` (refactor), `voodoo/security.py` (audit)

### S5-2: CLI & scaffolding (G15)
- [ ] `voodoo new my_app` → clean minimal project (`app.py`, `pages/`,
      `components/`, `models.py`, `agents/`, `workers/`, `styles.css`,
      `tests/`, `pyproject.toml`) — nothing extra
- [ ] File-based pages: `pages/index.py`, `pages/about.py`,
      `pages/users/[id].py` → `/`, `/about`, `/users/{id}`
- [ ] `voodoo dev` (banner per spec), `voodoo routes`, `voodoo doctor`
      (runtime/db/auth/mesh/mcp/provider/workers/telemetry checks + warnings),
      `voodoo version`
- [ ] Trim CLI to core set; move extras behind existing commands
- [ ] **File**: `voodoo/cli.py` (refactor)

### S5-3: Tests
- [ ] Security test suite per §10 threat model
- [ ] CLI tests: `voodoo new`, `voodoo dev`, `voodoo routes`, `voodoo doctor`
- [ ] File-based page loading tests
- [ ] Full suite green; ruff clean; commit

---

## File Changes

| File | Action | Description |
|---|---|---|
| `voodoo/auth.py` | MODIFY | Harden, reduce exports, audit |
| `voodoo/security.py` | MODIFY | Audit pass, verify defaults |
| `voodoo/cli.py` | MODIFY | `voodoo new`, file pages, doctor, routes |
| `voodoo/core/app.py` | MODIFY | File-based page loader (if needed) |
| `tests/test_security.py` | MODIFY | Threat model coverage |
| `tests/test_cli.py` | MODIFY | New CLI command tests |

---

## Exit Criteria

- [ ] `voodoo new demo && cd demo && voodoo dev` yields working app
- [ ] File-based pages work: `pages/index.py` → `/`
- [ ] Security test suite green (cookie flags, JWT, CSRF, CORS, rate limit)
- [ ] `voodoo doctor` runs health checks
- [ ] Full suite green; ruff clean; committed (no version bump)
