"""Tests for the SQLite-backed durable execution store (Sprint 3)."""

from __future__ import annotations

import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.runtime.persistence import JSONFileExecutionStore
from voodoo.storage.execution import SQLiteExecutionStore


def _execution(**overrides) -> Execution:
    base = {
        "id": "ex1",
        "trace_id": "t1",
        "intent": Intent(name="some.intent"),
        "actor": "alice",
    }
    base.update(overrides)
    return Execution(**base)


class TestSQLiteExecutionStore:
    def test_round_trip(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        ex = _execution(id="a", status=ExecutionStatus.COMPLETED, result={"ok": 1})
        store.save(ex)
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == "a"
        assert loaded[0].result == {"ok": 1}
        assert loaded[0].status is ExecutionStatus.COMPLETED
        store.close()

    def test_save_multiple_executions(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        store.save(_execution(id="a"))
        store.save(_execution(id="b"))
        assert {e.id for e in store.load_all()} == {"a", "b"}
        store.close()

    def test_last_write_wins(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        store.save(_execution(id="a", status=ExecutionStatus.CREATED))
        store.save(_execution(id="a", status=ExecutionStatus.COMPLETED))
        loaded = {e.id: e for e in store.load_all()}
        assert loaded["a"].status is ExecutionStatus.COMPLETED
        store.close()

    def test_journal_timeline(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        ex = _execution(id="a", status=ExecutionStatus.COMPLETED)
        store.save(ex)
        timeline = store.timeline("a")
        assert len(timeline) == 1
        assert timeline[0]["event_type"] == "execution.completed"
        assert timeline[0]["payload"]["id"] == "a"
        store.close()

    def test_journal_records_status_transitions(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        ex = _execution(id="a", status=ExecutionStatus.RUNNING)
        store.save(ex)
        ex.complete(result="done")
        store.save(ex)
        timeline = store.timeline("a")
        assert [ev["event_type"] for ev in timeline] == [
            "execution.started",
            "execution.completed",
        ]
        store.close()

    def test_list_events_across_executions(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        store.save(_execution(id="a", status=ExecutionStatus.CREATED))
        store.save(_execution(id="b", status=ExecutionStatus.WAITING))
        events = store.list_events()
        assert len(events) == 2
        assert {ev["execution_id"] for ev in events} == {"a", "b"}
        store.close()

    def test_missing_file_creates_new_db(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "new_dir" / "executions.db")
        assert store.load_all() == []
        store.close()

    def test_data_survives_reopen(self, tmp_path):
        path = tmp_path / "executions.db"
        store = SQLiteExecutionStore(path)
        store.save(_execution(id="durable", status=ExecutionStatus.COMPLETED))
        store.close()

        reopened = SQLiteExecutionStore(path)
        loaded = reopened.load_all()
        assert [e.id for e in loaded] == ["durable"]
        reopened.close()


class TestEngineRecoveryFromSQLite:
    def test_recover_returns_unfinished_only(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        store.save(_execution(id="waiting", status=ExecutionStatus.WAITING))
        store.save(_execution(id="done", status=ExecutionStatus.COMPLETED))

        engine = ExecutionEngine()
        engine.use_store(store)
        recovered = engine.recover()
        assert {e.id for e in recovered} == {"waiting"}
        store.close()

    def test_recover_rebuilds_pending_approval(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        store.save(_execution(id="w", status=ExecutionStatus.WAITING, actor="bob"))

        engine = ExecutionEngine()
        engine.use_store(store)
        recovered = engine.recover()
        assert recovered
        approval = engine.approvals.get("w")
        assert approval is not None
        assert approval.requested_by == "bob"
        store.close()


class TestJSONLToSQLiteMigration:
    def test_import_jsonl_executions(self, tmp_path):
        jsonl = JSONFileExecutionStore(tmp_path / "legacy.jsonl")
        jsonl.save(_execution(id="old1", status=ExecutionStatus.COMPLETED))
        jsonl.save(_execution(id="old2", status=ExecutionStatus.WAITING))

        sqlite = SQLiteExecutionStore(tmp_path / "new.db")
        for ex in jsonl.load_all():
            sqlite.save(ex)

        loaded = sqlite.load_all()
        assert {e.id for e in loaded} == {"old1", "old2"}
        sqlite.close()


def test_persistence_failure_raises_not_swallowed(tmp_path):
    """Persistence errors must surface, not be silently dropped (§51.16)."""
    store = SQLiteExecutionStore(tmp_path / "executions.db")
    store.close()  # simulate a broken store

    engine = ExecutionEngine()
    engine.use_store(store)
    ex = _execution(id="boom", status=ExecutionStatus.COMPLETED)

    with pytest.raises(AttributeError):
        engine._persist(ex)
