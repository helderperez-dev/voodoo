# Voodoo — Runtime & Protocol Implementation Plan (Sprint Tracker)

Source spec: [`ROADMAP.md`](ROADMAP.md) — the master architectural and
engineering plan (formerly `VOODOO_RUNTIME_PROTOCOL_ARCHITECTURE.txt`).
Historical record of the completed 1.2.0 milestone: `IMPLEMENTATION.md`.

This file is the **single source of truth** for progress. Each sprint is a
small, complete, releasable feature. Work sprints strictly in order. Each sprint
ends with a pushed commit and a released version (PyPI + Homebrew + uv via the
existing automated workflow).

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
| **Latest release** | `1.15.1` (`src/voodoo/__init__.py` → `__version__`) |
| **Sprints 1–13** | ✅ All DONE + released (v1.3.0 → v1.15.1) |
| **Next sprint** | **Sprint 14 — ModelProvider protocol → `1.16.0`** |

**Release cadence (one version per sprint, minor bump each):**

| Sprint | Version | Sprint | Version |
|--------|---------|--------|---------|
| 14 — ModelProvider protocol | 1.16.0 | 18 — Capability security & secrets | 2.0.0 |
| 15 — Memory capability | 1.17.0 | 19 — Observability | 2.1.0 |
| 16 — Agents as durable entities | 1.18.0 | 20 — Protocol schemas & versioning | 2.2.0 |
| 17 — Durable HITL | 1.19.0 | 21 — Local runtime DX | 2.3.0 |

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
| 14 | ModelProvider protocol | 1.16.0 | Model descriptors + routing aliases + contract tests | TODO |
| 15 | Memory capability | 1.17.0 | Layered memory: search/read/write, SQLite default | TODO |
| 16 | Agents as durable entities | 1.18.0 | Agent registry; runs are executions; CLI | TODO |
| 17 | Durable human-in-the-loop | 1.19.0 | WAITING_FOR_HUMAN survives restart, no live worker | TODO |
| 18 | Capability security & secrets | 2.0.0 | secrets.get, redaction, no ambient authority | TODO |
| 19 | Observability | 2.1.0 | Execution-aware tracing, `voodoo status/workers` | TODO |
| 20 | Protocol schemas & versioning | 2.2.0 | `voodoo.protocol`, schema_version everywhere | TODO |
| 21 | Local runtime DX | 2.3.0 | `voodoo create` + `voodoo dev` boot the full local runtime | TODO |

Spec §52 "Definition of Done — Durable Runtime" is achieved after Sprint 6.
"Moderate production = PostgreSQL + S3/R2" (§7) is achieved after Sprint 12.

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
**Version 1.16.0 · ROADMAP §64, §47 · Status: TODO · Released as: —**

Goal: models are providers behind one normalized interface (spec gap #7).

Scope:
- [ ] `VoodooModelProvider` interface: `generate`, `stream`, `embed`,
      `count_tokens` (optional), `describe()`.
- [ ] Model descriptors: provider, model, modalities, context_window,
      tool_use, structured_output, streaming, reasoning, vision, audio,
      embeddings, pricing metadata.
- [ ] Routing aliases `best|fast|cheap|vision|reasoning` resolved by the
      runtime from config + descriptors.
- [ ] Existing OpenAI/Anthropic/Gemini/Ollama/Mock providers conform; agent
      `model="provider:model"` resolution goes through the registry.
- [ ] `voodoo generate` stops bypassing the abstraction (known debt).
- [ ] `tests/contracts/test_model_provider.py` — `ModelProviderContractTests`
      (Mock provider in default suite; live providers integration-gated).
- [ ] Model calls journaled (`model.called`/`model.completed`) for Sprint 4
      checkpoints.

## Sprint 15 — Memory capability
**Version 1.17.0 · ROADMAP §28, §26 · Status: TODO · Released as: —**

Goal: memory semantics without a vector-database mandate.

Scope:
- [ ] Layered interfaces: working / execution / durable / semantic / episodic
      memory with `memory.search() | read() | write()`.
- [ ] Default backend: SQLite (+ FTS5 for semantic search — no new deps).
- [ ] Execution memory: journal-derived episodic records (what the execution
      observed/did) written automatically.
- [ ] Agent API: `agent.memory` wired; context ≠ memory distinction kept.
- [ ] pgvector/external backends listed as future adapters only (not built).

## Sprint 16 — Agents as durable runtime entities
**Version 1.18.0 · ROADMAP §47 · Status: TODO · Released as: —**

Scope:
- [ ] `agents` registry table: identity, capabilities, model policy, tools,
      permissions, configuration, state.
- [ ] An agent run always creates an Execution (already true) **and** persists
      agent state/history links (execution history queryable per agent).
- [ ] Multi-agent interaction via existing primitives only (events/tasks/
      executions) — no bespoke agent RPC (ROADMAP §47); parent/child executions
      keep trace relationships.
- [ ] CLI: `voodoo agents`, `voodoo agent <id>` (history, state, runs).
- [ ] Tests: agent survives restart (registry + state), two agents
      collaborating via events produce linked executions.

## Sprint 17 — Durable human-in-the-loop
**Version 1.19.0 · ROADMAP §50 · Status: TODO · Released as: —**

Goal: approvals work without the original worker process alive (today:
approvals recover as decidable-but-not-rerunnable).

Scope:
- [ ] `WAITING_FOR_HUMAN` executions persist resumable intent/compute
      (registered participants serialized durably — leverages Sprint 4).
- [ ] Approval decision → event → execution resumes on any worker.
- [ ] `approvals` durable registry; journal events
      `approval.requested/granted/denied`.
- [ ] CLI: `voodoo approvals` list, `voodoo approvals approve/deny <id>`.
- [ ] Tests: request approval → kill process → decide via CLI → resume
      completes with correct result.

## Sprint 18 — Capability security & secrets
**Version 2.0.0 · ROADMAP §55, §70 · Status: TODO · Released as: —**

Major bump: authority defaults change (agents lose ambient authority).

Scope:
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
- [ ] Tests: denied-by-default matrix; redaction of known secret patterns.

---

# MILESTONE E — PROTOCOL STABILITY & DX

## Sprint 19 — Observability
**Version 2.1.0 · ROADMAP §54 · Status: TODO · Released as: —**

Scope:
- [ ] Trace/correlation identity on: execution, task, worker, model call,
      tool call, event, object op (single contextvar chain, today: two).
- [ ] OpenTelemetry-compatible span model; optional OTLP export behind
      `[otel]` extra (in-memory store remains default).
- [ ] CLI: `voodoo status`, `voodoo workers`, upgraded `voodoo doctor`
      (providers, capabilities, migrations, queue depth, schedule health).
- [ ] Telemetry summaries persisted (rolling) so `voodoo status` works after
      restart.

## Sprint 20 — Protocol schemas & versioning
**Version 2.2.0 · ROADMAP §56, §57 · Status: TODO · Released as: —**

Scope:
- [ ] `voodoo.protocol` package: canonical entity schemas (identity,
      capabilities, intents, executions, tasks, events, objects, errors)
      as the stable semantic boundary.
- [ ] `schema_version` on every persisted record + envelope; versioned event
      types (`execution.completed.v1` or `schema_version: 1`).
- [ ] JSON Schema export command (`voodoo protocol export`) for other
      languages/SDKs.
- [ ] Compatibility policy documented (additive within major; migrations for
      stored data).
- [ ] Protocol conformance tests asserting round-trip serialize/deserialize
      for every entity.

## Sprint 21 — Local runtime DX ("WAMP for autonomous software")
**Version 2.3.0 · ROADMAP §63, §62 · Status: TODO · Released as: —**

Scope:
- [ ] `voodoo create <app>` (evolve `voodoo new`) scaffolds an app wired for
      the full local runtime (durable tasks, scheduler, events, objects,
      agent runtime) with a working example of each.
- [ ] `voodoo dev` boots everything and prints a runtime banner: providers
      active, queue depth, schedules, object store path, agent runtime,
      MCP endpoint.
- [ ] First-run experience: install → `voodoo create` → `voodoo dev` →
      working autonomous app with **zero external infrastructure** (ROADMAP §63).
- [ ] Template includes a crash/restart demo task proving durability.

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
