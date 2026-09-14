"""Sprint 28.8 acceptance for Voodoo Store-backed Execution persistence."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from voodoo.runtime.execution import Execution
from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store
from voodoo.storage.execution.store import VoodooStoreExecutionStore


def _runtime(tmp_path: Path) -> RuntimeStore:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "application.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    return runtime


def test_execution_store_reuses_active_runtime_store(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    try:
        store = VoodooStoreExecutionStore()
        assert store.path == runtime.config.path
        assert store.provider == "voodoo"
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_execution_save_load_and_timeline_are_durable(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    try:
        store = VoodooStoreExecutionStore()
        execution = Execution(trace_id="trace-1", actor="agent:test")
        store.save(execution)
        execution.start()
        store.save(execution)
        execution.complete({"ok": True})
        store.save(execution)

        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].id == execution.id
        assert loaded[0].status.value == "completed"
        assert loaded[0].result == {"ok": True}

        timeline = store.timeline(execution.id)
        assert [event["event_type"] for event in timeline] == [
            "execution.created",
            "execution.started",
            "execution.completed",
        ]
        assert [event["sequence"] for event in timeline] == [1, 2, 3]
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_execution_artifacts_and_approvals_share_application_store(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    try:
        store = VoodooStoreExecutionStore()
        execution = Execution(trace_id="trace-2")
        store.save(execution)

        store.record_artifact(
            {
                "id": "artifact-1",
                "execution_id": execution.id,
                "checksum": "abc",
                "metadata": {"kind": "report"},
            }
        )
        assert store.list_artifacts(execution.id)[0]["id"] == "artifact-1"

        now = datetime.now(UTC)
        approval = SimpleNamespace(
            id="approval-1",
            execution_id=execution.id,
            trace_id=execution.trace_id,
            capability="deploy",
            question="Deploy?",
            requested_by="agent:test",
            status=SimpleNamespace(value="pending"),
            decided_by=None,
            decided_at=None,
            reason=None,
            created_at=now,
            participant="human:operator",
        )
        store.save_approval(approval)

        loaded = store.load_approval(execution.id)
        assert loaded is not None
        assert loaded["id"] == "approval-1"
        assert loaded["participant"] == "human:operator"
        assert [item["id"] for item in store.load_approvals(pending_only=True)] == [
            "approval-1"
        ]
    finally:
        bind_active_runtime_store(None)
        runtime.stop()
