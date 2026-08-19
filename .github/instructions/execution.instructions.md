# Durable Persistence & Execution Instructions

> **Read this before:** touching `src/voodoo/runtime/persistence.py`, `src/voodoo/storage/execution/`, or anything related to checkpoints, recovery, or the execution journal.

---

## ExecutionStore Protocol (`voodoo.runtime.persistence`)

```python
class ExecutionStore(Protocol):
    def save(self, execution: Execution) -> None: ...
    def load_all(self) -> list[Execution]: ...
    def load_latest(self, execution_id: str) -> Execution | None: ...
    def load_approval(self, approval_id: str) -> Approval | None: ...
    def save_approval(self, approval: Approval) -> None: ...
    def append_event(self, execution_id: str, event: ExecutionEvent) -> None: ...
```

### Implementations

| Store | Location | Use Case |
|---|---|---|
| `InMemoryExecutionStore` | `runtime/persistence.py` | Tests only |
| `JSONFileExecutionStore` | `runtime/persistence.py` | Legacy JSONL reader (backward compat) |
| `SQLiteExecutionStore` | `storage/execution/sqlite.py` | **Default** — durable, WAL mode |
| `PostgresExecutionStore` | `storage/execution/postgres.py` | Production — server-backed |

---

## SQLiteExecutionStore (`voodoo.storage.execution.sqlite`)

### Key characteristics

- **Owns its own sync `sqlite3` connection** — not async `VoodooDatabase`. Engine checkpoints are synchronous.
- **WAL mode** with `busy_timeout=5000` for concurrent access.
- **Two tables:**
  - `executions` — materialized state (17 columns, last-write-wins on `save()`)
  - `execution_events` — append-only journal (FK → `executions.id`)

### Schema

```sql
CREATE TABLE executions (
    execution_id TEXT PRIMARY KEY,
    trace_id TEXT,
    parent_execution_id TEXT,
    intent TEXT,
    status TEXT,
    actor TEXT,
    capabilities TEXT,  -- JSON array
    effects TEXT,       -- JSON array
    state_changes TEXT, -- JSON
    cost REAL,
    duration_seconds REAL,
    error TEXT,
    created_at TEXT,
    updated_at TEXT,
    metadata TEXT,       -- JSON
    -- ... additional columns
);

CREATE TABLE execution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL REFERENCES executions(execution_id),
    event_type TEXT,
    data TEXT,           -- JSON
    timestamp TEXT,
);
```

### Indexes

- `idx_executions_trace_id` on `trace_id`
- `idx_executions_status` on `status`
- `idx_execution_events_execution_id` on `execution_id`
- `idx_execution_events_event_type` on `event_type`

### Migration

Registered via `register_framework_migration()` at import time:
- **v3** — `EXECUTION_MIGRATION` (creates `executions` + `execution_events` tables)
- **v7** — `execution_artifacts` table (in `migrations.py`)
- **v8** — `execution_approvals` table (in `migrations.py`)

---

## PostgresExecutionStore (`voodoo.storage.execution.postgres`)

### Key differences from SQLite

- **Sync psycopg** connection (not async).
- **FK-safe upsert** — `save()` must upsert the materialized `executions` row BEFORE appending journal events. PostgreSQL enforces the FK; SQLite (with FK enforcement off) does not.
- **Dict-like rows** — psycopg returns dict-like rows, so use `row["col"]` not `row[0]`.
- **Same schema** via shared translated migrations.

### Critical: FK ordering

```python
# CORRECT — upsert parent first
def save(self, execution: Execution) -> None:
    self._upsert_execution(execution)  # parent row first
    self._append_event(execution.execution_id, event)  # then journal


# WRONG — will fail on PostgreSQL
def save(self, execution: Execution) -> None:
    self._append_event(execution.execution_id, event)  # FK violation!
    self._upsert_execution(execution)
```

---

## Checkpoint & Recovery

### Checkpoint

```python
from voodoo.runtime import engine

# Checkpoint current execution state
engine.checkpoint(execution)
```

The checkpoint is a JSON-serializable snapshot containing:
- Completed effect IDs (for idempotency skip on resume)
- Current step index
- State changes count
- Status
- Metadata

### Resume from checkpoint

```python
completed_effect_ids = engine.resume_checkpoint(execution)
# Returns set of effect IDs that already completed — skip them on re-execution
```

### Recovery

```python
# Recover unfinished executions after a crash
await engine.recover()
```

`recover()`:
1. Loads all executions with status in `{created, planned, authorized, running, waiting}`.
2. Transitions `running` → `waiting` (since the compute was interrupted).
3. Rehydrates pending approval records.
4. Returns the list of recoverable executions.

### CLI recovery

```bash
voodoo recover              # restore unfinished executions
voodoo executions          # list all executions
voodoo execution <id>      # full timeline from journal
voodoo events              # recent journal events
voodoo artifacts <id>      # artifact chain for an execution
voodoo approvals           # list approvals
voodoo approvals approve <id>
voodoo approvals deny <id>
```

---

## Execution Journal

The `execution_events` table is an **append-only journal**. Each event has:

| Field | Purpose |
|---|---|
| `execution_id` | FK to `executions` |
| `event_type` | String (e.g., `"status_changed"`, `"effect_applied"`, `"checkpoint"`) |
| `data` | JSON blob with event-specific data |
| `timestamp` | ISO 8601 |

The journal enables:
- **Timeline reconstruction** — `voodoo execution <id>` shows the full history.
- **Audit trail** — Every state transition is recorded.
- **Recovery** — The materialized row can be rebuilt from the journal if corrupted.

---

## When Adding Persistence Features

1. **Extend the Protocol** — Add new methods to `ExecutionStore` in `runtime/persistence.py`.
2. **Implement in all stores** — `InMemoryExecutionStore`, `SQLiteExecutionStore`, `PostgresExecutionStore`.
3. **Add migration** — If new columns/tables are needed, register via `register_framework_migration()`.
4. **Update checkpoint format** — If the checkpoint needs new fields, update `checkpoint()` and `resume_checkpoint()`.
5. **Test durability** — Write a failure-path test: save → crash → recover → verify state.
6. **Update CLI** — If users need to observe the new data, add a `voodoo` subcommand.
7. **PG-safe** — Always test FK ordering with PostgreSQL (use the contract test suite).

---

## Failure-Path Testing

Every durability claim must have a failure-path test:

```python
class TestExecutionRecovery:
    async def test_crash_during_running_recovers(self):
        # 1. Create execution, set status to running
        # 2. Simulate crash (close store without completing)
        # 3. Reopen store, call recover()
        # 4. Verify execution is recovered as 'waiting'
        ...

    async def test_completed_effects_skipped_on_resume(self):
        # 1. Create execution with 3 effects
        # 2. Complete effects 1 and 2, checkpoint
        # 3. Crash
        # 4. Recover, resume
        # 5. Verify only effect 3 is executed
        ...
```

---

## Critical Gotchas

1. **PG FK ordering** — Upsert parent row BEFORE appending journal events. This is enforced on PostgreSQL.
2. **PG dict rows** — `row["col"]` not `row[0]`.
3. **WAL mode** — SQLite uses WAL with `busy_timeout=5000`. Don't change this without benchmarking concurrent access.
4. **Sync connection** — `SQLiteExecutionStore` owns a sync `sqlite3` connection, not async `aiosqlite`. Engine checkpoints are synchronous.
5. **Migration registration** — Migrations register at import time via `register_framework_migration()`. The `FRAMEWORK_MIGRATIONS` global is populated when `storage.execution.sqlite` is imported.
6. **`filter_unfinished()`** — Helper function in `runtime/persistence.py` that filters executions by unfinished statuses.
7. **Approval persistence** — Approvals are stored in `execution_approvals` (v8 migration). `load_approval()` / `save_approval()` methods on the store.
8. **Artifact persistence** — Artifacts are stored in `execution_artifacts` (v7 migration).
