# Voodoo Framework

## PROJECT
Voodoo is a Python web framework for building agentic systems, not glue.
Combines durable runtime (executions, tasks, queue) with AI agents, MCP, mesh, auth, UI.
Single source of truth for sprints: SPRINT_PLAN.md
Master roadmap: MASTER_ROADMAP.md
Historical record: IMPLEMENTATION.md
Spec: VOODOO_RUNTIME_PROTOCOL_ARCHITECTURE.txt

## DIRECTORY
src/voodoo/ — framework source
  runtime/ — execution engine, persistence, workflow, task, planner
  storage/ — durable backends (database, queue, execution)
  ai/ — agents, providers, tools
  cli/ — typer CLI commands
  core/ — app factory, routing, state, events
  mesh/ — event/mesh subsystem
  mcp/ — MCP client integration
  primitives/ — Intent, Effect, Resource, State, Capability
  auth/ — JWT, cookies, passwords, middleware
  security/ — CORS, CSRF, headers, rate limiting
  telemetry/ — trace/metrics store
  ui/ — component library, rendering, styles
tests/ — pytest suite
  contracts/ — adapter contract mixins
examples/ — sample apps
docs/ — markdown documentation

## ENTRY-POINTS
CLI: src/voodoo/cli/__init__.py → app (typer.Typer)
  Commands: new, dev, generate, auth, ai, inspect, tasks, executions, version, doctor, routes, recover
Web app: src/voodoo/core/app.py → App class, create_app()
Runtime engine: src/voodoo/runtime/engine.py → engine (global), ExecutionEngine

## MODULES
src/voodoo/runtime/engine.py — ExecutionEngine, pipeline: Intent → Capability → Compute → Effect → State
  → uses CapabilityResolver, ConstraintEnforcer, ResourceAccountant
  → uses ApprovalRegistry for human-in-the-loop
src/voodoo/runtime/execution.py — Execution pydantic model, ExecutionStatus
src/voodoo/runtime/persistence.py — ExecutionStore protocol, InMemoryExecutionStore, JSONFileExecutionStore (legacy reader)
src/voodoo/runtime/workflow.py — Workflow orchestrator (sequential, parallel, conditional, iterative, delegated, hierarchical, adaptive)
src/voodoo/runtime/task.py — Task unit
src/voodoo/storage/database/interfaces.py — VoodooDatabase protocol, Migration, DatabaseCapabilities
src/voodoo/storage/database/sqlite.py — SQLiteDatabase, register_framework_migration
src/voodoo/storage/queue/ — VoodooQueue, SQLiteQueue, MemoryQueue
src/voodoo/storage/execution/ — SQLiteExecutionStore (Sprint 3)
src/voodoo/storage/manager.py — StorageManager (legacy file/S3 facade)
src/voodoo/workers/queue.py — durable task workers, @task/@queue decorators
src/voodoo/cli/inspect.py — inspect runtime state (run, agent, tool, task, workflow, state, capabilities, mesh, approvals)
src/voodoo/cli/executions.py — list/show durable executions and events (Sprint 3)
src/voodoo/cli/recover.py — recover unfinished executions from store
src/voodoo/cli/tasks.py — task list/retry

## RUNTIME-GRAPH
ExecutionEngine.execute() → _build_context() → _emit(events) → capabilities.authorize() → constraints.enforce() → _run_compute() → _record_result() → _persist()
ExecutionEngine._persist() → _execution_store.save() — raises on failure (§51.16)
ExecutionEngine._handle_failure() → execution.wait()/fail()/cancel()/time_out() → approvals.create() → _persist()
ExecutionEngine.recover() → _execution_store.load_all() → filter_unfinished() → approvals.create() for waiting
App lifespan → SQLiteExecutionStore(config.db_path) → engine.use_store()
Workflow.run() → strategy dispatch → Task.run() → engine.execute()/delegate()
Task.run() → engine.execute() → returns Execution
CLI inspect.run → engine.get()/recent()
CLI executions → SQLiteExecutionStore.load_all()/timeline()/list_events()
CLI recover → SQLiteExecutionStore or JSONFileExecutionStore → engine.use_store() → engine.recover()
workers/queue.py → VoodooQueue → SQLiteQueue/MemoryQueue

## SCHEMA
executions table (Sprint 3): id, trace_id, parent_execution_id, status, actor, intent, capabilities, resources, effects, state_changes, result, error, metadata, timestamps
execution_events journal (Sprint 3): sequence, execution_id, event_type, payload, timestamp
tasks table (Sprint 2): id, type, payload, status, priority, available_at, attempts, max_attempts, locked_by, locked_at, lease_until, last_error, idempotency_key
schema_migrations ledger: version, name, applied_at
executions JSONL (legacy): id, trace_id, parent_execution_id, status, intent, actor, capabilities, resources, effects, state_changes, result, error, metadata, timestamps

## ENV
VOODOO_QUEUE_PROVIDER — queue backend selection (memory|sqlite)
VOODOO_EXECUTION_STORE — path to JSONL execution store (legacy)

## DEPENDENCIES
Core: starlette, uvicorn, pydantic, aiosqlite, typer, rich
Optional extras: ai (openai, anthropic, google-generativeai, ollama), dev (pytest, ruff, mypy)
No PostgreSQL, Redis, S3 in default install

## TESTING
tests/contracts/test_database.py — DatabaseContractTests mixin
tests/contracts/test_queue.py — QueueContractTests mixin
tests/test_execution_sqlite_store.py — SQLiteExecutionStore, recovery, migration (Sprint 3)
tests/test_persistence.py — JSONFileExecutionStore, recover, workflow checkpoints
Run: just format && just lint && just test

## KNOWN-INVARIANTS
WAL mode for SQLite file-backed DBs
SQLiteExecutionStore is default durable store; JSONFileExecutionStore is legacy reader
SQLiteExecutionStore uses check_same_thread=False (cross-thread asyncio workers)
Execution journal is append-only; materialized executions table is last-write-wins
Engine _persist raises on failure (§51.16) — no silent swallowing
Framework migrations: version 1 (user models), 2 (tasks), 3 (executions); apps reserve 100+
Execution status: CREATED → PLANNED → AUTHORIZED → RUNNING → WAITING/terminal
Waiting executions rebuilt with approval records on recovery
Engine uses global `engine` instance by default

## EXTENSION-POINTS
ExecutionStore protocol — swap in SQLite/Postgres stores
VoodooDatabase protocol — SQLiteDatabase implements, PostgreSQL planned
VoodooQueue interface — SQLiteQueue, MemoryQueue
AdapterCapabilities — declarative contracts (Sprint 8)
App.use(plugin) — plugin hook post-Starlette build
register_framework_migration() — dynamic schema registration
