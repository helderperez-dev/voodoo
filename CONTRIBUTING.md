# Contributing to Voodoo

First off — thank you for taking the time to contribute. Voodoo is an
open-source project and every contribution, from a typo fix to a new
adapter, is valued.

This document describes how to set up a development environment, the
quality gates every change must pass, and the conventions the project
follows.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Quality Gates](#quality-gates)
- [Architecture & Conventions](#architecture--conventions)
- [Testing](#testing)
- [Adding a New Adapter](#adding-a-new-adapter)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

---

## Code of Conduct

Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to abide by its terms.

---

## Getting Started

### Prerequisites

- **Python ≥ 3.12**
- [**uv**](https://docs.astral.sh/uv/) (recommended) or `pip` + `venv`
- **just** (command runner — `brew install just` on macOS)
- **Git**

### Clone & install

```bash
git clone https://github.com/helderperez-dev/voodoo.git
cd voodoo
uv sync --all-extras --dev
```

### Verify the install

```bash
just test
```

All tests should pass (some contract tests require external services and
will skip — see [Testing](#testing)).

---

## Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes.** Keep commits focused and write clear commit
   messages following [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat(redis): add RedisQueue adapter
   fix(queue): correct lease expiry calculation
   docs(readme): update installation instructions
   refactor(storage): extract object store interface
   test(contracts): add cache contract suite
   chore(deps): bump ruff to 0.6.0
   ```

3. **Run quality gates** before pushing (see below).

4. **Open a Pull Request** against `main`. Fill in the PR template and
   link any related issues.

---

## Quality Gates

Every PR must pass all three gates before merging:

```bash
just format   # ruff format + isort
just lint     # ruff check
just test     # pytest (full suite)
```

Or run them all at once:

```bash
just format && just lint && just test
```

### Pre-commit hooks

The repo includes a `.pre-commit-config.yaml`. Install hooks once:

```bash
pre-commit install
```

This runs `ruff format` and `ruff check` on every commit automatically.

### Type checking

```bash
just typecheck   # mypy
```

Mypy is not currently part of the hard gate (ruff is), but new code
should be type-clean. Files with pre-existing mypy issues are tracked
incrementally.

---

## Architecture & Conventions

### Design principles

Voodoo follows a set of architectural invariants (see
[ROADMAP.md §70](ROADMAP.md)). The most important ones for contributors:

1. **Local-first, zero-infra by default.** The default install must work
   with no external services. SQLite, local filesystem, in-process events.
2. **Adapters over lock-in.** Every infrastructure concern (database,
   queue, events, objects, cache) is behind a protocol with capability
   declarations. New backends are adapters, not core changes.
3. **Composition over configuration.** Python over DSLs. No YAML
   required to start.
4. **No new required dependencies.** Provider SDKs live in optional
   extras (`[ai]`, `[postgres]`, `[redis]`, `[s3]`).
5. **Every durability claim needs a failure-path test.** Worker crash,
   restart, lease expiry, duplicate delivery.

### Code style

- **Line length:** 88 characters (enforced by ruff).
- **Imports:** Sorted by isort (via ruff).
- **Quotes:** Double quotes (enforced by ruff format).
- **Async-first:** All I/O handlers, database work, and network calls
  should be `async def`.
- **Type hints:** Required on all public functions. Use `from __future__
  import annotations` is not needed (Python 3.12+).

### Project structure

```
src/voodoo/
├── adapters/       # Style adapters (Tailwind, CSS)
├── ai/             # Agent runtime, providers, tools
├── auth/           # JWT, API keys, RBAC, session management
├── cli/            # `voodoo` CLI commands
├── core/           # App, runtime engine, execution context
├── data/           # ORM, models, database init
├── mcp/            # Model Context Protocol server
├── mesh/           # Realtime event bus + WebSocket bridge
├── primitives/     # State, Capability, Intent, Effect, Time, Compute, Resource, Constraint
├── routing/        # File-based routing, API routes
├── runtime/        # ExecutionEngine, planner, supervisor
├── security/       # CORS, CSRF, rate limiting, security headers
├── static/         # Client-side JS, CSS, HTML templates
├── storage/        # Database, queue, events, objects, cache, execution stores
├── telemetry/      # Correlation IDs, tracing, token/cost accounting
├── tools/          # @tool decorator, tool registry
├── ui/             # Component system, state, styles, theme
└── workers/        # @task decorator, durable task queue
```

---

## Testing

### Test layout

```
tests/
├── test_*.py              # Unit & integration tests
└── contracts/             # Adapter portability suite
    ├── test_database.py           # DatabaseContractTests mixin
    ├── test_database_postgres.py  # PG contract (gated on VOODOO_TEST_DATABASE_URL)
    ├── test_queue.py              # QueueContractTests mixin
    ├── test_queue_redis.py        # Redis contract (gated on VOODOO_TEST_REDIS_URL)
    ├── test_cache.py              # CacheContractTests mixin
    ├── test_cache_redis.py        # Redis cache contract
    ├── test_objectstore.py        # ObjectStoreContractTests mixin
    ├── test_eventbus.py           # EventBusContractTests mixin
    └── test_capabilities.py       # Capability negotiation tests
```

### Running tests

```bash
# Full suite (contract tests for external services will skip)
just test

# Specific test file
uv run pytest tests/test_app.py -v

# With coverage
uv run pytest --cov=voodoo --cov-report=html

# Contract tests against live services (requires Docker)
docker run --name voodoo-pg -e POSTGRES_DB=voodoo_test \
  -e POSTGRES_USER=voodoo -e POSTGRES_PASSWORD=voodoo -p 5432:5432 -d postgres:16
docker run --name voodoo-redis -p 6379:6379 -d redis:7
docker run --name voodoo-minio -p 9000:9000 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  -d minio/minio server /data --console-address ":9001"

# Set env vars (see .env.example for details)
export VOODOO_TEST_DATABASE_URL=postgresql://voodoo:voodoo@localhost:5432/voodoo_test
export VOODOO_TEST_REDIS_URL=redis://localhost:6379/0
export VOODOO_TEST_S3_ENDPOINT=http://localhost:9000
export VOODOO_TEST_S3_BUCKET=voodoo-test
export VOODOO_TEST_S3_KEY=minioadmin
export VOODOO_TEST_S3_SECRET=minioadmin

uv run pytest tests/contracts/ -v
```

### Writing tests

- **Unit tests** go in `tests/test_*.py`.
- **Contract tests** for new adapters go in `tests/contracts/` and must
  use the appropriate contract mixin (e.g., `QueueContractTests`).
- **Failure-path tests** are required for any durability claim. Test
  crash → restart → recovery scenarios.
- Use `pytest-asyncio` (auto mode is enabled). All async tests are
  automatically detected.
- Use `tmp_path` for filesystem isolation. Never write to the repo root.

---

## Adding a New Adapter

Voodoo's adapter system lets you add new infrastructure backends without
touching core code. Every adapter implements a protocol and declares its
capabilities.

1. **Implement the protocol** (e.g., `VoodooQueue`, `VoodooDatabase`,
   `VoodooEventBus`, `VoodooObjectStore`, `VoodooCache`).

2. **Declare capabilities** via `.capabilities()` — be honest about what
   your adapter guarantees. The runtime uses this for negotiation.

3. **Write contract tests** — run the appropriate contract mixin against
   your adapter. If your adapter can't satisfy a contract assertion,
   document why and mark the capability as unsupported.

4. **Register the adapter** in `src/voodoo/adapters/registry.py`.

5. **Add an optional extra** in `pyproject.toml` if your adapter needs
   a third-party package.

6. **Wire CI** — add a service container in `.github/workflows/ci.yml`
   if your adapter needs an external service for contract tests.

See `src/voodoo/storage/queue/redis.py` and
`tests/contracts/test_queue_redis.py` as a reference implementation.

---

## Submitting Changes

### Pull Request checklist

- [ ] `just format && just lint && just test` is green
- [ ] Commit messages follow Conventional Commits
- [ ] New features have tests (including failure-path tests for
      durability claims)
- [ ] New adapters have contract tests
- [ ] No new required runtime dependencies (use optional extras)
- [ ] `__all__` updated if public exports changed
- [ ] `CHANGELOG.md` updated (under "Unreleased" or the next version
      header)
- [ ] Documentation updated if behavior changed

### Review process

1. A maintainer will review your PR within a few days.
2. Address feedback by pushing new commits (don't force-push during
   review unless asked).
3. Once approved and CI is green, a maintainer will squash-merge your PR.

---

## Release Process

Releases are fully automated via GitHub Actions:

1. Maintainer updates `CHANGELOG.md` and `SPRINT_PLAN.md`.
2. Commit and push to `main`.
3. Trigger the release:
   ```bash
   just release X.Y.Z
   ```
4. The `release.yml` workflow automatically:
   - Validates semver and runs the full test suite
   - Bumps version in `src/voodoo/__init__.py`
   - Commits, tags (`vX.Y.Z`), and pushes
   - Builds distributions (`uv build`)
   - Publishes to PyPI
   - Updates the Homebrew formula
   - Creates a GitHub Release with assets and release notes
5. Monitor with:
   ```bash
   gh run watch --workflow=release.yml
   ```

Versioning follows [Semantic Versioning](https://semver.org/). Minor bump
per feature sprint, patch for fixes, major only at breaking-change
milestones.

---

## Questions?

- **Bug reports:** [Open an issue](https://github.com/helderperez-dev/voodoo/issues/new?template=bug_report.md)
- **Feature requests:** [Open an issue](https://github.com/helderperez-dev/voodoo/issues/new?template=feature_request.md)
- **Security reports:** See [SECURITY.md](SECURITY.md)
- **Discussions:** [GitHub Discussions](https://github.com/helderperez-dev/voodoo/discussions)

Thank you for contributing to Voodoo. 🪄
