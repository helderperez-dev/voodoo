"""Tests for durable execution persistence & recovery (Phase 11)."""

from __future__ import annotations

import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.errors import ApprovalRequired
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.runtime.persistence import (
    InMemoryExecutionStore,
    JSONFileExecutionStore,
    filter_unfinished,
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


class TestInMemoryStore:
    def test_round_trip(self):
        store = InMemoryExecutionStore()
        ex = _execution()
        store.save(ex)
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == ex.id
        assert loaded[0].intent.name == "some.intent"


class TestJSONFileStore:
    def test_round_trip(self, tmp_path):
        store = JSONFileExecutionStore(tmp_path / "executions.jsonl")
        ex = _execution(id="a", status=ExecutionStatus.COMPLETED, result={"ok": 1})
        store.save(ex)
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == "a"
        assert loaded[0].result == {"ok": 1}
        assert loaded[0].status is ExecutionStatus.COMPLETED

    def test_append_only_multiple(self, tmp_path):
        store = JSONFileExecutionStore(tmp_path / "executions.jsonl")
        store.save(_execution(id="a"))
        store.save(_execution(id="b"))
        assert {e.id for e in store.load_all()} == {"a", "b"}

    def test_corrupt_lines_are_tolerated(self, tmp_path):
        path = tmp_path / "executions.jsonl"
        path.write_text(
            "not valid json\n"
            '{"id": "good", "trace_id": "t", "intent": {"name": "ok", "status": "created", "temporal_unit": "sec"}}\n'
            "{also broken\n",
            encoding="utf-8",
        )
        store = JSONFileExecutionStore(path)
        loaded = store.load_all()
        # the one valid line loads; corrupt lines are skipped
        assert [e.id for e in loaded] == ["good"]

    def test_missing_file_loads_empty(self, tmp_path):
        store = JSONFileExecutionStore(tmp_path / "nope.jsonl")
        assert store.load_all() == []

    def test_load_latest_last_write_wins(self, tmp_path):
        store = JSONFileExecutionStore(tmp_path / "executions.jsonl")
        store.save(_execution(id="a", status=ExecutionStatus.CREATED))
        store.save(_execution(id="a", status=ExecutionStatus.COMPLETED))
        latest = store.load_latest()
        assert latest["a"].status is ExecutionStatus.COMPLETED


class TestFilterUnfinished:
    def test_filters_terminal_states(self):
        unfinished = [
            _execution(id="c", status=ExecutionStatus.CREATED),
            _execution(id="p", status=ExecutionStatus.PLANNED),
            _execution(id="r", status=ExecutionStatus.RUNNING),
            _execution(id="w", status=ExecutionStatus.WAITING),
        ]
        finished = [
            _execution(id="d", status=ExecutionStatus.COMPLETED),
            _execution(id="f", status=ExecutionStatus.FAILED),
        ]
        ids = {e.id for e in filter_unfinished(unfinished + finished)}
        assert ids == {"c", "p", "r", "w"}


class TestRecover:
    def test_recover_returns_unfinished_only(self, tmp_path):
        store = JSONFileExecutionStore(tmp_path / "executions.jsonl")
        store.save(_execution(id="waiting", status=ExecutionStatus.WAITING))
        store.save(_execution(id="done", status=ExecutionStatus.COMPLETED))

        engine = ExecutionEngine()
        engine.use_store(store)
        recovered = engine.recover()
        assert {e.id for e in recovered} == {"waiting"}

    def test_recover_without_store_returns_empty(self):
        engine = ExecutionEngine()
        assert engine.recover() == []

    def test_recover_rebuilds_pending_approval_for_waiting(self, tmp_path):
        store = JSONFileExecutionStore(tmp_path / "executions.jsonl")
        store.save(_execution(id="w", status=ExecutionStatus.WAITING, actor="bob"))

        engine = ExecutionEngine()
        engine.use_store(store)
        recovered = engine.recover()
        assert recovered
        # a restarted waiting execution gets a resumable approval record
        approval = engine.approvals.get("w")
        assert approval is not None
        assert approval.requested_by == "bob"


def test_persisted_approval_survives_restart_end_to_end(tmp_path):
    """A human-approved execution's waiting state survives a process restart."""
    store = JSONFileExecutionStore(tmp_path / "executions.jsonl")

    # First process: run an approval-gated compute, persist the waiting state.
    engine = ExecutionEngine()
    engine.use_store(store)

    async def compute(ctx):
        from voodoo.runtime.human import ApprovalStatus as S

        if ctx.metadata.get("approval") != S.APPROVED.value:
            raise ApprovalRequired("please approve", execution_id=ctx.execution_id)
        return "done"

    with pytest.raises(ApprovalRequired):
        import asyncio

        asyncio.run(engine.execute(Intent(name="manual"), compute))
    waiting = engine.get(list(engine.executions)[-1])
    assert waiting.status is ExecutionStatus.WAITING

    # "Restart": a fresh engine recovers the waiting execution from the store.
    engine2 = ExecutionEngine()
    engine2.use_store(store)
    recovered = engine2.recover()
    recovered_ids = {e.id for e in recovered}
    assert waiting.id in recovered_ids
    assert engine2.approvals.get(waiting.id) is not None


def test_workflow_checkpoints_each_task(tmp_path):
    """A sequential workflow persists each task's execution to the store
    as it completes, so a mid-workflow restart can recover partial progress."""
    from voodoo.runtime import Task, Workflow, WorkflowStrategy
    from voodoo.runtime.persistence import JSONFileExecutionStore

    store = JSONFileExecutionStore(tmp_path / "wf_executions.jsonl")
    engine = ExecutionEngine()
    engine.use_store(store)

    async def step_a(ctx):
        return "a"

    async def step_b(ctx):
        return "b"

    task_a = Task(name="a", compute=step_a)
    task_b = Task(name="b", compute=step_b, depends_on=[task_a])
    wf = Workflow(tasks=[task_a, task_b], strategy=WorkflowStrategy.SEQUENTIAL)

    import asyncio

    asyncio.run(wf.run(engine=engine))

    loaded = store.load_all()
    # both task executions should be in the store (checkpointed per-task)
    ids = {e.id for e in loaded}
    assert len(ids) >= 2
    # all should be completed (not waiting/running)
    assert all(e.status is ExecutionStatus.COMPLETED for e in loaded)
