# Sprint 30 — Production Readiness

**Status:** IN PROGRESS
**Started:** 2026-10-06

> **Live checkpoint (2026-10-10):** The cross-repository production plan is
> **112 complete / 36 open**. The repository-level checklist below is the
> original Sprint 30 scope; implementation evidence is maintained in the root
> `VOODOO_PRODUCTION_READINESS_PLAN.md` and `VOODOO_STATUS.md`. Local gates are
> green (Framework **2,388 passed, 133 skipped, 2 warnings**; Store Python
> **82 passed**; Site **421 passed**; release contract passing). Remaining
> unchecked work is limited to
> catalog-wide breadth, hosted certification, external review, historical
> compatibility evidence, and final artifact/signature verification.

The local dependency gate now audits pinned `uv.lock` exports directly,
excluding only the unpublished editable application package and removing the
previous `pip-audit` skip from Framework, Store, and Site evidence. Site CI now
uses the same export for its hosted audit and dependency SBOM.

## Goal

Certify the existing Voodoo architecture for a precise first production
profile instead of expanding the framework surface.

Production Profile 1 supports:

- one application-owned Runtime process;
- one live local Voodoo Store writer;
- multiple isolated authenticated browser sessions;
- durable local data, work, events, objects and Runtime state;
- tested backup, destructive restore, upgrade and rollback procedures.

It does not claim Store replication, shared-file multi-writer operation,
distributed consensus, global transactions or global exactly-once execution.

## Architecture laws

1. Runtime owns application semantics, identity projection, authorization,
   session ownership and effect interpretation.
2. Store owns durable mechanics, local transactions, recovery and lifecycle.
3. UI session state is bounded and isolated; application-global state is an
   explicit opt-in semantic.
4. Production configuration fails closed.
5. Documentation, templates and skills execute against the public API they
   teach.
6. Release claims are backed by mandatory automated evidence.

## Workstreams

### 30.1 Production security

- [x] Production-aware CSRF, CORS, cookie and HSTS defaults.
- [x] Startup rejection for development signing secrets and unsafe browser
  security combinations.
- [x] Application configuration injection into authentication and security
  middleware.
- [x] CSRF bypass only after validated non-cookie authentication.
- [x] Rate-limit buckets based on validated principal or client address, with
  bounded in-memory client state.
- [x] Encrypted local secrets fail closed, use atomic replacement and receive
  owner-only permissions.
- [x] Strict WebSocket origin, authentication, size, concurrency, backpressure
  and idle-timeout policy.
- [x] CSP hash policy and explicit unsafe HTML/style escape hatches. Production
  script sources reject unsafe inline/eval, the remaining Site shell script is
  covered by an exact SHA-256 hash, production style sources default to
  `'self'`, and `Html`/`css={}` are explicit reviewed escape hatches.
- [x] JWT algorithm/issuer/audience/key-rotation contract. HS256/JWT headers,
  optional issuer/audience claims, bounded clock skew, and explicit previous-key
  rotation are implemented and tested. `revoke_access_token()` now provides
  bounded process-local invalidation by JTI/hash until expiry; distributed
  revocation remains outside the Profile 1 boundary.
- [x] Dependency, license, secret and supply-chain gates.

### 30.2 UI session correctness

- [x] Runtime-owned `UISession` identity and lifecycle.
- [x] Per-session binding/callable registry and render tree.
- [x] Targeted patch delivery instead of implicit global broadcast.
- [x] Component, page/session, application and durable state scopes.
- [x] Disconnect/navigation teardown for bindings, state and tasks.
- [x] Two-user isolation, replay, cross-session and leak regression tests.

### 30.3 Public API and scaffold convergence

- [x] Generated public API manifest and executable documentation imports.
- [x] `voodoo new` as the one scaffold engine.
- [x] `voodoo create` temporary warning alias to that same engine.
- [x] Canonical versioned template vendored for offline creation.
- [x] Cross-repository template parity and generated-application smoke tests.
- [x] Current command, import, version and Design System truth in every current guide (historical changelogs/reviews retain their original release context).

### 30.4 Store and Runtime durability

- [x] Durable-domain ownership inventory and removal of duplicate encodings.
- [x] Store fuzz, crash, power-loss and retained recovery corpus.
- [x] Automated backup/destroy/restore drill.
- [x] Versioned Runtime record codecs and migration fixtures.
- [x] Store operational metrics, resource limits and performance budgets.
- [x] Explicit at-rest security policy.

### 30.5 Stable component system

- [x] Component taxonomy and stable/beta/experimental/deprecated manifest.
- [x] Preferred APIs and migrations for overlapping component families.
- [x] Stable render identity and session-aware event lifecycle.
- [x] Semantic tokens and complete interaction-state contract (199 token declarations, 51 references, and the 102-control state contract pass).
- [x] Automated accessibility plus keyboard acceptance (local contract and browser matrix pass; hosted axe/screen-reader certification remains).
- [x] Chromium, Firefox and WebKit behavior gates (CI matrix; hosted runs still required for certification).
- [x] Deterministic responsive/light/dark/RTL/reduced-motion visual baselines (committed signatures/PNG baselines pass locally; hosted raw-image review remains).

### 30.6 Documentation, site, templates and skills

- [x] Executable progressive quickstart (canonical scaffold compile/install smoke passes).
- [x] Site snippets imported from or checked against source.
- [x] Site browser, accessibility, link and deployment-preview gates (local 421-test suite and browser matrix pass; hosted deployment certification remains).
- [x] Skill compatibility manifests, validation and source synchronization.
- [x] Installer dry-run, checksum, backup and rollback.
- [x] Canonical default template with production guidance and CI.

### 30.7 Release and operations

- [x] Full-package mypy ratchet to zero. `uv run mypy src/voodoo --no-incremental --show-error-codes` passes with zero errors.
- [x] Risk-weighted coverage gates (focused risk-path contract passes for auth/security, events, state, Store adapters, scheduling and providers).
- [x] Build once, test the exact wheel and source distribution artifacts, then publish (workflow contract enforced; hosted execution remains).
- [ ] Trusted publishing, checksums, SBOM and artifact attestations.
- [ ] Supported OS/Python/browser compatibility matrix.
- [ ] Upgrade, rollback and disaster-recovery runbooks and drills.
- [ ] External security review before a general-availability claim.

## First acceptance slice

The first vertical slice is complete when an unsafe production configuration
cannot start and the same resolved configuration controls both startup and
request middleware.

Evidence required:

- production defaults are safe;
- development secret, debug, insecure cookie, disabled HSTS/CSRF and wildcard
  credentialed CORS each fail independently;
- invalid API-key/Bearer headers do not bypass CSRF;
- rotating invalid credential strings does not evade the rate limit;
- local encrypted secrets never silently read or write plaintext;
- Ruff, targeted mypy and targeted tests pass.

## Completion gate

Sprint 30 remains in progress until every mandatory workstream item is complete,
the full repository and compatibility matrices pass, published artifacts have
provenance, and the Production Profile 1 operational drill succeeds using only
those artifacts.
