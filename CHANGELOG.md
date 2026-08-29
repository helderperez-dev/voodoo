# Changelog

## [Unreleased]

## 2.1.0 — 2026-08-29

### Added — Sprint 18: Durable human-in-the-loop

- **`Approval.participant`** — durable handle naming the compute to re-run
  after a decision. Persisted in the `approvals` table (migration v9,
  `participant` column) on both SQLite and PostgreSQL stores.
- **`ExecutionEngine.register_participant(name, compute)`** /
  **`.resolve_participant(name)`** — registry of named compute participants.
  After a restart, `approve()` re-resolves the compute by name and resumes
  the waiting execution on any worker.
- **Durable resume on approve** — `engine.approve()` re-resolves the compute
  from the participant registry when the live callable is gone and falls
  back to the waiting execution's persisted intent, so the resumed run
  executes the original work instead of a bare acknowledgement.
- **Journal events** — `approval.requested` (on wait), `approval.granted`,
  `approval.denied` (on decide), recorded to the execution journal on both
  SQLite and PostgreSQL stores.
- **`store.load_approvals(pending_only=False)`** — list approvals (newest
  first) on SQLite + PostgreSQL execution stores.
- **CLI `voodoo approvals`** — `list [--pending]`, `show <id>`,
  `approve <id> [--by] [--note]`, `deny <id> [--by] [--reason]`, operating
  directly on the durable store with optional `--app` to import the
  application so participants re-register.
- **`tests/test_durable_hitl.py`** — 12 tests including the sprint
  acceptance criterion (crash → decide → resume completes) and journal-event
  coverage.

## 2.0.0 — 2026-08-29

### Added — Sprint 17: Agents as durable entities (v2.0.0)

- **`AgentEntity`** — durable agent identity (id, name, description, model,
  system_prompt, capabilities, tools, permissions, config, state, metadata,
  timestamps) in `voodoo.agents.models`. Serializes to/from dict.
- **`AgentRunRecord`** — run history record (run_id, agent_id, execution_id,
  prompt, output, status, tokens, cost, tool_calls, trace_id) in
  `voodoo.agents.models`.
- **`AgentRegistry` Protocol** — persistence contract for agent registries
  (`register`, `get`, `list_agents`, `update`, `delete`, `record_run`,
  `get_runs`, `count_agents`, `count_runs`) in `voodoo.agents.registry`.
- **`InMemoryAgentRegistry`** — in-memory registry for tests.
- **`SQLiteAgentRegistry`** — durable SQLite registry with WAL mode and
  `busy_timeout=5000`. Agents and runs tables with CASCADE delete. JSON
  serialization for list/dict fields.
- **Agent auto-registration** — agents with `agent_id` + `agent_registry`
  are automatically registered on first `run()` or `stream()`.
- **Agent run history** — every `Agent.run()` and `Agent.stream()` persists
  an `AgentRunRecord` to the registry (prompt, output, status, tokens, cost,
  tool calls, trace ID).
- **CLI `voodoo agents list`** — list registered agents with `--state`,
  `--limit`, `--json` flags.
- **CLI `voodoo agents show <id>`** — inspect agent details + recent run
  history with `--limit`, `--json` flags.
- **Public API exports**: `AgentEntity`, `AgentRegistry`, `AgentRunRecord`,
  `SQLiteAgentRegistry` from `voodoo`.
- **`tests/test_agent_registry.py`** — 27 tests covering entity models,
  in-memory registry, SQLite registry, persistence across reopen, agent
  integration, and multi-agent collaboration.

## 1.20.0 — 2026-08-29

### Added — Sprint 16: Memory as entity state

- **`MemoryStore` Protocol** — the persistence contract for memory backends
  (`write`, `read`, `search`, `list_entries`, `delete`, `count`) in
  `voodoo.memory.interfaces`.
- **`MemoryEntry`** — a single piece of knowledge (entity id, layer, content,
  metadata, tags, importance, source execution id, TTL).
- **`MemoryLayer`** — semantic origin tags: `WORKING`, `EPISODIC`, `DURABLE`,
  `SEMANTIC`.
- **`SQLiteMemoryStore`** — default durable backend with FTS5 full-text search.
  Falls back to LIKE when FTS5 is unavailable. WAL mode, `busy_timeout=5000`.
  No new dependencies.
- **`InMemoryMemoryStore`** — non-durable store for tests.
- **Agent.memory** — lazily created memory store on every `Agent` instance.
  Context ≠ memory: context is an opaque dict for tool calls; memory is a
  queryable, durable record of what the entity knows.
- **Episodic memory auto-write** — every `Agent.run()` and `Agent.stream()`
  writes an episodic memory entry (Layer 1) capturing prompt, output, tool
  calls, and token accounting.
- **Public API exports**: `MemoryEntry`, `MemoryLayer`, `MemoryStore`,
  `SQLiteMemoryStore` from `voodoo`.
- **`tests/test_memory.py`** — 36 tests covering CRUD, search (FTS5 + LIKE),
  persistence across restart, agent integration, and episodic auto-write.
- **`tests/test_contract_api.py`** — updated to pin the new memory exports.

## 1.19.1 — 2026-08-28

### Fixed

- **Chat app-shell layout CSS** — fixed layout issues in the chat application shell.
- **Top-level `Html` export** — `Html` component now exported from `voodoo` top level.

## 1.19.0 — 2026-08-28

### Added — "Less-Code" initiative

Making Voodoo apps dramatically smaller by turning hand-rolled patterns into
framework primitives. Validated by rewriting the `ai-agent` template from
~1,850 lines (~1,120 Python + ~730 CSS + ~200 inline JS) to **one 285-line
`main.py` with zero CSS, zero inline JS, and zero custom provider classes**.

#### AI — native tool-calling protocol

- **`ToolCall` dataclass** (`name`, `arguments`, `id`) plus
  `ProviderResponse.tool_calls` — structured tool calls replace the fragile
  `[TOOL: name]` text-marker convention (kept only as the mock-provider
  fallback).
- **`OpenAIProvider`** parses native `message.tool_calls` in `complete()` and
  accumulates streaming tool-call deltas in `stream()` (flushed as
  `tool_call` events before `done`).
- **`AnthropicProvider`** parses `tool_use` blocks into `ToolCall`s.
- **`Agent`** builds native multi-turn follow-up messages (assistant
  `tool_calls` + `tool` role with `tool_call_id` echoing the call `id`), so
  providers map tool results correctly.

#### AI — config-driven providers & multi-turn

- **`[ai]` config block** (`provider`, `model`, `base_url`, `api_key`,
  `aliases`) in `voodoo.toml`/`voodoo.yaml`, with `VOODOO_AI_*` env fallbacks
  and `${VAR}` interpolation — **any OpenAI-compatible endpoint (DeepSeek,
  OpenRouter, …) now works with zero provider code**.
- **`get_provider()`** applies `ai.base_url`/`ai.api_key` as fallback kwargs
  for the `openai` provider; `ai.aliases` merge into routing aliases.
- **`default_model()`** resolves the app's model from config; `Agent()` with
  no `model` argument uses it.
- **Multi-turn conversations**: `Agent.run(prompt, history=[...])` and
  `Agent.stream(...)` accept prior turns as `Message` dicts.
- **`runtime.run_api_through_runtime`** config flag (env
  `VOODOO_RUN_API_THROUGH_RUNTIME`) replaces the `api.run_through_runtime`
  module-level hack (the attribute remains, now config-initialized).

#### Data — fluent query API & FK cascades

- **`Model.where(**filters)`** starts a lazy, chainable `Query`:
  `.order_by("-col")`, `.limit()`, `.offset()`, `await` (rows), `.first()`,
  `.count()`, `.delete()`. Class shortcuts: `Model.count(**f)`,
  `Model.first(**f)`, `Model.delete_where(**f)`.
- **`FK[ParentModel]` field annotation** — column stored as `INTEGER`;
  deleting a parent row cascades to children (registered in the model
  metaclass; portable ANSI SQL). Unconditional `delete()` is guarded.
- Exported `FK` from `voodoo` and `voodoo.data`.

#### UI — chat primitives, Icon, Markdown, reactive wiring, client SDK

- **`Icon(name, size, label)`** — curated inline-SVG icon set (~26 icons,
  stroke/currentColor; unknown names render a placeholder, never raise).
- **`Markdown(source)`** — safe, dependency-free renderer (headings,
  emphasis, inline code, fenced blocks, lists, quotes, http(s)-only links;
  **all raw HTML escaped**) in `voodoo.ui.markdown`.
- **Chat primitives**: `MessageList` (auto-scroll), `ChatMessage(role=…)`
  (user/assistant/system/tool bubbles), `StreamingText` (animated caret),
  `Composer(on_send=…)` (Enter-to-send textarea + send button),
  `Sidebar`. All styled via the `vd-*` design system — zero hand-written CSS.
- **Reactive loop wired**: `StateRenderer.bind(el, fn, cells=[...])`
  subscribes to the cells — `State.set()` during a handler now schedules the
  re-render + WebSocket patch automatically (the "zero JS" promise).
- **Client JS SDK** (`static/client.js`): `voodoo.navigate`,
  `voodoo.scrollToBottom`, `voodoo.onEnter`, auto-growing composer,
  Enter-send / Shift+Enter-newline, auto-scroll on patch/append — installed
  via `setupChatBehaviors()` after every DOM swap.
- New components exported from `voodoo` top level: `Icon`, `Markdown`,
  `MessageList`, `ChatMessage`, `StreamingText`, `Composer`, `Sidebar`.

## 1.18.0 — 2026-08-28

### Added — Theme presets, chrome components & shareable themes

- **Themes are now portable modules.** A theme is a JSON-only `theme.json`
  document (the exact shape `Theme.model_dump()` produces) plus an optional
  sibling `custom.css`. Presets resolve in order: explicit path/URL → project
  `.voodoo/theme/theme.json` → built-in (`default`, `ember-paper`) →
  `~/.voodoo/themes/<name>/` → PyPI `voodoo-theme-<name>`.
- **New theme CLI** — `voodoo theme list`, `voodoo theme use <name|path|url>`,
  `voodoo theme init`, and `voodoo theme install <name>` snapshot, switch, and
  install presets into `.voodoo/theme/` (custom CSS lives next to the JSON,
  never embedded in it).
- **`[theme]` config** — `voodoo.toml` gains `theme.preset = "<name|path|url>"`
  and honors `theme.mode`. `create_app()` activates the preset at startup.
- **`ember-paper` built-in preset** — warm paper surfaces, an ember accent
  (`#E8A33D` dark / `#B45309` light), and editorial typography (Fraunces
  display, Schibsted Grotesk body, IBM Plex Mono) with a soft `--vd-glow`
  halo token.
- **Light/dark accent tokens** — `ThemeColors` gained `light_secondary` /
  `light_on_secondary` so the accent (and its on-color) invert per mode; the
  stock indigo default is unchanged.
- **Chrome component tier** — `Navbar`, `NavLink`, `Brand`, `ThemeToggle`,
  `Hero`, `PageHero`, `Eyebrow`, `Chip`, `CodeBlock`, `Stats`, `Stat`,
  `CTABand`, `BackLink`, `FeatureCard`, and `LinkArrow` (exported from
  `voodoo` and `voodoo.ui`), each backed by generated `vd-*` CSS.
- **Dead semantic CSS is now wired** — `Nav`, `Header`, `Footer`, `Main`,
  `Section`, `Article`, `Aside`, `Figure`, `FigCaption`, `Address`,
  `Paragraph`, `Time`, and `Img` now emit their `vd-*` classes, so their
  existing stylesheet rules actually apply.
- **Motion & code tokens** — `@keyframes vd-fade-up/vd-fade-in/vd-pulse` with a
  `prefers-reduced-motion` guard, and a `--vd-code-*` syntax palette consumed
  by `CodeBlock`.
- **`tests/test_theme_presets.py` + `tests/test_chrome.py`** — preset
  resolution/round-trip and chrome rendering/CSS coverage.

## 1.17.1 — 2026-08-20

### Fixed

- **Dark-mode primary action color was invisible.** The `primary` token was
  near-black (`#18181B`) in *both* light and dark modes, which made primary
  buttons, links, and focus rings invisible on dark surfaces (the default
  mode). `primary` now inverts per mode — near-white (`#FAFAFA`) in dark mode,
  near-black (`#18181B`) in light mode — via new `light_primary` /
  `light_primary_hover` tokens that `light_overrides()` swaps in.
- **Links, focus rings, and form accents are consistently visible** in every
  mode: the indigo `secondary` token now drives `:focus-visible` rings,
  `::selection`, links, checkbox/radio accent colors, and the user-badge avatar
  (previously the now-inverted `primary`, which vanished in dark mode).
- **Default `.vd-button` now has a visible surface + border** (previously
  transparent), plus hover/active feedback so it reads as interactive in both
  modes. The Tailwind `primary` variant uses the `surface` token for its text
  color so it stays legible on the near-white dark-mode fill.

## 1.17.0 — 2026-08-20

### Changed — Sprint 15: Design system & theme engine

- **Voodoo CSS is now the polished default** — `VoodooCSSAdapter` gained full
  component coverage via `generate_component_css()`: base reset, typography
  scale, and styled `button`, `card`, `form`, `input`, `textarea`, `select`,
  `badge`, `avatar`, `divider`, `list`, `heading`, `link`, and layout classes.
- **Layout parity** — `Flex` (`direction`/`justify`/`items`/`wrap`/`gap`),
  `Grid` (`cols`/`gap`), `Container` (`size`/`centered`), and `Page`
  (`size`/`pad`) emit semantic `vd-*` classes in the default adapter. Numeric
  gaps use a 4px base (`calc(0.25rem * 4)`); named gaps use spacing tokens.
- **Theme mode plumbing** — `render_page` now emits `class="{mode}"`
  (dark/light/system, no duplicated `dark dark`) plus an inline
  `theme_init_script` that resolves the `voodoo_theme` cookie → `Theme.mode`
  → `prefers-color-scheme` before paint (no flash).
- **No hardcoded Tailwind** — auth forms and library components dropped raw
  `space-y-*`/`text-center` utilities in favor of semantic `Stack`/`Form`
  composition; `Form` now uses `style="form"` resolved by every adapter.

### Added — Sprint 15: Design system & theme engine

- **`voodoo.setTheme(mode)`** — client runtime API to toggle light/dark/system
  and persist the choice in the `voodoo_theme` cookie.
- **`Form.style = "form"`** — `_form` resolvers added to both `VoodooCSSAdapter`
  and `TailwindAdapter`.
- **`tests/test_design_system.py`** — layout parity, stylesheet coverage, and
  theme-mode plumbing tests.
- **`docs/design_system.md`** — rewritten with the token, theme, adapter, and
  layout reference; `docs/components.md` documents layout props.

## 1.16.1 — 2026-08-20

### Changed — Sprint 14b: Runtime vision alignment

- Aligned code docstrings, flow diagrams, and package metadata with the
  "programmable runtime" vision: `AI-native application framework` →
  `programmable runtime`; `STATE → INTENT → CAPABILITY → COMPUTE → EFFECT →
  STATE` → `ENTITY → STATE → INTENT → CAPABILITY → EXECUTION → EFFECT → STATE`;
  `eight architectural primitives` → `computational model`; `AI is one class
  of Compute` → `AI is one form of Compute`. `pyproject.toml` description and
  `release.yml` Homebrew `desc` updated to match. No behavior change.

## 1.16.0 — 2026-08-20

### Added — Sprint 14: ModelProvider protocol

- **`VoodooModelProvider` Protocol** — normalized model provider interface
  (`generate`, `stream`, `embed`, `count_tokens`, `describe`, `name`) in
  `voodoo.ai.providers`. `LLMProvider` now provides default implementations
  for `generate()` (delegates to `complete()`), `embed()` (raises
  `NotImplementedError`), `count_tokens()` (word-count heuristic), and
  `describe()` (conservative capability defaults).
- **`ModelDescriptor`** — static model capability descriptor (provider,
  model, modalities, context window, tool use, structured output, streaming,
  reasoning, vision, audio, embeddings, pricing) with a `qualified_name`
  property. Added `describe_model(model)` helper.
- **`EmbeddingResponse`** — embedding result dataclass (`embeddings`,
  `model`, `tokens_in`, `cost`).
- **Routing aliases** — capability aliases (`best`, `fast`, `cheap`,
  `vision`, `reasoning`) resolved from config `models.aliases` over built-in
  defaults; `resolve_model()` now accepts caller-supplied aliases.
- **`register_provider(name, class_path)`** — pluggable provider factory
  registration.
- **Provider capabilities** — `mock` (deterministic `embed()` + `describe()`),
  `openai` (`embed()` via `embeddings.create`, `base_url` support, `describe()`),
  `anthropic`/`gemini`/`ollama` (`describe()`) now conform to the interface.
- **Agent model journaling** — `model.called` and `model.completed` events
  (with `tokens_in`/`tokens_out`/`cost`) broadcast in both `Agent.run()` and
  `Agent.stream()`.
- **`voodoo generate`** — refactored to resolve models through
  `get_provider()` (no direct SDK use); `VOODOO_MODELS_DEFAULT`,
  `OPENAI_API_KEY`/`OPENROUTER_API_KEY` honored.
- **Contract tests** — `ModelProviderContractTests` mixin +
  `TestMockProviderContract` in `tests/contracts/test_model_provider.py`.

### Added — AI development workflow

- Structured guidance for AI coding agents (Claude Code, Cursor, GitHub Copilot):
  - `AGENTS.md` — root-level AI agent instructions.
  - `.github/copilot-instructions.md` — GitHub Copilot entry point.
  - `.github/instructions/` — domain-specific instruction files.
  - `.github/skills/` — structured workflows.
  - `.github/prompts/` — structured prompts.
- `ARCHITECTURE.md` — root-level architecture reference.
- Expanded PR template with documentation-sync checklist.

### Fixed

- **Labeler config** — replaced the invalid `any-glob-to-changed-file` key
  with `any-glob-to-any-file` in `.github/labeler.yml`.

## 1.15.1 — 2026-08-19

### Docs & metadata cleanup

- **`ROADMAP.md`** — consolidated master architectural & engineering plan
  (replaces the former `MASTER_ROADMAP.md` and
  `VOODOO_RUNTIME_PROTOCOL_ARCHITECTURE.txt`); `SPRINT_PLAN.md` now sources
  the roadmap from `ROADMAP.md`.
- **`README.md`** — PyPI/Python/License/CI/download badges, table of
  contents, and expanded feature/primitive documentation.
- **`pyproject.toml`** — full project metadata: description, authors,
  maintainers, keywords, classifiers, license, and `[project.urls]`
  (homepage, docs, repository, changelog, roadmap).
- **Community files** — `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `LICENSE` (MIT), GitHub issue templates, and pull request template.
- **Docs consolidation** — removed stale `docs/ai/*` scaffolding; added
  `docs/adaptive.md`, `docs/hitl.md`, `docs/runtime.md`.
- **`.env.example`** — refreshed configuration reference.

## 1.15.0 — 2026-08-18

### Redis queue + cache (Sprint 13 — optional distributed backend)

- **`[redis]` extra** — `pip install "voodoo-framework[redis]"` adds
  `redis>=5.0`; redis remains an optional import, so nothing in the default
  path imports it (explicitly optional per spec §8).
- **`RedisQueue`** (`voodoo.storage.queue.redis`) — a durable, multi-process
  queue provider behind the `VoodooQueue` protocol with the same semantics
  as SQLite/Postgres: priority ordering, delayed delivery, idempotency keys,
  lease-based claiming, per-status stats, and retry-with-backoff. Claims are
  atomic Lua scripts over ZSETs + per-task hashes, so concurrent workers
  never claim the same task. Capabilities are honest: `at_least_once`
  delivery, `best_effort` ordering, `durable=True`.
- **`RedisCache`** (`voodoo.storage.cache.redis`) — a TTL-capable, durable
  cache provider behind the new `VoodooCache` protocol
  (`CacheCapabilities.ttl=True`, `.durable=True`).
- **Cache seam** — new `VoodooCache` protocol + `CacheCapabilities` +
  `CacheContractTests`; `MemoryCache` moves out of the registry, gains
  `capabilities()` (`ttl=False`, `durable=False`), and rejects `set(ttl=...)`
  with a `CapabilityError` rather than silently dropping the TTL.
- **Registry wiring** — `register_queue("redis", ...)` and
  `register_cache("redis", ...)` factories with URL resolution
  (`url` → `VOODOO_QUEUE_URL`/`VOODOO_CACHE_URL` → `VOODOO_REDIS_URL` →
  `extra.host`/`port`/`db` → `redis://localhost:6379/0`).
- **Contract suites vs real Redis** — new `tests/contracts/test_queue_redis.py`
  and `tests/contracts/test_cache_redis.py` run the full `QueueContractTests`
  / `CacheContractTests` mixins (plus reconnect + TTL-expiry extras) against a
  live server when `VOODOO_TEST_REDIS_URL` is set.
- **Redis parity for local dev + CI** — `just redis-up` / `just redis-down`
  recipes, `.env.example` documentation, and a `redis:7` service container in
  `ci.yml` and `release.yml` (mirroring the `postgres:16` / `minio` pattern)
  so the Redis contract suites run in CI.

## 1.14.0 — 2026-08-18

### S3/R2 object store hardening (Sprint 12 — production object storage)

- **`[s3]` extra** — `pip install "voodoo-framework[s3]"` adds `boto3` /
  `botocore`; boto3 remains an optional import, so the object store falls
  back to `LocalObjectStore` when the extra is absent.
- **`S3ObjectStore` hardening** (`voodoo.storage.objects.s3`):
  - **Presigned PUT** — `presign_put(key, expires_in)` alongside GET, so
    clients can upload objects directly to the bucket.
  - **Multipart uploads** — objects ≥ 8 MiB (configurable via
    `multipart_threshold`) upload via
    `create_multipart_upload` / `upload_part` / `complete_multipart_upload`
    with abort-on-failure; `ObjectStoreCapabilities.multipart` is now `True`.
  - **R2 / MinIO path-style addressing** — non-AWS endpoints use path-style
    URLs automatically (AWS keeps virtual-hosted style); `url()` reflects it.
  - **`region` handling** — region from `AWS_REGION` / `AWS_DEFAULT_REGION`.
  - **`close()` lifecycle** — releases the boto3 client's connection pool.
- **Registry bug fix** — `_create_s3_objects` passed `access_key`/`secret_key`/
  `region` kwargs that `S3ObjectStore.__init__` rejected (TypeError with
  `objects.provider: s3`); it now constructs the store with matching
  `key`/`secret`/`region` kwargs and reconciles the `VOODOO_S3_*` env vars.
- **Object store contract suite vs real S3** — new
  `tests/contracts/test_objectstore_s3.py` runs the full
  `ObjectStoreContractTests` mixin (put/get/delete/stat/list/reopen) plus
  presigned GET/PUT roundtrips, multipart upload, and path-style URL checks
  against a live S3-compatible server when `VOODOO_TEST_S3_ENDPOINT` is set.
- **MinIO parity for local dev + CI** — `just minio-up` / `just minio-down`
  recipes, `.env.example` documentation, and a `minio` service container in
  `ci.yml` and `release.yml` (mirroring the `postgres:16` pattern) so the
  S3 contract suite runs in CI.

## 1.13.0 — 2026-08-18

### PostgreSQL queue, events & execution store (Sprint 11 — the durable runtime on PG)

- **`PostgresQueue`** (`voodoo.storage.queue.postgres`) — a durable queue
  provider behind the `VoodooQueue` protocol with the same semantics as
  `SQLiteQueue`: transactional claims under a lease, retry with backoff,
  priority, delayed delivery, and idempotent enqueue. Claims use
  `FOR UPDATE SKIP LOCKED` so concurrent workers never claim the same task.
  Provider: `postgres` (`VOODOO_QUEUE_PROVIDER=postgres`).
- **`PostgresEventStore`** (`voodoo.storage.events.postgres`) — a durable
  event bus provider behind the `VoodooEventBus` protocol (publish /
  subscribe / replay) with the same schema as `SQLiteEventBus`. Provider:
  `postgres` (`VOODOO_EVENTS_PROVIDER=postgres`).
- **`PostgresExecutionStore`** (`voodoo.storage.execution.postgres`) — the
  durable execution store (materialized `executions` + `execution_events`
  journal, artifacts, approvals) on PostgreSQL, conforming to the sync
  `ExecutionStore` protocol. The app lifespan now runs the execution store on
  PG automatically when `database.provider: postgres` (the Sprint 10 guard is
  removed); the scheduler remains SQLite-backed (documented).
- **Shared translated migrations** — artifacts + approvals DDL is extracted
  into the shared framework migration list (new versions 7/8), so PostgreSQL
  creates the same TEXT/JSON schema as SQLite via the migration runner
  (JSONB / TIMESTAMPTZ remain a future sprint). `SQLiteExecutionStore._migrate()`
  now reuses the shared migrations instead of duplicated inline DDL.
- **Registry & config wiring** — `postgres` queue/events factories registered
  in `ProviderRegistry`; `voodoo doctor` capability matrix now lists the
  postgres queue and event bus rows.
- **Contract + failure-path tests against a real server** —
  `tests/contracts/test_queue_postgres.py` (28 tests: contract, reconnect,
  skip-locked, idempotency, lease expiry, concurrent claims),
  `test_eventbus_postgres.py` (9 tests), and `test_execution_postgres.py`
  (11 tests) run when `VOODOO_TEST_DATABASE_URL` is set; CI and the release
  workflow provide a `postgres:16` service container. Local `pytest` skips
  cleanly without a server.
- **Defect fix** — `src/voodoo/schedule.py` registered its migration with
  three positional args (crash); it now builds a `Migration` object and
  registers it correctly.
- **Docs** — `docs/architecture.md`, `docs/data.md`, `docs/workers.md`,
  `docs/mesh.md`, and `docs/deployment.md` document the PG queue/events/
  execution store and production PostgreSQL configuration.

## 1.12.0 — 2026-08-18

### PostgreSQL database adapter (Sprint 10 — server-backed storage, same protocol)

- **`voodoo.storage.database.postgres.PostgresDatabase`** — a complete
  PostgreSQL backend behind the same `VoodooDatabase` protocol as SQLite.
  Async psycopg 3 (`psycopg[binary]`), lazy import, dict rows, and the same
  migration list v1–v6 plus app migrations. Provider: `postgres`.
- **Placeholder/DDL translation** — application and framework SQL (`?`
  placeholders, `AUTOINCREMENT`) is adapted adapter-side: `?` → `%s`,
  `??` → escaped `?`, `AUTOINCREMENT` → `GENERATED BY DEFAULT AS IDENTITY`.
  `"abc"` string literals, `--` line comments and `/* */` block comments are
  preserved.
- **`transaction()` is atomic** — explicit BEGIN/COMMIT/ROLLBACK via
  psycopg's transaction block even while plain `execute()` calls run in
  autocommit (mirroring the SQLite adapter's per-statement commit).
- **`[postgres]` extra** — `pip install "voodoo-framework[postgres]"`.
- **Configuration** — `database.provider: postgres` + `database.url`
  (`postgres://`, `postgresql://` pass through `_resolve_db_path`); env
  `VOODOO_DATABASE_URL` / `VOODOO_DATABASE_PROVIDER`; or URL parts
  (`host`/`port`/`dbname`/`user`/`password`) under `database.extra`.
  Other non-sqlite schemes (`mysql://`, …) still raise `ConfigurationError`
  with an actionable message.
- **Capability-aware data layer** — `BaseModel` detects the backend:
  `_create_table` emits identity columns on PG, `insert()` uses
  `RETURNING id` (PG) vs `lastrowid` (SQLite). `auth.user` boolean filters
  now bind `?`-parameterized `true` instead of literal `1`.
- **Lifespan guard** — the app refuses `database.provider: postgres` until
  the execution/schedule stores are protocol-bound (Sprint 11), with an
  actionable `ConfigurationError` instead of mixed-writer state.
- **`voodoo doctor`** — capability matrix now includes PostgreSQL
  (transactions/migrations/native JSONB/concurrent writers).
- **Contract tests against a real server** — `tests/contracts/test_database_postgres.py`
  runs the full `DatabaseContractTests` suite when
  `VOODOO_TEST_DATABASE_URL` is set; CI provides a `postgres:16` service
  container. Local `pytest` skips cleanly without a server.
- **Docs** — `docs/data.md` documents the backend boundary, pooling choice
  (single in-process async connection mirroring aiosqlite; psycopg_pool is
  the documented future option), and JSONB payload status.

## 1.11.0 — 2026-08-18

### Runtime configuration (Sprint 9 — infrastructure by configuration, never code)

- **Provider registry** (`voodoo.adapters.registry`) — a central
  `ProviderRegistry` maps names → adapter factories for database, queue,
  events, objects, and cache. Sprints 1–7 implementations are registered
  (sqlite/memory queue, sqlite/local events, local/S3 objects, memory cache);
  future adapters (Postgres, Redis, …) register their factories here (§31).
- **`voodoo.yaml` provider blocks** — `database`, `queue`, `events`,
  `objects`, `cache`, `models` are now first-class config blocks with typed
  pydantic models. The default file is all-local and zero-config behavior is
  identical to today.
- **Env interpolation** — `${VAR}` and `${VAR:default}` are expanded
  recursively across strings, dicts, and lists in both `voodoo.yaml` and
  `voodoo.toml`.
- **Precedence** — explicit file config > env vars (`VOODOO_QUEUE_PROVIDER`,
  `VOODOO_DATABASE_PROVIDER`, …) > local defaults, verified by tests.
- **Actionable validation** — unknown providers raise `ConfigurationError`
  listing the available providers for that category.
- **`voodoo doctor`** — now prints the resolved provider for queue, events,
  objects, cache, and the default model alias.
- **`init_db` is provider-driven** — the database connection is resolved
  through the registry (with migrations passed explicitly), while
  `get_db()`/`close_db()` remain backward compatible.
- **`tests/test_config.py`** & **`tests/test_provider_switching.py`** — pin
  interpolation, precedence, registry resolution/errors, and the sprint's
  done-when: the same app runs against `queue: sqlite` then `queue: memory`
  with zero application-code edits.

## 1.10.0 — 2026-08-18

### Adapter contracts & capability negotiation (Sprint 8 — never silently violate correctness)

- **`voodoo.adapters.capabilities`** — a single capability model shared by
  every adapter kind: `AdapterCapabilities` (provider + boolean feature
  flags), `DatabaseCapabilities`, `QueueCapabilities`, `EventBusCapabilities`,
  and `ObjectStoreCapabilities` (§9).
- **Every adapter declares guarantees** via `.capabilities()` — SQLite and
  memory queue, SQLite and local event bus, local and S3 object store, and
  SQLite database each report their durability, ordering, delivery,
  transaction, and visibility guarantees.
- **Runtime negotiation** (§10) — `require()` rejects an unsupported required
  operation with an explicit `CapabilityError` (kind/provider/feature/hint),
  `negotiate()` proceeds when supported and emulates when a safe fallback is
  supplied, and `capability_matrix()` renders a uniform provider matrix.
- **Memory queue delayed delivery now fails loudly** — `enqueue(delay>0)`
  raises `CapabilityError` ("queue provider 'memory' does not support
  'delayed_delivery' — use a durable queue provider (sqlite)") instead of
  silently enqueueing immediately.
- **`voodoo doctor` capability matrix** — prints each active provider and its
  declared feature flags.
- **`tests/contracts/test_capabilities.py`** — pins `require`/`negotiate`/
  `capability_matrix` rules; the queue contract's `test_delayed_delivery` is
  now capability-aware (asserts loud rejection for memory, real delayed
  delivery for SQLite).

## 1.9.0 — 2026-08-18

### EventBus protocol & mesh unification (Sprint 7 — events survive restarts)

- **`VoodooEventBus` protocol** (`voodoo.storage.events`) — `publish`,
  `subscribe`, `replay` with a declarative `EventBusCapabilities`
  (durability, replay, ordering, delivery semantics).
- **Event envelope** (§17) — every event carries `event_id`, `event_type`,
  `timestamp`, `source`, `subject`, `correlation_id`, `causation_id`,
  `payload`, and `schema_version`; correlation id defaults to the ambient
  trace id so execution trace linkage is end-to-end.
- **`LocalEventBus`** (in-process, non-durable — today's mesh behavior) and
  **`SQLiteEventBus`** (durable event log, replayable subscriptions), both
  registered as framework migrations; WAL mode + `check_same_thread=False`.
- **Mesh unified** — `mesh` publishes through the active bus while local
  handlers still flow through the engine (`_fire_local`) with the raw payload;
  `expose()`/WS remote mesh are unchanged externally.
- **`tests/contracts/test_eventbus.py`** — `EventBusContractTests`
  (publish/subscribe/replay/no-lost-subscriber-on-error).

## 1.8.0 — 2026-08-18

### Object store & artifacts (Sprint 6 — provenance for generated payloads)

- **`VoodooObjectStore` protocol** (`voodoo.storage.objects`) —
  `put/get/delete/exists/stat/list` + `presign`/`url` where supported, with a
  declarative `ObjectStoreCapabilities` (presign_urls, checksums, metadata,
  multipart).
- **`LocalObjectStore`** — the default embedded backend under
  `.voodoo/objects/` with SHA-256 sharded paths and a `metadata.db` table
  (key, size, content_type, checksum, created_at).
- **`S3ObjectStore`** — S3 logic extracted out of `StorageManager` into its
  own adapter; `StorageManager` is now a thin facade (behavior-compatible),
  so `status.py` and downstream callers are unchanged.
- **Artifacts + provenance** (§46) — `artifacts` table (id, execution_id,
  parent_artifact_id, created_by, tool, model, checksum, metadata,
  created_at) + `Execution.artifact()` helper + `SQLiteExecutionStore`
  `record_artifact`/`list_artifacts`.
- **`tests/contracts/test_objectstore.py`** — `ObjectStoreContractTests`.

## 1.7.0 — 2026-08-18

### Durable Scheduler (Sprint 5 — schedule.at/after/every/cron)

- **`voodoo.schedule` public API** — `at(when, task_type, payload)`,
  `after(seconds, task_type, payload)`, `every(seconds, task_type, payload)`,
  `cron(expr, task_type, payload)` durably persist schedule rows via
  `SQLiteScheduleStore`; the `ScheduleService` tick loop (already wired into
  the app lifespan) claims due schedules and enqueues them as durable tasks.
  Available as `voodoo.schedule` (module) or `from voodoo import schedule`.
- **`TimeSpec` consumed** — `schedule.from_spec(TimeSpec, task_type, payload)`
  dispatches to `cron`/`every`/`at` based on `TimeSpec.schedule`,
  `TimeSpec.interval`, and `TimeSpec.deadline` respectively, closing the
  previously-dead `TimeSpec.schedule`/`TimeSpec.interval` fields.
- **`voodoo schedules` CLI registered** — `list`, `pause <id>`, `resume <id>`
  (the command module existed but was never mounted on the root Typer app).

## 1.6.0 — 2026-08-18

### Checkpoints & resume (Sprint 4 — interrupted executions resume)

- **Durable checkpoints** — `Execution.checkpoint` captures JSON-serializable
  resumable state (completed effect ids, state-changes count, step sequence)
  at meaningful boundaries: after state mutation, before waiting, and on
  completion.
- **Recovery flow** — `engine.recover()` restores unfinished executions,
  marks leftover `running` executions `waiting`, and rehydrates persisted
  `Approval` records (status, decided_by, reason) from the new `approvals`
  table.
- **Approval persistence** — pending approvals are written to the store and
  decisions (`human.approved` / `human.denied`) are recorded as journal
  events, so a restart no longer rebuilds approvals as memory-only placeholders.
- **Idempotent effects** — journaled effects carry `idempotency_key`
  (`{execution_id}:{effect_id}`) so a resumed execution skips already-completed
  non-idempotent effects (§15).

## 1.5.0 — 2026-08-18

### Durable Executions (Sprint 3 — executions survive restarts)

- **`SQLiteExecutionStore`** (`voodoo.storage.execution`) — the default durable
  execution store: a materialized `executions` table (id, trace_id,
  parent_execution_id, status, actor, intent, capabilities, resources, effects,
  state_changes, result, error, metadata, checkpoint, timestamps) plus an
  append-only `execution_events` journal (sequence, execution_id, event_type,
  payload, timestamp). Registered as framework migration version 3; WAL mode
  and `check_same_thread=False` for cross-thread asyncio workers.
- **Event journal** — every `save()` appends a status-derived event
  (`execution.created` / `execution.started` / `execution.completed` /
  `execution.failed` / `execution.waiting`) and provides `timeline(id)` /
  `list_events()` for reconstruction and inspection.
- **Engine default** — the app lifespan now attaches `SQLiteExecutionStore`
  (`config.db_path`, default `.voodoo/state/data.db`) to the engine, so
  `engine.recover()` reads SQLite and restores unfinished executions with
  journal history intact.
- **CLI wired** — `voodoo executions list|show|events`, plus top-level
  `voodoo execution <id>` (timeline from the journal) and `voodoo events`;
  `voodoo recover` now defaults to SQLite (legacy `.jsonl` still readable via
  `--store …/executions.jsonl`); `voodoo executions import-jsonl <file>`
  migrates a legacy `JSONFileExecutionStore` into SQLite.
- **Failure surface** — persistence failures raise (`engine._persist`) rather
  than being silently swallowed, per spec §51.16, with a regression test.

## 1.4.0 — 2026-08-17

### Durable Task Queue (Sprint 2 — tasks survive restarts)

- **`VoodooQueue` protocol** (`voodoo.storage.queue`) — backend-neutral durable
  task queue: `enqueue`, `claim`, `heartbeat`, `complete`, `fail`, `release`,
  `release_expired`, `retry`, `list`, `stats` with declarative
  `QueueCapabilities` (durability, delivery semantics, visibility timeout,
  delayed delivery, priority, transactions).
- **`SQLiteQueue`** — the default durable provider: `tasks` table (migration
  0002) with atomic `UPDATE … RETURNING` claim (concurrent workers never claim
  the same task), lease-based visibility timeout, exponential backoff retries,
  priority ordering, delayed delivery, and `idempotency_key` deduplication for
  at-least-once semantics. Reclaims expired leases from dead workers.
- **`MemoryQueue`** — the ephemeral in-process provider, selected via
  `VOODOO_QUEUE_PROVIDER=memory`. Preserves the legacy `asyncio.Queue` behavior
  for non-critical work.
- **Workers reworked** — `workers/queue.py` now polls/claims from the durable
  queue instead of draining an `asyncio.Queue`; a background reaper reclaims
  expired leases. `@task`/`@queue`/`enqueue`/`start_workers`/`stop_workers`
  public API unchanged.
- **`voodoo.tasks` CLI** — `voodoo tasks list` (with stats), `voodoo tasks
  retry <id>`.
- **Queue contract test suite** (`tests/contracts/test_queue.py`) —
  `QueueContractTests` portability mixin (enqueue/claim/complete, fail/retry,
  release, idempotency, priority, delayed delivery, heartbeat, lease expiry,
  concurrent claims) run against both Memory and SQLite providers (43 tests).

## 1.3.0 — 2026-08-17

### Storage Core & Migrations (Sprint 1 — durable runtime foundation)

- **`VoodooDatabase` protocol** (`voodoo.storage.database`) — backend-neutral
  database capability: connection lifecycle, migration runner, transaction
  helper, query primitives, and declarative `DatabaseCapabilities`
  (transactions, migrations, native JSON, concurrent writers). The adapter
  boundary for the future PostgreSQL backend.
- **`SQLiteDatabase`** — the default embedded backend, now with WAL
  journaling on file-backed databases, `busy_timeout`, and an ordered
  idempotent migration runner tracked in a `schema_migrations` ledger.
  Migrations support static statements, async functions, and re-runnable
  idempotent steps; duplicate versions are rejected.
- **User-model DDL is now migration 0001** (`user_model_baseline`) —
  registered by `voodoo.data`, re-runs its `CREATE TABLE IF NOT EXISTS` DDL
  on every `init_db` so late-imported models keep working. Existing
  databases upgrade in place: the first run records the baseline without
  touching existing tables.
- **`voodoo.storage` is now a package** — `StorageManager` moved to
  `voodoo.storage.manager` with import-compatible re-exports
  (`from voodoo.storage import storage` unchanged).
- **Database contract test suite** (`tests/contracts/test_database.py`) —
  `DatabaseContractTests` portability mixin (ledger tracking, idempotent
  migrations, write/read roundtrip, transaction commit/rollback, reconnect
  durability, capability declaration). Every future adapter must pass it
  unchanged.

## 1.2.0 — 2026-08-17

### Unified Runtime Engine — every participant runs through one execution system

Voodoo now has a single `ExecutionEngine` that produces an `Execution` record (with `execution_id`, `trace_id`, `status`, `effects`, `state`, `cost`, `error`, `parent_execution_id`) for every meaningful operation. All nine participant types — HTTP, Agent, Tool, MCP, Worker, Task, Workflow, Human approval, Event handler — are now integrated.

### Human-in-the-Loop (HITL)

- **`ask_human()`** — humans as compute participants. Raises `ApprovalRequired`, execution enters `waiting` state.
- **`engine.approve(id)` / `engine.deny(id)`** — resume or fail a waiting execution as a child execution (shared trace, `parent_execution_id` link).
- **`Task(human=True, approval_capability=...)`** — human tasks inside workflows.
- **`voodoo inspect approvals`** — CLI command to list pending/decided approvals.
- **`voodoo recover`** — CLI command to reload unfinished executions from the persistence store after a restart.

### Durable Persistence & Recovery

- **`JSONFileExecutionStore`** — append-only JSONL store, corrupt-line tolerant.
- **`Engine.use_store(store)`** — attach a persistence backend.
- **Checkpointing** — executions persisted on terminal states + `waiting` (approval) + mid-workflow (per-task in sequential/parallel strategies).
- **`Engine.recover()`** — reloads unfinished executions (created/planned/authorized/running/waiting) and rebuilds pending approval records.

### Planner (Phase 12)

- **`Planner`** — deterministic capability → compute participant resolution. Registers agents, tools, workers, humans as `ComputeParticipant` with declared capabilities.
- **`Plan`** — strategy + per-capability step assignment with fallbacks and approval flags.
- **`voodoo inspect plan <intent> --requires cap1,cap2`** — debug surface showing the planner's decisions.

### Adaptive Runtime (Phase 13)

- **`AdaptiveSupervisor`** — supervisor loop with explicit decisions: `continue | retry | delegate | fallback | wait | request_approval | fail`.
- **Resource budget steering** — `SupervisorConfig.budget` accumulates per-step cost/tokens/latency and stops when exhausted.
- **Constraint → retry hook** — `ConstraintEnforcer.retry_hint(intent=...)` checks for `kind="retry"` constraints; the supervisor retries the same step instead of failing.
- **`WorkflowStrategy.ADAPTIVE`** — delegates to planner + supervisor.

### Integration: all participants through the engine

| Participant | Integration |
|---|---|
| HTTP request | `api._run_through_runtime` → `engine.execute` |
| Agent | capability-gated tool calls, effects lifted to Execution |
| Tool | `ToolSpec.permissions` enforced |
| MCP tool | `_run_tool_call` routes through engine (intent `mcp:<tool>`) |
| Worker | `_run_worker` executes via engine (intent `worker:<name>`) |
| Event handler | mesh handlers as child executions (intent `mesh:<event>`) |

### CLI

- `voodoo inspect plan <intent> --requires ...` — planner debug surface
- `voodoo inspect approvals [--pending] [--json]` — human approvals
- `voodoo recover [--store path] [--json]` — reload unfinished executions

### Tests

- **547 tests passing**, ruff clean.
- New test files: `test_human.py` (6), `test_persistence.py` (12), `test_http_runtime.py` (5), `test_mcp_runtime.py` (3), `test_planner_adaptive.py` (13), plus additions to `test_mesh.py` (2), `test_workers.py` (2), `test_cli_inspect.py` (6).

## 1.1.1 — 2026-08-17

### Default scaffold — Voodoo CSS + folder-based routing

- **`voodoo new` default template** now uses Voodoo CSS (the default adapter) and folder-based routing instead of Tailwind utility classes + `main.py`/`@page`.
- **Scaffold structure**: `app/page.py` → `/`, `app/about/page.py` → `/about`, `app/users/[id]/page.py` → `/users/{id}` (dynamic segment with `int` coercion).
- **Best practices showcased**: semantic component props (`variant`, `size`, `tone`, `level`), `Page`/`Stack`/`Flex`/`Card` layout, `(SEO, Component)` tuple returns, `A` + `voodoo.navigate()` for internal links.
- **Remote template repo** (`helderperez-dev/voodoo-templates`) `default/` variant updated to match.
- No `main.py`, `.env`, or infrastructure boilerplate — `voodoo dev` auto-discovers via `voodoo.core:app`.

### Bug fixes

- **`voodoo dev` module resolution**: Added `importlib.util.find_spec` check so importable packages (e.g. `voodoo.core`) are recognized even when not present as local files. Fixes `voodoo dev` in folder-routing projects with no `main.py`.
- **`find_spec` exception handling**: Wrapped `find_spec` in `try/except (ModuleNotFoundError, ValueError)` to prevent unhandled tracebacks when a dotted module's parent package is missing.

### Documentation

- Updated `docs/routing.md` and `docs/installation.md` to reflect folder-based routing as the scaffold default.
- Updated fallback AI rules (`scaffolding.py`) to describe Voodoo CSS as the default adapter and folder-based routing convention.

## 1.1.0 — 2026-08-16

### Scaffold revision — progressive complexity

- **Minimal scaffold**: `voodoo new` now produces only `app/page.py`, `voodoo.toml`, `pyproject.toml`. No `main.py`, `.env`, placeholder directories, or infrastructure files.
- **`voodoo ai init`**: New CLI command for opt-in AI development context. Replaces automatic AI asset generation during `voodoo new`. Supports `--ide` flag (trae, cursor, windsurf, vscode, all).
- **`voodoo dev` auto-discovery**: When no `main.py` exists, `voodoo dev` uses `voodoo.core:app` (lazy ASGI app). `main:app` still supported for backward compatibility.

### Lazy runtime

- **Lazy database**: SQLite initializes on first `get_db()` call, not at startup. Default path changed from `.data/voodoo.db` to `.voodoo/state/data.db`.
- **Lazy storage**: No storage directories created unless storage is used. Conditional `/storage` mount only if directory exists.
- **Lazy workers**: Worker subsystem starts only if workers are registered.
- **Conditional `public/` mount**: Static assets mounted only if `public/` directory exists.

### Configuration

- **`voodoo.toml`**: Added TOML config support (preferred for new projects). YAML compatibility preserved. Precedence: `voodoo.toml` > `voodoo.yaml` > env vars > defaults.

### Architectural primitives

- **`voodoo.primitives` package**: Eight fundamental computational primitives — State, Capability, Intent, Effect, TimeSpec, ComputeSpec, Resource, Constraint.
- **Execution model**: STATE → INTENT → CAPABILITY → COMPUTE → EFFECT → STATE, with TIME + CONSTRAINTS surrounding the lifecycle and RESOURCE determining execution.
- **AI as Compute**: AI is one class of Compute, not a separate subsystem. `ComputeSpec.reasoning(provider="openai", model="gpt-4o")`.
- **Capability-based security**: Explicit, composable, revocable, delegatable permissions. `Capability.timed("payment.execute", expires_in=600)`.
- **59 new tests** for all primitives and their composition.

### CLI

- `voodoo new` — minimal scaffold (no `--ide` flag, no AI sync)
- `voodoo ai init [--ide <ide>]` — opt-in AI context
- `voodoo dev` — auto-discovers app
- `voodoo routes` — auto-discovers app
- `voodoo doctor` — updated AI kit hint to `voodoo ai init`

### Backward compatibility

- Existing projects with `main.py`, `app/pages/`, `.data/`, `storage/`, `voodoo.yaml` continue to work.
- `create_app()` and `App` preserved.
- All existing features (agents, MCP, mesh, workers, auth, security, SEO, telemetry, components, state, CLI generation) preserved.

---

## 1.0.0 — 2026-08-15

First stable release of Voodoo — the AI-native application framework for Python.

### Core Runtime
- `App` central facade wrapping the ASGI/Starlette machinery with `app.run()` dev server
- `@page(path)` decorator for SSR routes with path params and type coercion
- `api` namespace (`api.get/post/put/delete/patch`) for JSON endpoints
- Error hierarchy: `VoodooError` tree covering all subsystems
- Env-driven configuration (`VOODOO_ENV`, `VOODOO_DEBUG`, `DATABASE_URL`, provider keys)

### Reactive State & Events
- `state()` reactive primitive: `get()`, `set()`, `update()`, `subscribe()`
- `@event` decorator: auto-registers async handlers for browser events
- `StateRenderer`: re-renders page functions and broadcasts DOM patches over WebSocket
- `client.js`: minimal browser runtime with exponential backoff reconnection
- Zero-JS developer experience: state changes trigger live UI updates

### UI Component System
- Single `Component` base: child flattening, attribute pipeline, HTML escaping
- Semantic props: `variant`, `size`, `tone` on components
- Accessibility defaults baked in (roles, aria, semantic HTML)
- `StyleAdapter` boundary: Tailwind isolated in `adapters/tailwind`
- `Theme` semantic tokens translated to CSS variables / Tailwind config
- VoodooCSS adapter: framework CSS with `--vd-*` tokens
- Custom CSS via `styles.css` convention and `class_` escape hatch

### Data & Workers
- `Model` CRUD facade: `create()`, `get()`, `all()`, `save()`, `delete()`
- Built on Pydantic + aiosqlite with `on_insert`/`on_update` hooks
- Storage backend boundary designed for future PostgreSQL adapter
- `@task` worker decorator: retries with backoff, timeout, telemetry spans
- Queue integration with Mesh events (`@mesh.on` → `@task` chain)
- Single-process scope; distributed backend boundary named

### Auth & Security
- JWT auth with proper expiry, `nbf` validation, constant-time comparison
- Session cookies: `HttpOnly`, `SameSite=lax`, `Secure` in production
- CSRF double-submit cookie with M2M exemption
- CORS with `Vary: Origin` and disallowed-origin suppression
- Rate limiting with client isolation
- Security headers: CSP, HSTS, X-Frame-Options, Permissions-Policy
- PBKDF2-HMAC-SHA256 password hashing (600K iterations, OWASP standard)
- Route guards: `login_required`, `requires_role`, `requires_permission`
- Production error handling: no stack/secret/path leakage

### Tools & Providers
- `@tool` decorator → `ToolSpec` with schemas from typing, permissions, source metadata
- `ToolRegistry`: single source of truth for all tools
- One tool definition serves: Python calls, Agent runs, MCP consumers, Mesh exposure
- `LLMProvider` interface: `complete()`, `stream()`, token/cost accounting
- Providers: OpenAI, Anthropic, Gemini, Ollama (optional extras, lazy imports)
- `MockProvider` for deterministic CI testing (no network)
- `model="provider:model"` resolution

### Agent
- `Agent(model=..., tools=[...])` with execution loop: prompt → model → tool calls → final
- `run()` returns `AgentRun` record: run_id, model, provider, timings, tokens, cost, tool calls, status
- `stream()` yields normalized events: `text | tool_started | tool_finished | thinking | error | completed`
- Lifecycle states: created → configured → running → (tool_call ⇄ thinking) → completed | error
- Explicit `context={...}` parameter (context ≠ memory ≠ database)
- Agent lifecycle publishes namespaced Mesh events

### Mesh
- `mesh.emit()` / `mesh.on()` / `mesh.expose()` — three verbs
- Event envelope: id, timestamp, source, correlation_id
- Namespaced event names enforced (`agent.started`, not `started`)
- `expose` = explicit remote capability with permission awareness
- Local event ≠ remote event boundary documented

### MCP
- MCP layer consumes `ToolRegistry` (no separate `@mcp_tool`)
- Schema generation from `ToolSpec` type hints
- SSE endpoint with JSON-RPC protocol
- `MCPClient` for external tool consumption

### Telemetry
- `trace` decorator with span recording
- Correlation IDs via `ContextVar` propagated: request → mesh → worker → agent → tool → db
- AI telemetry: per-run records with model, provider, latency, tokens, cost, tool calls
- Tool call telemetry with error tracking
- Unified summary API for DevTools/doctor consumption

### CLI
- `voodoo new my_app` — scaffolding with file-based pages structure
- `voodoo dev` — dev server with startup banner
- `voodoo routes` — list registered routes
- `voodoo doctor` — health checks across all subsystems
- `voodoo version` — print version
- File-based pages: `pages/index.py`, `pages/about.py`, `pages/users/[id].py`

### Quality
- 381 tests: contract, unit, integration, security, performance
- Public API pinned by contract test (semver 1.0)
- Ruff lint clean, mypy configured
- Deterministic mock LLM provider for CI (no network)
- 16 documentation pages following the page formula
- 5 example apps including the AI SaaS killer demo
- Clean install: `uv tool install voodoo-framework` → `voodoo new` → `voodoo dev`

### Packaging
- Optional extras: `voodoo[ai]`, `voodoo[mcp]`, `voodoo[dev]`
- Core install stays lean (providers lazy-imported)
- Package data includes `client.js`

---

## 1.0.22 — Pre-release baseline

Initial baseline audit and working repository state before the 1.0 implementation plan.
