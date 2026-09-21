"""Sprint 28.8 acceptance for HITL recovery over application.vstore."""

from __future__ import annotations

from pathlib import Path

import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.execution.engine import ExecutionEngine
from voodoo.runtime.errors import ApprovalRequired
from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store
from voodoo.storage.execution.store import VoodooStoreExecutionStore


def _open(path: Path) -> tuple[RuntimeStore, VoodooStoreExecutionStore]:
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    return runtime, VoodooStoreExecutionStore()


def _close(runtime: RuntimeStore) -> None:
    bind_active_runtime_store(None)
    runtime.stop()


def _execution(store: VoodooStoreExecutionStore, execution_id: str):
    return next(item for item in store.load_all() if item.id == execution_id)


@pytest.mark.asyncio
async def test_pending_approval_is_rehydrated_and_denied_after_store_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "application.vstore"
    first_runtime, first_store = _open(path)
    first = ExecutionEngine()
    first.use_store(first_store)

    def guarded(ctx: ExecutionContext):
        raise ApprovalRequired(
            "Delete production data?",
            execution_id=ctx.execution_id,
            trace_id=ctx.trace_id,
            context={"capability": "data.destroy"},
        )

    with pytest.raises(ApprovalRequired):
        await first.execute(Intent(name="purge"), guarded)
    waiting = first.recent(1)[0]
    assert waiting.status.value == "waiting"
    assert first_store.load_approval(waiting.id)["status"] == "pending"
    _close(first_runtime)

    second_runtime, second_store = _open(path)
    try:
        second = ExecutionEngine()
        second.use_store(second_store)
        recovered = second.recover()

        assert [item.id for item in recovered] == [waiting.id]
        approval = second.approvals.get(waiting.id)
        assert approval is not None
        assert approval.status.value == "pending"
        assert approval.capability == "data.destroy"

        denied = await second.deny(waiting.id, by="operator", reason="too risky")
        assert denied is not None
        assert denied.status.value == "failed"
        assert second_store.load_approval(waiting.id)["status"] == "denied"
        assert _execution(second_store, waiting.id).status.value == "failed"
    finally:
        _close(second_runtime)

    third_runtime, third_store = _open(path)
    try:
        durable = _execution(third_store, waiting.id)
        approval = third_store.load_approval(waiting.id)
        assert durable.status.value == "failed"
        assert "too risky" in (durable.error or "")
        assert approval is not None
        assert approval["status"] == "denied"
        assert approval["decided_by"] == "operator"
    finally:
        _close(third_runtime)


@pytest.mark.asyncio
async def test_pending_approval_can_resume_registered_compute_after_store_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "application.vstore"

    def deploy(ctx: ExecutionContext):
        if ctx.metadata.get("approval") != "approved":
            raise ApprovalRequired(
                "Deploy release?",
                execution_id=ctx.execution_id,
                trace_id=ctx.trace_id,
                context={"capability": "deploy.execute"},
            )
        return "deployed"

    first_runtime, first_store = _open(path)
    first = ExecutionEngine()
    first.use_store(first_store)
    with pytest.raises(ApprovalRequired):
        await first.execute(Intent(name="deploy"), deploy)
    waiting = first.recent(1)[0]

    approval = first.approvals.get(waiting.id)
    assert approval is not None
    approval.participant = "deployer"
    first._persist_approval(approval)
    _close(first_runtime)

    second_runtime, second_store = _open(path)
    try:
        second = ExecutionEngine()
        second.use_store(second_store)
        second.register_participant("deployer", deploy)
        recovered = second.recover()
        assert [item.id for item in recovered] == [waiting.id]

        resumed = await second.approve(waiting.id, by="ops", note="approved")
        assert resumed is not None
        assert resumed.result == "deployed"
        assert resumed.parent_execution_id == waiting.id
        assert _execution(second_store, waiting.id).status.value == "completed"
        assert _execution(second_store, waiting.id).result == "deployed"
        durable_child = _execution(second_store, resumed.id)
        assert durable_child.parent_execution_id == waiting.id
        assert durable_child.status.value == "completed"
        assert second_store.load_approval(waiting.id)["status"] == "approved"
    finally:
        _close(second_runtime)
