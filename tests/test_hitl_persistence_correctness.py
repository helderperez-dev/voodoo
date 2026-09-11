"""Durability regressions for human-in-the-loop decisions."""

from __future__ import annotations

import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.errors import ApprovalRequired
from voodoo.storage.execution import SQLiteExecutionStore


def _execution_by_id(store: SQLiteExecutionStore, execution_id: str):
    return next(ex for ex in store.load_all() if ex.id == execution_id)


@pytest.mark.asyncio
async def test_approve_after_restart_persists_parent_completion_and_child_lineage(
    tmp_path,
) -> None:
    db = str(tmp_path / "state.db")

    def deploy(ctx: ExecutionContext):
        if ctx.metadata.get("approval") != "approved":
            raise ApprovalRequired(
                "Deploy?",
                execution_id=ctx.execution_id,
                trace_id=ctx.trace_id,
                context={"capability": "deploy.execute"},
            )
        return "deployed"

    first = ExecutionEngine()
    first_store = SQLiteExecutionStore(db)
    first.use_store(first_store)
    with pytest.raises(ApprovalRequired):
        await first.execute(Intent(name="deploy"), deploy)

    waiting = first.recent(1)[0]
    approval = first.approvals.get(waiting.id)
    assert approval is not None
    approval.participant = "deployer"
    first._persist_approval(approval)
    first_store.close()

    second = ExecutionEngine()
    second_store = SQLiteExecutionStore(db)
    second.use_store(second_store)
    second.recover()
    second.register_participant("deployer", deploy)

    resumed = await second.approve(waiting.id, by="ops", note="approved")
    assert resumed is not None
    assert resumed.result == "deployed"
    assert resumed.parent_execution_id == waiting.id
    second_store.close()

    reopened = SQLiteExecutionStore(db)
    original = _execution_by_id(reopened, waiting.id)
    durable_child = _execution_by_id(reopened, resumed.id)
    assert original.status.value == "completed"
    assert original.result == "deployed"
    assert durable_child.status.value == "completed"
    assert durable_child.parent_execution_id == waiting.id
    reopened.close()


@pytest.mark.asyncio
async def test_deny_after_restart_persists_waiting_execution_failure(tmp_path) -> None:
    db = str(tmp_path / "state.db")

    def guarded(ctx: ExecutionContext):
        raise ApprovalRequired(
            "Delete?",
            execution_id=ctx.execution_id,
            trace_id=ctx.trace_id,
            context={"capability": "data.destroy"},
        )

    first = ExecutionEngine()
    first_store = SQLiteExecutionStore(db)
    first.use_store(first_store)
    with pytest.raises(ApprovalRequired):
        await first.execute(Intent(name="purge"), guarded)
    waiting = first.recent(1)[0]
    first_store.close()

    second = ExecutionEngine()
    second_store = SQLiteExecutionStore(db)
    second.use_store(second_store)
    second.recover()
    denied = await second.deny(waiting.id, by="admin", reason="too risky")
    assert denied is not None
    assert denied.status.value == "failed"
    second_store.close()

    reopened = SQLiteExecutionStore(db)
    durable = _execution_by_id(reopened, waiting.id)
    assert durable.status.value == "failed"
    assert "too risky" in (durable.error or "")
    reopened.close()


@pytest.mark.asyncio
async def test_approval_without_resumable_compute_still_persists_terminal_state(
    tmp_path,
) -> None:
    db = str(tmp_path / "state.db")

    engine = ExecutionEngine()
    store = SQLiteExecutionStore(db)
    engine.use_store(store)

    def guarded(ctx: ExecutionContext):
        raise ApprovalRequired(
            "Proceed?",
            execution_id=ctx.execution_id,
            trace_id=ctx.trace_id,
        )

    with pytest.raises(ApprovalRequired):
        await engine.execute(Intent(name="manual"), guarded)
    waiting = engine.recent(1)[0]
    store.close()

    recovered = ExecutionEngine()
    recovered_store = SQLiteExecutionStore(db)
    recovered.use_store(recovered_store)
    recovered.recover()
    decided = await recovered.approve(waiting.id, by="operator")
    assert decided is not None
    assert decided.status.value == "completed"
    recovered_store.close()

    reopened = SQLiteExecutionStore(db)
    durable = _execution_by_id(reopened, waiting.id)
    assert durable.status.value == "completed"
    assert durable.result == {"approved": True, "by": "operator"}
    reopened.close()
