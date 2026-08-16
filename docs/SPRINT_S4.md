# Sprint 4 — Data & Workers

> Implementation tracking for S4. Derived from IMPLEMENTATION_PLAN.md §3.1, §3.3.
> **Status**: Done

---

## Goal

Deliver the `Model` CRUD facade and the `@task` worker decorator with retries,
timeouts, and telemetry spans. Apps can persist data and run background work.

---

## Workstreams

### S4-1: Model facade (G7)
- [x] `class Lead(Model)` with async `create/get/all/save/delete`
- [x] Pydantic + aiosqlite underneath (existing `data.py`)
- [x] Keep existing hooks (`on_insert`, `on_update`) working
- [x] Design storage backend boundary (PostgreSQL adapter later)
- [x] Table creation conventions (create-if-absent; migrations = extension point)
- [x] **File**: `voodoo/data/model.py` (new), `voodoo/data/__init__.py` (extend)

### S4-2: @task worker decorator (G8)
- [x] `@task` decorator with retries, timeout, structured errors
- [x] Telemetry span per task execution
- [x] Queue integration with Mesh events (`@mesh.on` → `@task` chain)
- [x] Document single-process scope; boundary named for future distributed backend
- [x] **File**: `voodoo/workers/__init__.py` (new), `voodoo/queue.py` (refactor)

### S4-3: Exports & contract
- [x] Export `Model`, `task` from `voodoo/__init__.py`
- [x] Update `__all__` and contract test
- [x] **Files**: `voodoo/__init__.py`, `tests/test_contract_api.py`

### S4-4: Tests
- [x] `tests/test_model.py`: CRUD operations, hooks, table creation
- [x] `tests/test_workers.py`: @task retries, timeout, error handling, telemetry
- [x] Full suite green; ruff clean; commit

---

## File Changes

| File | Action | Description |
|---|---|---|
| `voodoo/data/model.py` | NEW | Model facade with async CRUD |
| `voodoo/data/__init__.py` | NEW | Package re-exports + PEP 562 live-global forwarding |
| `voodoo/data/base.py` | RENAMED (from `voodoo/data.py`) | Existing BaseModel/storage layer; metaclass skips `Model` |
| `voodoo/workers/__init__.py` | NEW | @task decorator, worker runtime |
| `voodoo/queue.py` | MODIFY | Refactor onto workers package |
| `voodoo/__init__.py` | MODIFY | Export Model, task |
| `tests/test_model.py` | NEW | Model CRUD tests |
| `tests/test_workers.py` | NEW | Worker tests |
| `tests/test_contract_api.py` | MODIFY | Add Model, task to __all__ |

---

## Exit Criteria

- [x] `Model.create()`, `.get()`, `.all()`, `.save()`, `.delete()` work async
- [x] `@task` runs with retries, timeout, and telemetry span
- [x] `@mesh.on` → `@task` chain works naturally
- [x] Existing data tests pass
- [x] Full suite green; ruff clean; committed (no version bump)
