"""Sprint 28.8 acceptance for Voodoo Store-backed Execution persistence."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    from voodoo.observability import telemetry_store

    runtime = _runtime(tmp_path)
    try:
        store = VoodooStoreExecutionStore()
        span_start = len(telemetry_store.metrics["spans"])
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

        native_record = runtime.provider.native.get_record(
            b"runtime.executions", execution.id.encode("utf-8")
        )
        assert native_record is not None
        assert json.loads(bytes(native_record[1]))["_schema_version"] == 1

        timeline = store.timeline(execution.id)
        assert len(runtime.provider.native.read_stream(b"runtime.execution.events", 0, 10)) == 3
        assert [event["event_type"] for event in timeline] == [
            "execution.created",
            "execution.started",
            "execution.completed",
        ]
        assert [event["sequence"] for event in timeline] == [1, 2, 3]
        spans = telemetry_store.metrics["spans"][span_start:]
        assert [span["name"] for span in spans if span["name"].startswith("store.execution.")] == [
            "store.execution.save",
            "store.execution.save",
            "store.execution.save",
            "store.execution.load",
        ]
        assert all(span["attributes"] == {"provider": "voodoo"} for span in spans if span["name"].startswith("store.execution."))
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_execution_artifacts_and_approvals_share_application_store(
    tmp_path: Path,
) -> None:
    from voodoo.observability import telemetry_store

    runtime = _runtime(tmp_path)
    try:
        store = VoodooStoreExecutionStore()
        span_start = len(telemetry_store.metrics["spans"])
        execution = Execution(trace_id="trace-2")
        store.save(execution)

        native = runtime.provider.native
        native.put(
            b"runtime:execution:artifact:artifact-1",
            json.dumps(
                {
                    "id": "artifact-1",
                    "execution_id": execution.id,
                    "checksum": "old",
                }
            ).encode(),
        )
        store.record_artifact(
            {
                "id": "artifact-1",
                "execution_id": execution.id,
                "checksum": "abc",
                "metadata": {"kind": "report"},
            }
        )
        assert store.list_artifacts(execution.id)[0]["id"] == "artifact-1"
        assert native.get(b"runtime:execution:artifact:artifact-1") is None

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
        native.put(
            b"runtime:execution:approval:approval-1",
            json.dumps(
                {
                    "id": "approval-1",
                    "execution_id": execution.id,
                    "status": "pending",
                }
            ).encode(),
        )
        store.save_approval(approval)

        loaded = store.load_approval(execution.id)
        assert loaded is not None
        assert loaded["id"] == "approval-1"
        assert loaded["participant"] == "human:operator"
        assert native.get(b"runtime:execution:approval:approval-1") is None
        assert [item["id"] for item in store.load_approvals(pending_only=True)] == [
            "approval-1"
        ]
        spans = telemetry_store.metrics["spans"][span_start:]
        names = [
            span["name"]
            for span in spans
            if span["name"].startswith("store.execution.")
        ]
        assert names == [
            "store.execution.save",
            "store.execution.record_artifact",
            "store.execution.save_approval",
        ]
        assert all(
            span["attributes"] == {"provider": "voodoo"}
            for span in spans
            if span["name"].startswith("store.execution.")
        )
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_execution_store_reads_legacy_materialized_records(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    try:
        store = VoodooStoreExecutionStore()
        execution = Execution(trace_id="legacy-trace", actor="agent:legacy")
        legacy = execution.model_dump(mode="json")
        native = runtime.provider.native
        native.put(
            b"runtime:execution:data:" + execution.id.encode("utf-8"),
            json.dumps(legacy).encode("utf-8"),
        )

        loaded = store.load_all()
        assert [item.id for item in loaded] == [execution.id]
        store.save(execution)
        assert native.get_record(
            b"runtime.executions", execution.id.encode("utf-8")
        ) is not None
        assert native.get(
            b"runtime:execution:data:" + execution.id.encode("utf-8")
        ) is None
        future = dict(legacy)
        future["_schema_version"] = 99
        native.put(
            b"runtime:execution:data:future-execution",
            json.dumps(future).encode("utf-8"),
        )
        with pytest.raises(ValueError, match="unsupported execution schema"):
            store.load_all()
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_execution_store_migrates_legacy_events_to_native_stream(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    try:
        store = VoodooStoreExecutionStore()
        native = runtime.provider.native
        event = {
            "sequence": 1,
            "execution_id": "legacy-execution",
            "event_type": "execution.created",
            "payload": {"id": "legacy-execution"},
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        native.put(
            b"runtime:execution:event:00000000000000000001",
            json.dumps(event).encode(),
        )
        assert store.timeline("legacy-execution") == [event]
        assert native.get(b"runtime:execution:event:00000000000000000001") is None
        assert native.read_stream(b"runtime.execution.events", 0, 10) == [
            (0, json.dumps(event, separators=(",", ":")).encode())
        ]
        # A second read is a no-op and does not duplicate stream history.
        assert store.list_events() == [event]
        assert len(native.read_stream(b"runtime.execution.events", 0, 10)) == 1
    finally:
        bind_active_runtime_store(None)
        runtime.stop()
