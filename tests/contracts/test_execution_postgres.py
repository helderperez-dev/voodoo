"""PostgreSQL execution store tests (Sprint 11).

Mirrors ``tests/test_execution_sqlite_store.py`` against a real PostgreSQL
server when ``VOODOO_TEST_DATABASE_URL`` is set (CI service container).
Skipped locally when no server is available.
"""

from __future__ import annotations

import os

import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.storage.execution import PostgresExecutionStore

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_DATABASE_URL"),
    reason="VOODOO_TEST_DATABASE_URL not set (no PostgreSQL server available)",
)


def _execution(**overrides) -> Execution:
    base = {
        "id": "ex1",
        "trace_id": "t1",
        "intent": Intent(name="some.intent"),
        "actor": "alice",
    }
    base.update(overrides)
    return Execution(**base)


def _drop_tables(conn) -> None:
    with conn.cursor() as cur:
        for table in ("execution_events", "executions", "artifacts", "approvals"):
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    conn.commit()


@pytest.fixture
def store() -> PostgresExecutionStore:
    import psycopg as _p

    url = os.environ["VOODOO_TEST_DATABASE_URL"]
    with _p.connect(url) as conn:
        _drop_tables(conn)
    s = PostgresExecutionStore(url)
    yield s
    s.close()


class TestPostgresExecutionStore:
    def test_round_trip(self, store):
        ex = _execution(id="a", status=ExecutionStatus.COMPLETED, result={"ok": 1})
        store.save(ex)
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == "a"
        assert loaded[0].result == {"ok": 1}
        assert loaded[0].status is ExecutionStatus.COMPLETED

    def test_save_multiple_executions(self, store):
        store.save(_execution(id="a"))
        store.save(_execution(id="b"))
        assert {e.id for e in store.load_all()} == {"a", "b"}

    def test_last_write_wins(self, store):
        store.save(_execution(id="a", status=ExecutionStatus.CREATED))
        store.save(_execution(id="a", status=ExecutionStatus.COMPLETED))
        loaded = {e.id: e for e in store.load_all()}
        assert loaded["a"].status is ExecutionStatus.COMPLETED

    def test_journal_timeline(self, store):
        ex = _execution(id="a", status=ExecutionStatus.COMPLETED)
        store.save(ex)
        timeline = store.timeline("a")
        assert len(timeline) == 1
        assert timeline[0]["event_type"] == "execution.completed"
        assert timeline[0]["payload"]["id"] == "a"

    def test_journal_records_status_transitions(self, store):
        ex = _execution(id="a", status=ExecutionStatus.RUNNING)
        store.save(ex)
        ex.complete(result="done")
        store.save(ex)
        timeline = store.timeline("a")
        assert [ev["event_type"] for ev in timeline] == [
            "execution.started",
            "execution.completed",
        ]

    def test_list_events_across_executions(self, store):
        store.save(_execution(id="a", status=ExecutionStatus.CREATED))
        store.save(_execution(id="b", status=ExecutionStatus.WAITING))
        events = store.list_events()
        assert len(events) == 2
        assert {ev["execution_id"] for ev in events} == {"a", "b"}

    def test_data_survives_reopen(self, store):
        store.save(_execution(id="durable", status=ExecutionStatus.COMPLETED))
        store.close()

        reopened = PostgresExecutionStore(store.url)
        loaded = reopened.load_all()
        assert [e.id for e in loaded] == ["durable"]
        reopened.close()

    def test_record_and_list_artifacts(self, store):
        store.save(_execution(id="a", status=ExecutionStatus.COMPLETED))
        store.record_artifact(
            {
                "id": "art-1",
                "execution_id": "a",
                "tool": "research",
                "model": "gpt-4",
                "metadata": {"size": 10},
            }
        )
        artifacts = store.list_artifacts("a")
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == "art-1"
        assert artifacts[0]["metadata"] == {"size": 10}

    def test_save_and_load_approval(self, store):
        from datetime import UTC, datetime

        approval = _execution(id="w", status=ExecutionStatus.WAITING, actor="bob")
        store.save(approval)

        class _Approval:
            id = "appr-1"
            execution_id = "w"
            trace_id = "t-1"
            capability = "tool.run"
            question = "run?"
            requested_by = "bob"
            status = type("S", (), {"value": "pending"})()
            decided_by = None
            decided_at = None
            reason = None
            created_at = datetime.now(UTC)

        store.save_approval(_Approval())
        loaded = store.load_approval("w")
        assert loaded is not None
        assert loaded["capability"] == "tool.run"
        assert loaded["status"] == "pending"


class TestPostgresEngineRecovery:
    def test_recover_returns_unfinished_only(self, store):
        store.save(_execution(id="waiting", status=ExecutionStatus.WAITING))
        store.save(_execution(id="done", status=ExecutionStatus.COMPLETED))

        engine = ExecutionEngine()
        engine.use_store(store)
        recovered = engine.recover()
        assert {e.id for e in recovered} == {"waiting"}

    def test_recover_rebuilds_pending_approval(self, store):
        store.save(_execution(id="w", status=ExecutionStatus.WAITING, actor="bob"))

        engine = ExecutionEngine()
        engine.use_store(store)
        recovered = engine.recover()
        assert recovered
        approval = engine.approvals.get("w")
        assert approval is not None
        assert approval.requested_by == "bob"
