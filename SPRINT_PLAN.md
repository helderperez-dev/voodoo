# Voodoo — Runtime & Protocol Implementation Plan (Sprint Tracker)

Source spec: [`ROADMAP.md`](ROADMAP.md) — the master architectural and
engineering plan (formerly `VOODOO_RUNTIME_PROTOCOL_ARCHITECTURE.txt`).
Historical record of the completed 1.2.0 milestone: `IMPLEMENTATION.md`.

This file is the **single source of truth** for progress. Each sprint is a
small, complete, releasable feature. Work sprints strictly in order. Each sprint
ends with a pushed commit and a released version (PyPI + Homebrew + uv via the
existing automated workflow).

**Voodoo is a programmable runtime for adaptive applications and operational
systems.** Web, APIs, agents, workers, human workflows, distributed systems,
and physical systems are manifestations of one runtime that converge on
**Execution**. Every sprint below advances that convergence — a sprint is done
only when it moves the runtime closer to one coherent model, not when it adds
another disconnected feature.

> **Spec references.** Sprint headings cite `Spec §NN` from the *original*
> runtime protocol spec. That spec was consolidated into
> [`ROADMAP.md`](ROADMAP.md), which renumbers sections (§0–§78). Sprints 14+
> cite `ROADMAP §NN` explicitly. The pre-consolidation `Spec §NN` references
> on Sprints 1–13 and in the Rules/Backlog/Appendix sections are historical
> only — resolve them against `ROADMAP.md` when implementing.

---

## Current Position

| | |
|---|---|
| **Latest release** | `1.19.1` (`src/voodoo/__init__.py` → `__version__`) |
| **Sprints 1–15 + L1–L5** | ✅ All DONE |
| **Next sprint** | **Sprint 19 — Capability security & secrets → `2.2.0`** |

**Release cadence (one version per sprint, minor bump each):**

| Sprint | Version | Sprint | Version |
|--------|---------|--------|---------|
| 14 — ModelProvider protocol | 1.16.0 | L1 — Native tool calling | 1.19.0 |
| 14b — Runtime vision alignment | 1.16.1 | L2 — Config-driven AI | 1.19.0 |
| 15 — Voodoo Design System & CSS | 1.17.0 | L3 — ORM query API | 1.19.0 |
| 15 patch — primary token fix | 1.17.1 | L4 — UI/realtime foundation | 1.19.0 |
| 15 patch — chrome & themes | 1.18.0 | L5 — ai-agent template rewrite | 1.19.0 |
| — | — | 19.1 patch — chat layout fix | 1.19.1 |
| 16 — Memory capability | 1.20.0 | 20 — Observability | 2.2.0 |
| 17 — Agents as durable entities | 2.0.0 | 21 — Protocol schemas | 2.3.0 |
| 18 — Durable HITL | 2.1.0 | 22 — Local runtime DX | 2.4.0 |
| 19 — Capability security & secrets | 2.5.0 | — | — |

### Runtime convergence map

Each upcoming sprint advances one convergent runtime, mapped to the
conceptual model in [`docs/primitives.md`](docs/primitives.md):

| Sprint | Advances | Ontology concept |
|---|---|---|
| 14b — Vision alignment | Code, docs & metadata speak one vocabulary | Convergence (naming) |
| 15 — Design System & CSS | Semantic UI is token-driven, polished, professional by default | Convergence (presentation) |
| L1–L5 — Less-Code | Apps shrink 5×; config-driven AI, ORM, chat primitives | Convergence (DX) |
| 16 — Memory | Durable, queryable entity recall | State (+ Entity) |
| 17 — Agents as durable entities | Identity + state + history for agents | Entity, Identity |
| 18 — Durable HITL | Human approval survives restart | Execution, Constraint |
| 19 — Capability security | No ambient authority; secrets never leak | Capability, Effect, Constraint |
| 20 — Observability | One trace identity end-to-end | Telemetry |
| 21 — Protocol schemas | Stable semantic boundary for all entities | Identity, Event, Relationship |
| 22 — Local runtime DX | The whole runtime boots as one thing | Convergence (all) |

---

## HOW TO WORK (Sprint Protocol)

Repeat for every sprint:

> **AI coding agents:** Read [`AGENTS.md`](AGENTS.md) and
> [`.github/copilot-instructions.md`](.github/copilot-instructions.md) first.
> Use the [`implement-sprint`](.github/skills/implement-sprint/SKILL.md) skill
> for structured sprint implementation. Read the relevant
> [instruction files](.github/instructions/) before touching each domain.

1. **Resume.** Find the **first sprint whose status is not `DONE`** in this file.
   That is the resume point after any interruption — no other context needed.
2. **Branch.** `git checkout main && git pull && git checkout -b feat/sprint-N`.
3. **Implement only the checked scope boxes** for that sprint. Do not start the
   next sprint's scope. Follow the sprint's "Files" + "Tests" bullets.
4. **Quality gate** (must be green before anything else):
   ```bash
   just format && just lint && just test
   uv run mypy src/voodoo          # type check (not in `just lint`, still required)
   ```
5. **Public API.** If exports change, update `tests/test_contract_api.py`
   deliberately (breaking `__all__` without a major bump is not allowed).
6. **Docs** (mandatory, see `.github/instructions/pull-request.instructions.md`):
   tick scope boxes + set `Status` + fill `Released as` here; add the release
   entry to `CHANGELOG.md`; update `docs/*.md`, `README.md`, `ROADMAP.md`,
   `ARCHITECTURE.md` per the source-path-to-doc mapping.
7. **Commit + push + PR** (Conventional Commits):
   ```bash
   git add -A && git commit -m "feat(scope): Sprint N — <name>"
   git push -u origin feat/sprint-N
   gh pr create --title "feat(scope): Sprint N — <name>" --body "$(cat .github/PULL_REQUEST_TEMPLATE.md)"
   ```
8. **Merge.** Wait for CI green, then squash-merge. `enforce_admins` is `false`
   (sole owner), so the owner merges their own PR with `--admin`:
   ```bash
   gh pr merge N --squash --delete-branch --admin
   ```
9. **Release** (workflow auto-bumps `__version__`, tags `vX.Y.Z`, publishes
   PyPI + Homebrew + GitHub Release — do NOT edit `__version__` manually):
   ```bash
   just release X.Y.Z                        # → gh workflow run release.yml
   gh run watch --workflow=release.yml
   ```
10. **Verify.** Confirm PyPI (`pip index versions voodoo-framework`), Homebrew
    formula, and the GitHub Release `vX.Y.Z` all show the new version.
11. **Close out.** Mark the sprint `DONE` in this file, `git commit -m "docs(sprint):
    mark Sprint N as DONE"`, push, then move to the next sprint.

### Rules

- **Release only complete features.** A sprint ships only when its scope is
  fully wired (no half-enabled flags, no dead settings). If scope balloons,
  split the sprint and re-plan the version numbers below it.
- **No giant rewrites.** Preserve existing primitives (engine, mesh, MCP,
  agents, auth, UI). Refactor incrementally behind interfaces.
- **Every durability claim needs a failure-path test** (worker crash, restart,
  lease expiry, duplicate delivery — ROADMAP §53).
- **Local dev stays zero-infra** (SQLite + local FS). No new required
  dependencies in the default install. Provider SDKs live in optional extras.
- Versioning: minor bump per feature sprint; patch for follow-up fixes;
  major (`2.0.0`) only at Sprint 18 (authority/secrets behavior shift).

### Status legend

```
DONE  |  WIP  |  TODO
```

---

## MILESTONE OVERVIEW

| # | Sprint | Version | Delivers | Status |
|---|--------|---------|----------|--------|
| 1 | Storage core & migrations | 1.3.0 | VoodooDatabase + SQLite + migration runner | DONE |
| 2 | Durable task queue | 1.4.0 | SQLite queue: claim/lease/retry — tasks survive restart | DONE |
| 3 | Durable executions | 1.5.0 | SQLite ExecutionStore + execution event journal | DONE |
| 4 | Checkpoints & resume | 1.6.0 | Resume waiting/unfinished executions after restart | DONE |
| 5 | Durable scheduler | 1.7.0 | schedule.at/after/every/cron backed by SQLite | DONE |
| 6 | Object store & artifacts | 1.8.0 | VoodooObjectStore + provenance records | DONE |
| 7 | EventBus protocol | 1.9.0 | Event envelope + durable SQLite bus, mesh unified | DONE |
| 8 | Adapter contracts | 1.10.0 | Capability declarations + portability test suite | DONE |
| 9 | Runtime configuration | 1.11.0 | `voodoo.yaml` selects providers | DONE |
| 10 | PostgreSQL database | 1.12.0 | Postgres adapter, same logical model + migrations | DONE |
| 11 | PostgreSQL queue & events | 1.13.0 | SKIP LOCKED queue + event store on PG | DONE |
| 12 | S3/R2 object store | 1.14.0 | Presign, checksums, multipart; `s3` extra | DONE |
| 13 | Redis adapters (optional) | 1.15.0 | Redis queue/cache behind contracts | DONE |
| 14 | ModelProvider protocol | 1.16.0 | Model descriptors + routing aliases + contract tests | DONE |
| 14b | Runtime vision alignment | 1.16.1 | Naming/docstring alignment — no behavior change | DONE |
| 15 | Voodoo Design System & CSS | 1.17.0 | Polished default: layout parity, base reset, full component CSS, light/dark/system | DONE |
| — | Primary token & design patch | 1.17.1 | Dark-mode primary invert, focus-ring/link visibility fix | DONE |
| — | Chrome components & themes | 1.18.0 | Navbar/Hero/ThemeToggle, ember-paper preset, shareable `theme.json` | DONE |
| L1 | Less-code: native tool calling | 1.19.0 | `ToolCall` protocol; OpenAI/Anthropic native parsing | DONE |
| L2 | Less-code: config-driven AI + multi-turn | 1.19.0 | `[ai]` block, `Agent(history=)`, `run_api_through_runtime` flag | DONE |
| L3 | Less-code: ORM query API + FK cascades | 1.19.0 | `Model.where/order_by/limit/first/count/delete_where`, `FK[...]` | DONE |
| L4 | Less-code: UI/realtime foundation | 1.19.0 | Icon/Markdown/chat primitives, reactive wiring, client SDK | DONE |
| L5 | Less-code: ai-agent template rewrite | 1.19.0 | 285-line single-file chat app; 0 CSS / 0 JS / 0 provider class | DONE |
| — | Chat layout fix | 1.19.1 | Chat app-shell CSS fix, top-level `Html` export | DONE |
| 16 | Memory capability | 1.20.0 | Layered memory: search/read/write, SQLite default | TODO |
| 17 | Agents as durable entities | 2.0.0 | Agent registry; runs are executions; CLI | TODO |
| 18 | Durable human-in-the-loop | 2.1.0 | WAITING_FOR_HUMAN survives restart, no live worker | TODO |
| 19 | Capability security & secrets | 2.2.0 | secrets.get, redaction, no ambient authority | TODO |
| 20 | Observability | 2.3.0 | Execution-aware tracing, `voodoo status/workers` | TODO |
| 21 | Protocol schemas & versioning | 2.4.0 | `voodoo.protocol`, schema_version everywhere | TODO |
| 22 | Local runtime DX | 2.5.0 | `voodoo create` + `voodoo dev` boot the full local runtime | TODO |

Spec §52 "Definition of Done — Durable Runtime" is achieved after Sprint 6.
"Moderate production = PostgreSQL + S3/R2" (§7) is achieved after Sprint 12.

---

# MILESTONE L — "LESS-CODE" INITIATIVE (productized 2026-08)

A template review (`voodoo-templates/ai-agent`) showed apps hand-rolling
~1,850 lines (provider adapters, chat CSS/JS, raw SQL) for patterns that
belong in the runtime. Sprints L1–L5 turned those into primitives. The
rewritten template (the acceptance test) is one 285-line Python file with
zero hand-written CSS, zero inline JS, and zero custom provider classes.

- **L1 — Native tool calling**: `ToolCall` dataclass +
  `ProviderResponse.tool_calls`; OpenAI `complete()`/`stream()` parse native
  tool calls (delta accumulation); Anthropic parses `tool_use`; the agent
  builds native follow-up messages (`tool_call_id` echo). `[TOOL:]` markers
  remain as the mock-only fallback.
- **L2 — Config-driven AI + multi-turn**: `[ai]` block (provider, model,
  base_url, api_key, aliases) + `VOODOO_AI_*` env fallbacks; any
  OpenAI-compatible endpoint with zero provider code; `Agent()` defaults to
  the configured model; `Agent.run/stream(..., history=[...])` multi-turn;
  `runtime.run_api_through_runtime` flag replaces the module-level hack.
- **L3 — ORM query API**: lazy chainable `Query` from `Model.where(**f)`
  (order_by/limit/offset/first/count/delete); `FK[Parent]` annotations with
  cascade deletes; guard against unconditional `delete()`.
- **L4 — UI/realtime**: curated `Icon` set; safe `Markdown` renderer;
  `MessageList`/`ChatMessage`/`StreamingText`/`Composer`/`Sidebar`; `vd-*`
  design-system CSS for all of them; `StateRenderer.bind(cells=...)` now
  auto-schedules re-renders on `State.set()`; client SDK gains
  navigate/scrollToBottom/onEnter + auto chat behaviors after each patch.
- **L5 — Template rewrite**: `main.py` only — config-driven provider,
  multi-turn replay, ORM queries + `FK` cascade, chat components, `@event`
  handlers. Verified end-to-end over WebSocket (agent run → persistence →
  DOM patches).

---

# MILESTONE A — DURABLE LOCAL RUNTIME (zero infra)

## Sprint 1 — Storage core & migrations
**Version 1.3.0 · Spec §11, §38, §48 · Status: DONE · Released as: 1.3.0**

Goal: one internal database layer the whole runtime persists through, with
real migrations (today: create-if-absent DDL only).

Scope:
- [x] Convert `src/voodoo/storage.py` → `src/voodoo/storage/` package;
      re-export `StorageManager` from `storage/__init__.py` (import-compat).
- [x] `VoodooDatabase` interface (Protocol): connection lifecycle, migration
      runner, transaction helper.
- [x] `SQLiteDatabase` implementation: WAL mode, single async connection
      (mirror current `data/base.py` behavior), `schema_version` table,
      ordered migration list.
- [x] Rebase `voodoo.data.init_db` on `SQLiteDatabase`; user-model DDL becomes
      migration 0001 (existing DBs keep working via create-if-absent check).
- [x] `tests/contracts/test_database.py` — `DatabaseContractTests` mixin
      (create/migrate/read/write/transaction), run against SQLite.

Done when: `init_db` goes through the new layer, migrations run idempotently
on fresh and existing DBs, contract tests green, full suite green.

## Sprint 2 — Durable task queue
**Version 1.4.0 · Spec §12, §26, §37.7 · Status: DONE · Released as: 1.4.0**

Goal: background tasks survive process restarts. Replaces `asyncio.Queue` as
source of truth (§37.7).

Scope:
- [x] `VoodooQueue` interface: `enqueue`, `claim`, `heartbeat`, `complete`,
      `fail`, `release_expired`, `stats`; capability declaration
      (`at_least_once`, visibility/lease timeout, delayed delivery, priority).
- [x] `SQLiteQueue`: `tasks` table per §12 (id, type, payload, status,
      priority, available_at, attempts, max_attempts, locked_by, locked_at,
      lease_until, last_error, idempotency_key) with **transactional atomic
      claim** and lease expiry reclaim.
- [x] Lifecycle: `PENDING → RUNNING → COMPLETED | RETRYING | FAILED`
      with exponential backoff via `available_at`.
- [x] Rework `workers/queue.py`: workers poll/claim from the durable queue;
      keep in-memory queue available as explicit `provider: memory` choice.
- [x] `@task`/`.enqueue()` and `voodoo dev` lifespan wire the durable queue by
      default (`.voodoo/state/data.db`).
- [x] Failure-path tests: worker crash → lease expiry → reclaim by second
      worker; duplicate delivery honors `idempotency_key`; retries respect
      `max_attempts`.
- [x] CLI: `voodoo tasks` (list + statuses), `voodoo tasks retry <id>`.
- [x] `tests/contracts/test_queue.py` — `QueueContractTests` mixin.

Done when: kill -9 the worker mid-task, restart, task completes exactly-once
*effect* with at-least-once delivery visible in tests.

## Sprint 3 — Durable executions
**Version 1.5.0 · Spec §13, §39 (persistence.py → ExecutionStore) · Status: DONE · Released as: 1.5.0**

Goal: executions live in SQLite (journal + materialized state), replacing
JSONL as the default store.

Scope:
- [x] `executions` table (materialized state, per §4 Layer 3 fields) and
      `execution_events` append-only journal (sequence, execution_id,
      event_type, payload, timestamp).
- [x] Journal event types: `execution.created/started/completed/failed`,
      `step.started`, `state.changed`, `task.scheduled`,
      `execution.waiting` (full set lands in Sprint 4).
- [x] `SQLiteExecutionStore` implementing the existing `ExecutionStore`
      protocol + journal append; becomes the engine default when a DB path
      exists.
- [x] `JSONFileExecutionStore` stays as reader for one-time migration of
      existing `.voodoo/executions.jsonl` (import command).
- [x] `engine.recover()` reads SQLite; unfinished executions restored with
      journal history intact.
- [x] Telemetry/`inspect` read from the store, not engine memory.
- [x] CLI: `voodoo executions`, `voodoo execution <id>` (timeline from
      journal), `voodoo events`; `voodoo recover` uses SQLite by default.
- [x] Persistence failures are **never silently swallowed** (log + raise
      surface per §51.16).

Done when: restart the process mid-workflow and `voodoo execution <id>` shows
the full history; JSONL import works; failure tests green.

## Sprint 4 — Checkpoints & resume
**Version 1.6.0 · Spec §14, §30 (resumability), §50 · Status: DONE · Released as: 1.6.0**

Goal: an interrupted execution can resume from a durable checkpoint (spec gap
#3).

Scope:
- [x] Checkpoint writes at meaningful boundaries: after model completion,
      tool completion, state mutation, task scheduling, before waiting
      (engine hooks already exist — extend `_persist`).
- [x] Durable representation of resumable work: JSON-serializable state,
      object refs, deterministic ids (never live Python objects — §14).
- [x] Recovery flow: on restart, unfinished `running` executions → `waiting`
      (recoverable) or re-driven from last checkpoint for task-based
      workflows (pending-work reconstruction).
- [x] Waiting executions: pending `Approval` records persisted (not just
      rebuilt in memory), decisions recorded as journal events.
- [x] Effects recorded in the journal carry `idempotency_key` so a resumed
      execution does not blindly re-run non-idempotent effects (§15).
- [x] Tests: crash between steps → resume skips completed steps; duplicate
      resume attempts are safe; checkpoint payload stays JSON-compatible.

Done when: a workflow interrupted by process kill resumes and completes
without re-executing finished steps.

## Sprint 5 — Durable scheduler
**Version 1.7.0 · Spec §25, TimeSpec gap · Status: DONE · Released as: 1.7.0**

Goal: schedules are durable runtime primitives, not Python loops.

Scope:
- [x] `schedules` table: id, name, kind (`at` | `after` | `interval` | `cron`),
      spec, next_run_at, last_run_at, task_type, payload, active.
- [x] Scheduler service in the app lifespan: tick loop claims due schedules
      transactionally and **enqueues durable tasks** (Sprint 2).
- [x] Consume `TimeSpec.schedule` / `TimeSpec.interval` from
      `primitives/time.py` (currently dead fields).
- [x] Cron parsing (minimal 5-field subset is acceptable; document it).
- [x] Missed-run policy on restart (run-once catch-up, documented).
- [x] Tests: schedule survives restart; duplicate scheduler instances don't
      double-fire (claim is transactional); `at`/`after` fire once.
- [x] CLI: `voodoo schedules` (list/inspect), pause/resume.

Done when: schedule `every 5s` → kill process → restart → exactly one task
per due tick, none lost, none duplicated beyond catch-up policy.

## Sprint 6 — Object store & artifacts
**Version 1.8.0 · Spec §18, §46 · Status: DONE · Released as: 1.8.0**

Goal: object storage as a first-class capability with provenance (spec gap #5).

Scope:
- [x] `VoodooObjectStore` interface: `put, get, delete, exists, stat, list,
      url/presign` (where supported) + capability declaration.
- [x] `LocalObjectStore` under `.voodoo/objects/` (sharded paths); metadata
      table (object_id, bucket, key, size, content_type, checksum, metadata).
- [x] Move current S3 logic out of `StorageManager` into `S3ObjectStore`
      (behavior-compatible); `StorageManager` becomes a thin facade over the
      active adapter (breaking nothing).
- [x] Object references as the standard way to link large payloads from
      executions/journal (no blobs in SQLite).
- [x] Artifacts + provenance (§46): `artifacts` table (artifact_id,
      execution_id, parent_artifact_id, created_by, tool/model, timestamp,
      checksum, metadata) + `execution.artifact()` helper.
- [x] `tests/contracts/test_objectstore.py` — `ObjectStoreContractTests`.
- [x] CLI: `voodoo objects list/get`, `voodoo artifacts <execution_id>`.

Done when: agent/tool outputs can be stored as artifacts and reproduced with
full provenance from `voodoo artifacts`.

## Sprint 7 — EventBus protocol & mesh unification
**Version 1.9.0 · Spec §16, §17 · Status: DONE · Released as: 1.9.0**

Goal: explicit Event semantics; mesh sits on top of the bus instead of being
its own subsystem (spec gap #4).

Scope:
- [x] Event envelope per §17: event_id, event_type, timestamp, source,
      subject, correlation_id, causation_id, payload, schema_version.
- [x] `VoodooEventBus` interface: `publish`, `subscribe`, `replay` (where
      supported) + capability declaration.
- [x] `LocalEventBus` (in-process; today's mesh behavior) and
      `SQLiteEventBus` (durable event log, replayable subscriptions).
- [x] `mesh` refactored to publish/subscribe through the active bus; WS
      remote mesh and `expose()` unchanged externally; handler execution still
      flows through the engine.
- [x] Correlation/causation ids propagated from `ExecutionContext` → events
      (trace linkage end-to-end).
- [x] Events ≠ tasks ≠ commands documented and enforced by naming rules
      (dotted event types, §16).
- [x] `tests/contracts/test_eventbus.py` — `EventBusContractTests`
      (publish/subscribe/replay/no-lost-subscriber-on-error).

Done when: publish an event, restart the process, replay delivers it to a
late subscriber; mesh tests unchanged (public behavior preserved).

---

# MILESTONE B — PROTOCOL & CONFIGURATION

## Sprint 8 — Adapter contracts & capability negotiation
**Version 1.10.0 · Spec §9, §10, §29 · Status: DONE · Released as: 1.10.0**

Goal: providers declare what they guarantee; the runtime never silently
violates correctness.

Scope:
- [x] `AdapterCapabilities` model: durability, ordering, delivery, delayed,
      priority, transactions, visibility timeout, replay…
- [x] Every adapter from Sprints 1–7 declares capabilities via
      `.capabilities()`.
- [x] Runtime negotiation: emulate when safe / reject unsupported required
      ops with explicit errors / degrade loudly (§10).
- [x] Consolidate `tests/contracts/` into the portability suite; CI runs the
      same mixins against every registered adapter.
- [x] `voodoo doctor` prints active providers + their capability matrix.

Done when: asking the memory queue for delayed delivery raises an explicit
"unsupported by provider" error, and the same contract suite passes for every
adapter.

## Sprint 9 — Runtime configuration
**Version 1.11.0 · Spec §31, §28 · Status: DONE · Released as: 1.11.0**

Goal: infrastructure is selected by configuration, never by code changes.

Scope:
- [x] `voodoo.yaml` (+ env interpolation `${VAR}`): `database`, `queue`,
      `events`, `objects`, `cache`, `models` provider blocks; default file =
      all-local, zero-config behavior identical to today.
- [x] Provider registry mapping names → adapters (Sprints 1–7 implementations
      registered).
- [x] Precedence: explicit config > env vars (`VOODOO_QUEUE_PROVIDER`, …) >
      local defaults.
- [x] Validation with actionable errors; `voodoo doctor` prints resolved
      config.
- [x] Docs: local → production → later migration paths (§28 table).

Done when: switching `queue: sqlite` → `queue: memory` in `voodoo.yaml`
changes behavior with zero application-code edits, verified by tests running
the same app against two providers.

---

# MILESTONE C — PRODUCTION PROVIDERS (optional installs)

## Sprint 10 — PostgreSQL database adapter
**Version 1.12.0 · Spec §7, §11 · Status: DONE · Released as: 1.12.0**

Scope:
- [x] `PostgresDatabase` (async psycopg) with the same migration list
      translated to PG DDL; `[postgres]` extra; config: `database.provider:
      postgres` + url.
- [x] `DatabaseContractTests` green against PG (CI: GitHub Actions service
      container).
- [x] JSONB payload columns where SQLite uses TEXT JSON.
- [x] Document connection pooling choices (§49) without over-engineering.

> Note: `[postgres]` extra is installed only for tests (dev extra); local runs
> skip PG contract tests (`VOODOO_TEST_DATABASE_URL` unset); CI runs them
> against a `postgres:16` service container. JSONB is documented as `TEXT`-JSON
> parity for now (revisit when queue/events stores rewire in Sprint 11).

## Sprint 11 — PostgreSQL queue & events
**Version 1.13.0 · Spec §12 (SKIP LOCKED), §7 · Status: DONE · Released as: 1.13.0**

Scope:
- [x] `PostgresQueue` with `FOR UPDATE SKIP LOCKED` transactional claim +
      leases (same semantics as SQLiteQueue).
- [x] `PostgresEventStore` (durable publish/replay).
- [x] `QueueContractTests` + `EventBusContractTests` green on PG.
- [x] Execution store on PG (executions/journal/artifacts tables via the
      migration runner).
- [x] Failure-path tests against PG in CI (lease expiry, duplicate claim).
- ⭐ After this sprint: moderate production = PostgreSQL only (+ objects).

## Sprint 12 — S3/R2 object store hardening
**Version 1.14.0 · Spec §18 · Status: DONE · Released as: 1.14.0**

Scope:
- [x] Declare `boto3` under `[s3]` extra (currently an undeclared import).
- [x] Presigned GET/PUT, SHA-256 checksums, content-type, metadata.
- [x] Multipart upload above a size threshold; R2 endpoint compatibility
      tests (integration-gated).
- [x] `ObjectStoreContractTests` green against S3-compatible endpoint in CI
      (MinIO container), local suite unaffected.

## Sprint 13 — Redis adapters (optional)
**Version 1.15.0 · Spec §8, §34 · Status: DONE · Released as: 1.15.0**

Scope:
- [x] `[redis]` extra; `RedisQueue` (streams + consumer groups or lists with
      LMOVE) and `RedisCache`.
- [x] Contract tests green; capability declaration honest (ordering,
      redelivery semantics).
- [x] Explicitly optional: nothing in the default path imports redis.

---

# MILESTONE D — AI RUNTIME

## Sprint 14 — ModelProvider protocol
**Version 1.16.0 · ROADMAP §64, §47 · Status: DONE · Released as: 1.16.0**

Goal: models are providers behind one normalized interface (spec gap #7).

Scope:
- [x] `VoodooModelProvider` interface: `generate`, `stream`, `embed`,
      `count_tokens` (optional), `describe()`.
- [x] Model descriptors: provider, model, modalities, context_window,
      tool_use, structured_output, streaming, reasoning, vision, audio,
      embeddings, pricing metadata.
- [x] Routing aliases `best|fast|cheap|vision|reasoning` resolved by the
      runtime from config + descriptors.
- [x] Existing OpenAI/Anthropic/Gemini/Ollama/Mock providers conform; agent
      `model="provider:model"` resolution goes through the registry.
- [x] `voodoo generate` stops bypassing the abstraction (known debt).
- [x] `tests/contracts/test_model_provider.py` — `ModelProviderContractTests`
      (Mock provider in default suite; live providers integration-gated).
- [x] Model calls journaled (`model.called`/`model.completed`) for Sprint 4
      checkpoints.

## Sprint 14b — Runtime vision alignment
**Version 1.16.1 · ROADMAP §67 · Status: DONE · Released as: 1.16.1**

- **Goal:** Align code docstrings, flow diagrams, and package metadata with the
  "programmable runtime" vision already established in the docs.
- **Why:** The docs were reframed around one ontology
  (Entity → State → Intent → Capability → Execution → Effect → State), but code
  docstrings and package metadata still read "AI-native framework" and depict the
  pre-Execution flow (`COMPUTE → EFFECT`). Code and docs must speak one language.
- **Current State:** README, ROADMAP, ARCHITECTURE, `docs/primitives.md`, and
  `docs/execution-model.md` use the new ontology; code docstrings/flow diagrams
  and `pyproject.toml` / `release.yml` still use the old framing.
- **Changes:**
  - [x] Replace `STATE → INTENT → CAPABILITY → COMPUTE → EFFECT → STATE` with
        `ENTITY → STATE → INTENT → CAPABILITY → EXECUTION → EFFECT → STATE` in
        `src/voodoo/__init__.py`, `src/voodoo/primitives/__init__.py`,
        `src/voodoo/runtime/__init__.py`, `src/voodoo/runtime/workflow.py`,
        and `tests/test_primitives.py`.
  - [x] Rewrite "eight architectural primitives" → "computational model" in
        `src/voodoo/runtime/__init__.py`; "AI-native application framework" →
        "programmable runtime" in `src/voodoo/__init__.py`.
  - [x] Align `src/voodoo/runtime/task.py` ("runtime primitives" → "computational
        model") and `src/voodoo/primitives/compute.py` ("one class of Compute" →
        "one form of Compute").
  - [x] Update `pyproject.toml` `description` and `release.yml` Homebrew `desc`
        to the programmable-runtime framing.
- **Dependencies:** None (documentation/metadata only).
- **Acceptance Criteria:** No `AI-native framework`, `COMPUTE → EFFECT`, or
  `eight primitives` wording remains in code docstrings or package metadata;
  zero behavior change (full test suite unchanged).
- **Tests:** `tests/test_primitives.py` docstring only (no logic change).
- **Documentation:** `CHANGELOG.md` under `[Unreleased]`.
- **Definition of Done:** quality gate green + released `1.16.1`.

## Sprint 15 — Voodoo Design System & CSS
**Version 1.17.0 · ROADMAP §45, §46 · Status: DONE · Released as: 1.17.0**

> **Cross-cutting presentation sprint.** Ships before the remaining AI-runtime
> work so every new surface (agents, HITL, observability) renders on a polished
> default UI instead of the current unpolished CSS.

- **Goal:** Make the default Voodoo CSS path produce polished, professional
  interfaces out of the box — every semantic layout and component prop renders,
  backed by a base reset, full component CSS coverage, and light/dark/system
  theming.
- **Why:** `voodoo new` currently scaffolds apps that render broken layouts and
  unpolished components. The default `VoodooCSSAdapter` drops layout props
  (`gap`, `direction`, `justify`, `items`, `wrap`, `cols`, container/page
  sizes), `generate_component_css()` covers only a subset of the library, and
  there is no base reset — so the "terrible default" is structural, not a
  matter of taste.
- **Current State:** The component model (Sprints S2/DS) declares semantic props
  but the default adapter ignores them; only the Tailwind adapter maps them
  (and it is the only tested path). `docs/design_system.md` holds a strong
  MUI-inspired vision (tokens → CSS variables → semantic components → adapters)
  that is only partially implemented.
- **Changes:**
  - [x] **Layout parity** — map `direction`, `gap`, `justify`, `items`, `wrap`,
        `cols`, `size`, `pad`, `centered` to `vd-*` modifier classes in
        `VoodooCSSAdapter.component_classes()` and add matching rules in
        `generate_component_css()`. `Stack` must render a vertical layout with
        its declared `gap` by default; `Grid(cols=…)` must emit real columns.
  - [x] **Base reset & typography** — ship a minimal reset (`box-sizing:
        border-box`, `margin: 0` on `body`/headings/paragraphs, body
        `line-height`, antialiasing, `img { display: block; max-width: 100% }`)
        and apply the `--vd-*` type scale to `Text`/`Heading`/`Paragraph` so
        browser defaults stop leaking through.
  - [x] **Full component CSS coverage** — complete `generate_component_css` for
        every library component (Paragraph, Form, Nav, Header, Footer, Main,
        Section, Article, Aside, Figure, FigCaption, Address, Time, Img,
        ListItem, Option, Table base, Dialog/Modal backdrop) with consistent
        tokens, focus-visible rings, hover/active/disabled states, and motion
        tokens.
  - [x] **Remove hardcoded Tailwind classes** — `_auth_field`, `LoginForm`, and
        `RegisterForm` must use semantic components/tokens; `space-y-*`,
        `text-center mb-*` are no-ops under the default adapter.
  - [x] **Light/dark/system modes** — honor `theme.mode` via `:root`/`.dark`/
        `prefers-color-scheme`; drop the forced `class="dark dark"`; expose a
        runtime toggle (`voodoo.set_theme` / `data-theme` attribute).
  - [x] **Interactive polish** — consistent focus-visible rings, hover/active/
        disabled transitions, and spacing/typography rhythm across Button,
        Input, Select, Checkbox, Radio, Link, Badge, Card, Dialog, Modal.
  - [x] **Scaffold showcase** — update the `voodoo new` offline scaffold
        (`cli/new.py`) and `examples/hello_world` to demonstrate the polished
        default using semantic props only.
- **Dependencies:** None (presentation layer only; no runtime/storage impact).
- **Acceptance Criteria:** a freshly scaffolded `voodoo new` app renders a
  clean, professional page with correct gap/direction/columns and no browser
  default leakage; every semantic prop maps to a class *and* a generated CSS
  rule; no Tailwind utility classes remain inside `src/voodoo/ui/library.py`;
  `theme.mode` light/dark/system all render correctly.
- **Tests:** golden render tests for the `VoodooCSSAdapter` path (layout
  classes emitted); a parity test asserting each semantic prop produces a class
  with a matching generated CSS rule; a test asserting no `space-y-*`/Tailwind
  utilities in the library; `to_css_variables()`/`generate_component_css()`
  contain the reset + all component rules; mode variants. Update
  `tests/test_ui.py`, add `tests/test_design_system.py`.
- **Documentation:** rewrite `docs/design_system.md` (brainstorm → reference);
  update `docs/components.md` and `docs/routing.md` (scaffold example) if
  affected; `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `1.17.0`.

## Sprint 16 — Memory as entity state
**Version 1.20.0 · ROADMAP §28, §26 · Status: DONE · Released as: —**

- **Goal:** Give entities durable, queryable memory so their state survives and
  can be recalled — working, episodic, and semantic.
- **Why:** An entity with only one-shot state cannot reason over its own
  history; operational systems need recall derived from what actually happened.
- **Current State:** The execution journal already records what happened
  (Sprint 3); `State` is versionable, but there is no memory surface.
- **Changes:**
  - [ ] Layered interfaces: working / execution / durable / semantic / episodic
        memory with `memory.search() | read() | write()`.
  - [ ] Default backend: SQLite (+ FTS5 for semantic search — no new deps).
  - [ ] Execution memory: journal-derived episodic records (what the execution
        observed/did) written automatically.
  - [ ] Agent API: `agent.memory` wired; context ≠ memory distinction kept.
  - [ ] pgvector/external backends listed as future adapters only (not built).
- **Dependencies:** Sprint 3 (execution journal), Sprint 14 (model provider,
  optional for embeddings).
- **Acceptance Criteria:** memory reads/writes/search work; execution memory is
  written automatically; no vector-database mandate in the default path.
- **Tests:** memory CRUD contract; episodic records derived from journal;
  memory survives restart.
- **Documentation:** `docs/data.md`, `docs/agents.md`, `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `1.20.0`.

## Sprint 17 — Agents as durable entities
**Version 2.0.0 · ROADMAP §47 · Status: DONE · Released as: 2.0.0**

- **Goal:** Agents become durable entities — stable identity, capabilities,
  state, and queryable execution history.
- **Why:** Agents are the canonical entity. Without a registry they exist only
  in process memory, which violates the entity model.
- **Current State:** An agent run already creates an Execution, but there is no
  agent registry, identity, or persisted state.
- **Changes:**
  - [x] `agents` registry table: identity, capabilities, model policy, tools,
        permissions, configuration, state.
  - [x] An agent run always creates an Execution (already true) **and** persists
        agent state/history links (execution history queryable per agent).
  - [x] Multi-agent interaction via existing primitives only (events/tasks/
        executions) — no bespoke agent RPC (ROADMAP §47); parent/child executions
        keep trace relationships.
  - [x] CLI: `voodoo agents`, `voodoo agent <id>` (history, state, runs).
- **Dependencies:** Sprint 3 (executions), Sprint 14 (model provider).
- **Acceptance Criteria:** an agent survives restart with identity, state, and
  history intact; two agents collaborating via events produce linked executions.
- **Tests:** restart survival (registry + state); multi-agent collaboration
  produces linked, parented executions.
- **Documentation:** `docs/agents.md`, `docs/execution-model.md`, `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `2.0.0`.

## Sprint 18 — Durable human-in-the-loop
**Version 2.1.0 · ROADMAP §50 · Status: DONE · Released as: 2.1.0**

- **Goal:** Human approval is an execution state that survives process death;
  a decision resumes the execution on any worker.
- **Why:** Human intervention is not a live callback — it is a waiting
  Execution. Today approvals recover as decidable-but-not-rerunnable.
- **Current State:** Approvals persist but cannot resume the original work
  after the worker process dies.
- **Changes:**
  - [x] `WAITING_FOR_HUMAN` executions persist resumable intent/compute
        (registered participants serialized durably — leverages Sprint 4).
  - [x] Approval decision → event → execution resumes on any worker.
  - [x] `approvals` durable registry; journal events
        `approval.requested/granted/denied`.
  - [x] CLI: `voodoo approvals` list, `voodoo approvals approve/deny <id>`.
- **Dependencies:** Sprints 3–4 (executions + checkpoints), Sprint 11 (optional
  PG).
- **Acceptance Criteria:** request approval → kill process → decide via CLI →
  execution resumes and completes with the correct result.
- **Tests:** crash/restart human-in-the-loop path; decisions recorded as
  durable events.
- **Documentation:** `docs/hitl.md`, `docs/execution-model.md`, `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `2.1.0`.

## Sprint 19 — Capability security & secrets
**Version 2.2.0 · ROADMAP §55, §70 · Status: TODO · Released as: —**

- **Goal:** No ambient authority. Capabilities gate effects; secrets never
  leak into observability.
- **Why:** Capabilities must be explicit, revocable, and enforced; the major
  bump reflects the authority behavior shift.
- **Current State:** Capabilities exist but authority is implicit; secrets have
  no central redaction.
- **Changes:**
  - [ ] `secrets.get(name)` interface: env/local-default backend; encrypted
        local store option; provider managers are future adapters.
  - [ ] Redaction guard: secrets never persisted into events/journal/telemetry
        (ROADMAP §55) — enforced centrally.
  - [ ] Effect authorization context: actor, principal, capability, resource,
        scope recorded on every effect (ROADMAP §55).
  - [ ] Sensitive capabilities (`filesystem.write`, `network.request`,
        `shell.execute`, `secrets.read`, `payment.execute`, `email.send`)
        require explicit grants — no ambient authority by default.
  - [ ] Migration note + upgrade guide for existing agents (CHANGELOG + docs).
- **Dependencies:** Sprint 8 (capability negotiation), Sprint 17 (agent
  entities).
- **Acceptance Criteria:** denied-by-default matrix holds; secrets are redacted
  from events/journal/telemetry.
- **Tests:** denied-by-default matrix; redaction of known secret patterns.
- **Documentation:** `docs/auth.md`, `docs/security`, upgrade guide,
  `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `2.2.0`.

---

# MILESTONE E — PROTOCOL STABILITY & DX

## Sprint 20 — Observability
**Version 2.3.0 · ROADMAP §54 · Status: TODO · Released as: —**

- **Goal:** One trace identity propagates through execution, task, worker,
  model, tool, event, and object operation.
- **Why:** Telemetry is the sensory system of the runtime; today there are two
  contextvar chains instead of one.
- **Current State:** Correlation IDs exist but are split across subsystems.
- **Changes:**
  - [ ] Trace/correlation identity on: execution, task, worker, model call,
        tool call, event, object op (single contextvar chain, today: two).
  - [ ] OpenTelemetry-compatible span model; optional OTLP export behind
        `[otel]` extra (in-memory store remains default).
  - [ ] CLI: `voodoo status`, `voodoo workers`, upgraded `voodoo doctor`
        (providers, capabilities, migrations, queue depth, schedule health).
  - [ ] Telemetry summaries persisted (rolling) so `voodoo status` works after
        restart.
- **Dependencies:** Sprint 3 (executions), Sprint 17 (entities).
- **Acceptance Criteria:** `trace_id` propagates end-to-end; `voodoo status`
  works after restart.
- **Tests:** trace propagation across the full chain; status persistence.
- **Documentation:** `docs/telemetry.md`, `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `2.3.0`.

## Sprint 21 — Protocol schemas & versioning
**Version 2.4.0 · ROADMAP §56, §57 · Status: TODO · Released as: —**

- **Goal:** Canonical entity schemas form the stable semantic boundary for
  other languages and SDKs.
- **Why:** A programmable runtime needs a stable protocol boundary so
  Identity, Event, and Relationship survive across processes and languages.
- **Current State:** Entity schemas are implicit in code, not declared.
- **Changes:**
  - [ ] `voodoo.protocol` package: canonical entity schemas (identity,
        capabilities, intents, executions, tasks, events, objects, errors)
        as the stable semantic boundary.
  - [ ] `schema_version` on every persisted record + envelope; versioned event
        types (`execution.completed.v1` or `schema_version: 1`).
  - [ ] JSON Schema export command (`voodoo protocol export`) for other
        languages/SDKs.
  - [ ] Compatibility policy documented (additive within major; migrations for
        stored data).
- **Dependencies:** Sprint 3 (executions), Sprint 8 (contracts), Sprint 17
  (entities).
- **Acceptance Criteria:** every entity round-trips serialize/deserialize; the
  export command emits valid schemas.
- **Tests:** protocol conformance round-trips for every entity.
- **Documentation:** `docs/mcp.md` (or a new `docs/protocol.md`),
  `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `2.4.0`.

## Sprint 22 — Local runtime DX ("WAMP for autonomous software")
**Version 2.5.0 · ROADMAP §63, §62 · Status: TODO · Released as: —**

- **Goal:** `install → create → dev` boots the whole runtime as one thing, with
  zero external infrastructure.
- **Why:** The runtime must feel like one coherent system from the first
  command; convergence must be visible, not theoretical.
- **Current State:** `voodoo new` + `voodoo dev` exist but do not boot the full
  local runtime.
- **Changes:**
  - [ ] `voodoo create <app>` (evolve `voodoo new`) scaffolds an app wired for
        the full local runtime (durable tasks, scheduler, events, objects,
        agent runtime) with a working example of each.
  - [ ] `voodoo dev` boots everything and prints a runtime banner: providers
        active, queue depth, schedules, object store path, agent runtime,
        MCP endpoint.
  - [ ] First-run experience: install → `voodoo create` → `voodoo dev` →
        working autonomous app with **zero external infrastructure** (ROADMAP §63).
  - [ ] Template includes a crash/restart demo task proving durability.
- **Dependencies:** Sprints 2–7 (the local runtime pieces).
- **Acceptance Criteria:** first-run works with zero infrastructure; the
  crash/restart demo proves durability.
- **Tests:** first-run end-to-end; durability demo.
- **Documentation:** `docs/installation.md`, `README.md`, `CHANGELOG.md`.
- **Definition of Done:** quality gate green + released `2.5.0`.

---

# BACKLOG (explicitly not scheduled — build only when justified)

- TypeScript / Go SDKs (§32) — only after Sprint 20 stabilizes schemas.
- SQS / NATS / Kafka adapters (§8) — when scale requires; contracts already
  exist after Sprints 8–11.
- GCS / Azure Blob object stores.
- External secret managers (AWS SM / GCP / Vault) as `secrets` adapters.
- pgvector / external vector memory backends.
- Distributed multi-machine workers (§34) — contracts must allow, not build.
- WebSocket/realtime event fan-out beyond current mesh WS.
- Compaction/rotation for execution journals (size management).

---

# APPENDIX — Sprint acceptance checklist (run every release)

- [ ] `just format && just lint && just test` green (incl. new failure-path
      tests for this sprint).
- [ ] Contract suite updated if `__all__` or adapter behavior changed.
- [ ] No new required runtime dependencies (optional extras only).
- [ ] Local zero-infra experience still works: fresh project, no Redis/PG/
      S3/Docker (§37).
- [ ] Worker-death invariant: nothing durable lives only in worker memory
      (§51.1–51.3).
- [ ] `CHANGELOG.md` entry written for the version.
- [ ] `SPRINT_PLAN.md` status updated (`DONE` + `Released as`).
- [ ] Released via `just release X.Y.Z`; workflow green (PyPI + Homebrew +
      GitHub Release).
