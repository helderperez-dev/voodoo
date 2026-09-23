# AGENTS.md

> **Purpose:** Entry point for AI coding agents (Claude Code, Cursor, Copilot, etc.) working in this repository. Defines the rules, conventions, and structured process that must be followed for every change.

---

## Quick Reference

| What | Value |
|---|---|
| **Language** | Python ≥ 3.12 |
| **Package manager** | `uv` |
| **Task runner** | `just` |
| **Formatter/Linter** | `ruff` (line-length 88, double quotes) |
| **Type checker** | `mypy --strict` (not part of `just lint`) |
| **Test runner** | `pytest` (`asyncio_mode = "auto"`) |
| **Quality gate** | `just format && just lint && just test` |
| **Version** | `src/voodoo/__init__.py` → `__version__` |
| **Release** | `just release X.Y.Z` (triggers GitHub Actions) |

---

## Project Identity

Voodoo is a **programmable runtime for adaptive applications and operational systems** — not merely a web framework. Web applications, APIs, agents, background tasks, realtime systems, MCP integrations, human workflows, distributed systems, and physical systems are different manifestations of one runtime that converge on **Execution**. It is built on Starlette, Uvicorn, Pydantic, Voodoo Store, and standard Python `asyncio`. The runtime is **zero-config by default** with one local `.voodoo/application.vstore`; PostgreSQL, SQLite, Redis, S3 and provider SDKs remain explicit/optional adapters.

**Current version:** See `src/voodoo/__init__.py` → `__version__`.

---

## Runtime Model

- **Voodoo is a programmable runtime, not merely a web framework.** Web is one manifestation of the runtime.
- **AI is one form of Compute** — never a fundamental primitive. Do not make AI mandatory.
- **Agents are entities** capable of holding capabilities and executing intents.
- **Converge on Execution** — workers, tasks, tools, MCP operations, HTTP operations, humans, and physical devices should be represented as Executions whenever semantically appropriate. Do not create duplicate execution models.
- **Prefer existing primitives** over introducing new abstractions.
- **Keep the public API minimal.** Prefer explicit semantics over framework magic.
- **Local-first** — prefer local-first implementations; do not make cloud infrastructure, a specific database, or any vendor (OpenAI, Anthropic, AWS, GCP, Azure, Redis, Postgres) mandatory.
- **Preserve composability, inspectability, and deterministic behavior** where possible.

> **Architectural test:** Before introducing a new abstraction, determine whether the behavior can already be expressed through Entity, State, Intent, Capability, Execution, Effect, Compute, Time, Resource, or Constraint.

---

## Architectural Invariants (Never Violate)

1. **Zero-infra local dev** — The default install must never require external services. Voodoo Store is the default durable substrate for data, jobs, scheduling, events, objects and Runtime state.
2. **No new required dependencies** — Provider SDKs live in optional extras (`[ai]`, `[postgres]`, `[s3]`, `[redis]`). The base install stays minimal.
3. **Capability-based adapters** — Every infrastructure adapter implements a Protocol and declares boolean capability flags. Never use enums for capabilities.
4. **Contract tests are immutable** — The mixin contract suites in `tests/contracts/` must pass unchanged against every adapter implementation.
5. **Canonical 3.x ownership** — Do not reintroduce compatibility-only 2.x paths or duplicate semantic owners. Breaking migrations belong in documentation unless a future compatibility policy explicitly says otherwise.
6. **Lazy imports** — Provider SDKs and circular-dependency-prone modules must be imported at function level, not module level.
7. **Correlation IDs** — Every execution carries a `trace_id` that propagates through the entire stack via `trace_id_var` ContextVar.
8. **Events are namespaced** — All mesh/MCP events use dotted namespaces (e.g., `"agent.started"`, `"tool.completed"`).
9. **Sprint discipline** — Implement a numbered sprint only when `SPRINT_PLAN.md` explicitly declares it active. When the tracker is at a selection gate, do not invent Sprint 29 or add unrelated features; perform the product/architecture selection first.
10. **Conventional Commits** — All commits must use `type(scope): description` format.

---

## Code Style

### Must Follow

- **`from __future__ import annotations`** at the top of every Python module.
- **Type hints everywhere** — Use `str | None`, `list[Any]`, `dict[str, Any]` syntax.
- **`__all__`** — Explicit export list in every module.
- **Section dividers** — Use `# ---------------------------------------------------------------------------` to separate logical sections.
- **Docstrings** — Module-level docstring explaining purpose. Class/function docstrings with `Parameters` sections for public API.
- **Double quotes** for strings.
- **4-space indentation**.
- **Comments explain "why" not "what"** — Reference spec sections when relevant.

### Error Handling

- Use the structured error hierarchy in `voodoo.core.errors` (`VoodooError` base → specific subclasses).
- Broad excepts must use `# noqa: BLE001` and log context.
- Never swallow exceptions silently.

### Compatibility Patterns

- **`sys.modules` replacement** — For module aliases (see `voodoo/queue.py`, `voodoo/tools/registry.py`).
- **PEP 562 `__getattr__`** — For forwarded globals and deprecation shims (see `voodoo/__init__.py`).
- **Function-level imports** — For provider SDKs and circular dependency avoidance.

---

## Testing Standards

- **`pytest-asyncio`** with `asyncio_mode = "auto"` — async tests don't need `@pytest.mark.asyncio`.
- **Test classes** group related tests.
- **Fresh instances per test** — Never share mutable state. Use fixtures for isolation.
- **Autouse fixtures** in `tests/conftest.py` handle cleanup.
- **Contract tests** in `tests/contracts/` — mixin classes run unchanged against every adapter.
- **MockProvider** is deterministic and requires no network. Use it for all agent/AI tests.
- **Env var access** in test modules must use `os.environ.get(...)` not `os.environ[...]`.

---

## Development Process

### Standard Workflow

> **Before creating a PR, read `.github/instructions/pull-request.instructions.md`** — it documents branch protection rules, PR template requirements, CI checks, merge strategy, documentation sync rules, and emergency bypass procedures.

1. Identify the sprint or task.
2. Create a feature branch: `git checkout -b feat/<scope>`.
3. Implement changes following architectural rules.
4. Run quality gate: `just format && just lint && just test`.
5. Update documentation (MANDATORY):
   - `CHANGELOG.md` under `[Unreleased]`.
   - `docs/*.md` for changed behavior (see source-path-to-doc mapping).
   - `README.md` if user-facing.
   - `SPRINT_PLAN.md` if sprint scope changed.
   - `ROADMAP.md` if milestones changed.
   - `ARCHITECTURE.md` if layer/primitive changed.
   - `test_contract_api.py` if public API changed.
6. Commit with Conventional Commits.
7. Push and create a PR (fill the PR template — `.github/PULL_REQUEST_TEMPLATE.md`).
8. Wait for CI to pass (Python 3.12 + 3.13, lint, test).
9. Get Code Owner review (1 approval required, enforced for admins).
10. Resolve all review comments (conversation resolution required).
11. Merge with squash: `gh pr merge --squash --delete-branch`.
12. Release: `just release X.Y.Z` (if sprint complete).

**Documentation sync is mandatory.** A PR with code changes but no doc updates is incomplete and will be blocked in review. See `.github/instructions/pull-request.instructions.md` → "Documentation Sync" for the full mapping table.

**Branch protection on `main`:** `enforce_admins=true`, 1 review required, Code Owner reviews on, required status check "CI", `required_linear_history=true`, `required_conversation_resolution=true`. See `.github/instructions/pull-request.instructions.md` for full details.

### Conventional Commits

```
feat(scope): add new feature
fix(scope): fix a bug
docs(scope): documentation only
refactor(scope): code restructuring, no behavior change
test(scope): add or fix tests
chore(deps): dependency updates
```

Common scopes: `core`, `runtime`, `ai`, `ui`, `data`, `mesh`, `mcp`, `workers`, `auth`, `security`, `telemetry`, `cli`, `config`, `ci`, `docs`.

---

## Instruction Files

For domain-specific guidance, read the relevant instruction file before making changes:

| Domain | File |
|---|---|
| Architecture & layering | `.github/instructions/architecture.instructions.md` |
| Runtime engine & execution | `.github/instructions/runtime.instructions.md` |
| Provider/adapter system | `.github/instructions/providers.instructions.md` |
| Durable persistence | `.github/instructions/execution.instructions.md` |
| AI agents & tools | `.github/instructions/ai.instructions.md` |
| Testing & contracts | `.github/instructions/testing.instructions.md` |
| **PR & repo rules** | **`.github/instructions/pull-request.instructions.md`** |

---

## Skills

Structured workflows for common tasks:

| Skill | File | When to use |
|---|---|---|
| `architecture-review` | `.github/skills/architecture-review/SKILL.md` | Before merging major changes |
| `implement-sprint` | `.github/skills/implement-sprint/SKILL.md` | When starting a new sprint |
| `add-provider` | `.github/skills/add-provider/SKILL.md` | When adding a database/queue/cache/etc. adapter |
| `runtime-feature` | `.github/skills/runtime-feature/SKILL.md` | When adding runtime engine features |
| `testing` | `.github/skills/testing/SKILL.md` | When writing or fixing tests |
| `documentation` | `.github/skills/documentation/SKILL.md` | When updating docs |
| `release` | `.github/skills/release/SKILL.md` | When cutting a release |

---

## Prompts

Structured prompts for common tasks:

| Prompt | File | When to use |
|---|---|---|
| `audit-repository` | `.github/prompts/audit-repository.prompt.md` | Comprehensive repository audit |
| `plan-sprint` | `.github/prompts/plan-sprint.prompt.md` | Plan the next sprint |
| `architecture-review` | `.github/prompts/architecture-review.prompt.md` | Review a PR or branch |

---

## File Organization

```
src/voodoo/
├── __init__.py          # Small 3.x application happy path + __version__
├── core/                # App facade, lifecycle, events, state, errors
├── primitives/          # Foundational runtime concepts
├── runtime/             # Canonical execution and operational semantics
│   ├── execution/       # Execution engine and world-aware execution
│   ├── scheduling/      # tasks, queue orchestration, scheduler, dispatch
│   ├── agency/          # goals and adaptive supervision
│   ├── distributed/     # remote execution, membership, fabric
│   ├── reconciliation/  # desired/observed convergence
│   └── inspection/      # runtime lineage and inspection
├── world/               # entities, relationships, observations, WorldModel
├── edge/                # physical/external participant boundary
├── protocol/            # language-neutral semantic contracts
├── ai/                  # native Agent/provider/tool semantics
├── integrations/        # vendor-backed AI, MCP and OpenTelemetry integration
├── observability/       # framework-owned traces, metrics and telemetry state
├── adapters/            # provider registry and infrastructure adapters
├── storage/             # database, queue, events, objects, cache contracts
├── data/                # Store-first Model facade + SQL compatibility
├── ui/                  # components, reactive state, design system
├── routing/             # page and API routing
├── mesh/                # realtime/event transport application surface
├── auth/                # credential/session compatibility APIs
├── security/            # HTTP security and redaction
├── cli/                 # Typer CLI
├── config.py            # config loading and env interpolation
├── schedule.py          # public scheduler compatibility/application surface
├── i18n.py              # internationalization
├── seo.py               # SEO/OpenGraph metadata
└── status.py            # health endpoint
```

Removed 2.x namespaces such as `voodoo.workers`, `voodoo.queue`,
`voodoo.telemetry`, `voodoo.mcp`, `voodoo.tools`, `voodoo.agent`,
`voodoo.api` and `voodoo.theme` must not be recreated. See
`docs/public-api-3.md`.

---

## Critical Gotchas

1. **PostgreSQL FK ordering** — `execution_events.execution_id → executions.id` is enforced. Always upsert the parent row BEFORE appending journal events.
2. **PostgreSQL dict rows** — psycopg returns dict-like rows, so use `row["col"]` not `row[0]`.
3. **Test env vars** — `os.environ["VAR"]` at module level runs BEFORE skip markers. Always use `os.environ.get(...)`.
4. **`_protocol_check`** — Place Protocol compliance checks at file BOTTOM under `if TYPE_CHECKING:`.
5. **Queue handler registry** — Handlers register at import time. Queue/task orchestration is owned by `voodoo.runtime.scheduling`; test resets must clear runtime state without recreating removed `voodoo.workers` ownership.
6. **mypy is NOT in `just lint`** — Ruff is the lint gate. Run `uv run mypy src/voodoo` separately for type checking.
7. **WAL mode** — `SQLiteExecutionStore` uses WAL mode with `busy_timeout=5000` for concurrent access.
8. **`voodoo.toml`/`voodoo.yaml`** — Config precedence: explicit file > `VOODOO_*` env vars > local defaults.
