# Skill: Runtime Feature

> **When to use:** When adding features to the ExecutionEngine, execution lifecycle, checkpoint/recovery, or runtime internals.

---

## Purpose

Guide the structured addition of runtime engine features, ensuring they respect the execution lifecycle, trace_id propagation, and durability guarantees.

---

## Prerequisites

1. Read `.github/instructions/runtime.instructions.md` — full runtime reference.
2. Read `.github/instructions/execution.instructions.md` — persistence & recovery.
3. Read `.github/copilot-instructions.md` — Architectural Invariants.

---

## Runtime Architecture

### ExecutionEngine singleton

```python
from voodoo.runtime import engine

# The engine is a singleton — never instantiate ExecutionEngine() directly
# (except in tests with fresh instances)
result = await engine.execute(intent="my.intent", ...)
```

### Execution lifecycle

```
created → planned → authorized → running → waiting → completed
                    ↓              ↓         ↓
                  failed        timed_out  cancelled
```

### Execution context

Every execution carries:
- `execution_id` — unique identifier
- `trace_id` — correlation ID (propagates through the stack)
- `intent` — what the user wants to do
- `capabilities` — what the system can do
- `effects` — what actually happens
- `state` — current state
- `status` — lifecycle status

---

## Workflow

### Step 1: Identify the Feature

Determine which runtime component the feature touches:

| Component | Location | Responsibility |
|---|---|---|
| `ExecutionEngine` | `runtime/engine.py` | Orchestrate executions |
| `ExecutionContext` | `runtime/context.py` | Per-execution state |
| `Planner` | `runtime/planner.py` | Intent → effects planning |
| `CapabilityResolver` | `runtime/adaptive.py` | Resolve capabilities |
| `AdaptiveSupervisor` | `runtime/adaptive.py` | Adaptive execution |
| `HumanInTheLoop` | `runtime/human.py` | Approvals/pauses |
| `ExecutionStore` | `runtime/persistence.py` | Durability |
| `ConstraintEnforcer` | `runtime/engine.py` | Constraint checking |

### Step 2: Read the Relevant Module

Read the full source of the module you're modifying. Understand:
- The class hierarchy and methods.
- How `trace_id` propagates.
- What state is persisted.
- What events are emitted.

### Step 3: Implement the Feature

Follow these rules:

1. **`from __future__ import annotations`** at the top.
2. **Type hints everywhere** — Use `str | None`, `list[Any]`, `dict[str, Any]`.
3. **`__all__`** export list.
4. **Section dividers** — `# ---...` between logical sections.
5. **Docstrings** — Module-level + class/function with `Parameters` sections.
6. **Correlation IDs** — If the feature processes executions, propagate `trace_id`.
7. **Events namespaced** — If emitting events, use dotted namespaces.
8. **Lazy imports** — Provider SDKs at function level.
9. **Error handling** — Use `VoodooError` hierarchy. Broad excepts with `# noqa: BLE001`.

### Step 4: Extend the ExecutionStore (if needed)

If the feature requires new persisted data:

1. **Extend the Protocol** — Add methods to `ExecutionStore` in `runtime/persistence.py`.
2. **Implement in all stores** — `InMemoryExecutionStore`, `SQLiteExecutionStore`, `PostgresExecutionStore`.
3. **Add migration** — Register via `register_framework_migration()` in `storage/execution/sqlite.py`.
4. **Update checkpoint format** — If checkpoint data changes, update `checkpoint()` and `resume_checkpoint()`.
5. **PG-safe** — Test FK ordering with PostgreSQL.

### Step 5: Write Tests

```python
class TestMyFeature:
    """Tests for the new runtime feature."""

    async def test_basic_case(self):
        # Use fresh engine instance, not the singleton
        engine = ExecutionEngine()
        result = await engine.execute(...)
        assert result.status == "completed"

    async def test_failure_path(self):
        # Every durability claim needs a failure-path test
        engine = ExecutionEngine()
        # ... simulate crash, recover, verify state

    async def test_trace_id_propagation(self):
        engine = ExecutionEngine()
        result = await engine.execute(intent="test", ...)
        assert result.trace_id is not None
```

**Critical:** Use fresh `ExecutionEngine()` instances in tests, never the singleton.

### Step 6: Update CLI (if observable)

If users need to observe the new feature, add a `voodoo` subcommand in `src/voodoo/cli/`:

```python
@app.command()
def my_feature():
    """Show my feature info."""
    ...
```

### Step 7: Quality Gate

```bash
just format && just lint && just test
uv run mypy src/voodoo
```

### Step 8: Update Documentation

1. Update `CHANGELOG.md`.
2. Update `docs/runtime.md` if behavior changed.
3. Update `.github/instructions/runtime.instructions.md` if the feature changes the runtime guidance.

---

## Common Runtime Features

### Adding a new execution status

1. Add to the `ExecutionStatus` StrEnum in `runtime/types.py`.
2. Update the state machine transitions in `runtime/engine.py`.
3. Update `filter_unfinished()` in `runtime/persistence.py`.
4. Update `SQLiteExecutionStore` schema if needed.
5. Add tests for the new status transitions.

### Adding a new constraint type

1. Add the constraint check in `ConstraintEnforcer` (`runtime/engine.py`).
2. Define the constraint data structure.
3. Add tests for constraint enforcement and violation.

### Adding a new planner strategy

1. Subclass `Planner` in `runtime/planner.py`.
2. Implement `plan(intent, capabilities) -> list[Effect]`.
3. Register the strategy if applicable.
4. Test with various intents and capability sets.

### Adding human-in-the-loop support

1. Use `HumanInTheLoop` in `runtime/human.py`.
2. Create an `Approval` record.
3. Persist via `ExecutionStore.save_approval()`.
4. Emit `"approval.requested"` event.
5. Test the approval flow and recovery.

---

## Checklist

- [ ] Feature respects execution lifecycle state machine.
- [ ] `trace_id` propagates through the feature.
- [ ] Events use dotted namespaces.
- [ ] ExecutionStore extended in all implementations (if persisted).
- [ ] Migration registered (if new columns/tables).
- [ ] PG-safe FK ordering (if new tables).
- [ ] Failure-path tests written.
- [ ] Fresh engine instances in tests (not singleton).
- [ ] CLI updated (if observable).
- [ ] Quality gate passes.
- [ ] `uv run mypy src/voodoo` passes.
- [ ] Documentation updated.
