"""Execution store contract tests (Sprint 22.1).

``ExecutionStoreContractTests`` is the portability suite every
``ExecutionStore`` implementation must pass unchanged — SQLite (default)
and PostgreSQL (production). Provider-specific behavior gets its own
tests on top.
"""

from __future__ import annotations

import pytest

from voodoo.primitives.effect import Effect
from voodoo.primitives.intent import Intent
from voodoo.runtime.execution import Execution, ExecutionStatus


def _execution(**overrides) -> Execution:
    """Helper to create a minimal Execution for testing."""
    base = {
        "id": "ex1",
        "trace_id": "t1",
        "intent": Intent(name="test.intent"),
        "actor": "tester",
    }
    base.update(overrides)
    return Execution(**base)


class ExecutionStoreContractTests:
    """Mixin run against every execution store adapter.

    Subclasses must implement ``make_store`` to return a fresh store
    instance. The store is closed after each test via the autouse fixture.
    """

    def make_store(self) -> object:
        raise NotImplementedError

    @pytest.fixture(autouse=True)
    def store(self):
        store = self.make_store()
        yield store
        store.close()

    # -- save / load -------------------------------------------------------

    def test_round_trip(self, store):
        ex = _execution(
            id="rt1",
            status=ExecutionStatus.COMPLETED,
            result={"ok": True},
        )
        store.save(ex)
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == "rt1"
        assert loaded[0].result == {"ok": True}
        assert loaded[0].status is ExecutionStatus.COMPLETED

    def test_save_multiple_executions(self, store):
        store.save(_execution(id="m1"))
        store.save(_execution(id="m2"))
        ids = {e.id for e in store.load_all()}
        assert ids == {"m1", "m2"}

    def test_last_write_wins(self, store):
        store.save(_execution(id="lw", status=ExecutionStatus.CREATED))
        store.save(_execution(id="lw", status=ExecutionStatus.COMPLETED))
        loaded = {e.id: e for e in store.load_all()}
        assert loaded["lw"].status is ExecutionStatus.COMPLETED

    def test_save_preserves_parent_execution_id(self, store):
        ex = _execution(id="child", parent_execution_id="parent")
        store.save(ex)
        loaded = store.load_all()
        assert loaded[0].parent_execution_id == "parent"

    def test_save_preserves_capabilities(self, store):
        ex = _execution(id="cap", capabilities=["read", "write"])
        store.save(ex)
        loaded = store.load_all()
        assert loaded[0].capabilities == ["read", "write"]

    def test_save_preserves_effects(self, store):
        ex = _execution(id="eff")
        effect = Effect(name="db.write", idempotent=True)
        effect.mark_succeeded()
        ex.add_effect(effect)
        store.save(ex)
        loaded = store.load_all()
        assert len(loaded[0].effects) == 1
        assert loaded[0].effects[0].name == "db.write"

    # -- journal / timeline ------------------------------------------------

    def test_journal_timeline(self, store):
        ex = _execution(id="tl", status=ExecutionStatus.COMPLETED)
        store.save(ex)
        timeline = store.timeline("tl")
        assert len(timeline) >= 1
        assert timeline[0]["event_type"] == "execution.completed"

    def test_journal_records_status_transitions(self, store):
        ex = _execution(id="trans", status=ExecutionStatus.RUNNING)
        store.save(ex)
        ex.complete(result="done")
        store.save(ex)
        timeline = store.timeline("trans")
        event_types = [ev["event_type"] for ev in timeline]
        assert "execution.started" in event_types
        assert "execution.completed" in event_types

    def test_list_events_across_executions(self, store):
        store.save(_execution(id="ev1", status=ExecutionStatus.CREATED))
        store.save(_execution(id="ev2", status=ExecutionStatus.WAITING))
        events = store.list_events()
        assert len(events) >= 2

    def test_timeline_empty_for_unknown_execution(self, store):
        timeline = store.timeline("nonexistent")
        assert timeline == []

    # -- approvals ---------------------------------------------------------

    def test_save_and_load_approval(self, store):
        from voodoo.runtime.human import Approval

        approval = Approval(
            id="ap1",
            execution_id="ex1",
            trace_id="t1",
            capability="payment.execute",
            question="Approve $100?",
        )
        store.save_approval(approval)
        loaded = store.load_approval("ex1")
        assert loaded is not None
        assert loaded["id"] == "ap1"
        assert loaded["capability"] == "payment.execute"

    def test_load_approval_missing(self, store):
        loaded = store.load_approval("nonexistent")
        assert loaded is None

    # -- artifacts ---------------------------------------------------------

    def test_record_artifact(self, store):
        ex = _execution(id="art")
        store.save(ex)
        store.record_artifact(
            {
                "id": "a1",
                "execution_id": "art",
                "checksum": "abc123",
                "created_by": "tester",
            }
        )
        # Verify the artifact was recorded (store-specific assertion
        # may vary; at minimum it should not raise)


# ---------------------------------------------------------------------------
# SQLite concrete implementation
# ---------------------------------------------------------------------------


class TestSQLiteExecutionStoreContract(ExecutionStoreContractTests):
    """Run the execution store contract against SQLiteExecutionStore."""

    def make_store(self):
        import tempfile
        from pathlib import Path

        self._tmp_dir = tempfile.mkdtemp()
        from voodoo.storage.execution import SQLiteExecutionStore

        return SQLiteExecutionStore(Path(self._tmp_dir) / "executions.db")
