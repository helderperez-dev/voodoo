from __future__ import annotations

import json
from pathlib import Path

import pytest

from voodoo.runtime import (
    ComputeResult,
    ExecutionEngine,
    RuntimeStore,
    StoreConfig,
    Task,
    VoodooStoreWorkflowStore,
    Workflow,
    WorkflowStrategy,
)


def test_voodoo_store_workflow_checkpoints_share_application_store(tmp_path: Path):
    path = tmp_path / "application.vstore"
    runtime_store = RuntimeStore(StoreConfig(path=path))
    runtime_store.start()
    store = VoodooStoreWorkflowStore(runtime_store)
    running = {
        "workflow_id": "wf-running",
        "status": "running",
        "task_results": {"a": "A"},
        "task_statuses": {"a": "completed"},
        "execution_ids": ["ex-a"],
        "completed_steps": ["task:a"],
        "iterations": 0,
        "error": None,
        "updated_at": "2026-09-14T00:00:00+00:00",
    }
    completed = {
        "workflow_id": "wf-done",
        "status": "completed",
        "task_results": {},
        "task_statuses": {},
        "execution_ids": [],
        "completed_steps": [],
        "iterations": 0,
        "error": None,
        "updated_at": "2026-09-14T00:01:00+00:00",
    }

    store.save("wf-running", running)
    store.save("wf-done", completed)
    assert store.provider == "voodoo"
    assert store.path == path
    index_record = runtime_store.provider.native.get_record(
        b"runtime.workflow_index", b"wf-running"
    )
    assert index_record is not None
    index_payload = json.loads(bytes(index_record[1]).decode("utf-8"))
    native_id = bytes.fromhex(index_payload["native_id"])
    assert runtime_store.provider.native.get(store._native_index_key("wf-running")) is None
    assert native_id is not None
    native_instance = runtime_store.provider.native.get_workflow(bytes(native_id))
    assert native_instance is not None
    assert native_instance["status"] == "running"
    assert store.load("wf-running") == running
    assert store.load_unfinished() == [running]
    store.close()
    assert runtime_store.started
    runtime_store.stop()

    reopened_runtime = RuntimeStore(StoreConfig(path=path))
    reopened_runtime.start()
    reopened = VoodooStoreWorkflowStore(reopened_runtime)
    assert reopened.load("wf-running") == running
    assert reopened.load_unfinished() == [running]
    reopened_runtime.stop()


def test_workflow_checkpoint_codec_migrates_legacy_and_rejects_future_schema(
    tmp_path: Path,
):
    path = tmp_path / "versioned-workflows.vstore"
    runtime_store = RuntimeStore(StoreConfig(path=path))
    runtime_store.start()
    store = VoodooStoreWorkflowStore(runtime_store)
    legacy = {
        "workflow_id": "legacy",
        "status": "running",
        "task_results": {},
        "task_statuses": {},
        "updated_at": "2026-09-14T00:00:00+00:00",
    }
    native = runtime_store.provider.native
    native.put(store._key("legacy"), json.dumps(legacy).encode("utf-8"))
    assert store.load("legacy") == legacy

    future = dict(legacy)
    future["_schema_version"] = 99
    native.put(store._key("future"), json.dumps(future).encode("utf-8"))
    with pytest.raises(ValueError, match="newer than supported"):
        store.load("future")
    mismatch = dict(legacy)
    mismatch["workflow_id"] = "different"
    native.put(store._key("mismatch"), json.dumps(mismatch).encode("utf-8"))
    with pytest.raises(ValueError, match="identity"):
        store.load("mismatch")
    native_id = native.create_workflow(
        b"voodoo.workflow", b"checkpoint", b'{"workflow_id":"native-future"}', 1
    )
    native.put(store._native_index_key("native-future"), native_id)
    native.set_workflow_step(
        native_id,
        b"checkpoint",
        json.dumps(
            {"workflow_id": "native-future", "_schema_version": 99}
        ).encode(),
        2,
    )
    with pytest.raises(ValueError, match="newer than supported"):
        store.load("native-future")
    runtime_store.stop()


def test_existing_native_workflow_index_migrates_to_collection(tmp_path: Path):
    path = tmp_path / "migrate-workflow-index.vstore"
    runtime_store = RuntimeStore(StoreConfig(path=path))
    runtime_store.start()
    store = VoodooStoreWorkflowStore(runtime_store)
    native = runtime_store.provider.native
    native_id = native.create_workflow(
        b"voodoo.workflow",
        b"checkpoint",
        json.dumps({"workflow_id": "legacy-index", "status": "running"}).encode(),
        1,
    )
    native.put(store._native_index_key("legacy-index"), native_id)

    store.save(
        "legacy-index",
        {
            "workflow_id": "legacy-index",
            "status": "running",
            "task_results": {},
            "task_statuses": {},
            "updated_at": "2026-09-14T00:00:00+00:00",
        },
    )

    record = native.get_record(b"runtime.workflow_index", b"legacy-index")
    assert record is not None
    assert native.get(store._native_index_key("legacy-index")) is None
    runtime_store.stop()


async def test_sequential_workflow_resume_skips_checkpointed_steps(tmp_path: Path):
    path = tmp_path / "application.vstore"
    runtime_store = RuntimeStore(StoreConfig(path=path))
    runtime_store.start()
    store = VoodooStoreWorkflowStore(runtime_store)
    calls = {"a": 0, "b": 0}

    def compute_a(ctx):
        calls["a"] += 1
        return ComputeResult(value="A")

    def compute_b(ctx):
        calls["b"] += 1
        return ComputeResult(value="B")

    a = Task(name="a", compute=compute_a)
    b = Task(name="b", compute=compute_b, depends_on=[a])
    workflow = Workflow(
        id="wf-resume",
        tasks=[a, b],
        strategy=WorkflowStrategy.SEQUENTIAL,
        store=store,
    )
    store.save(
        workflow.id,
        {
            "workflow_id": workflow.id,
            "status": "running",
            "task_results": {"a": "A"},
            "task_statuses": {"a": "completed"},
            "execution_ids": ["existing-execution"],
            "completed_steps": ["task:a"],
            "iterations": 0,
            "error": None,
            "updated_at": "2026-09-14T00:00:00+00:00",
        },
    )

    run = await workflow.resume(engine=ExecutionEngine())

    assert run.status == "completed"
    assert calls == {"a": 0, "b": 1}
    assert run.task_results == {"a": "A", "b": "B"}
    assert run.completed_steps == ["task:a", "task:b"]
    assert run.execution_ids[0] == "existing-execution"
    assert len(run.execution_ids) == 2
    persisted = store.load(workflow.id)
    assert persisted is not None
    assert persisted["status"] == "completed"
    runtime_store.stop()


async def test_iterative_workflow_resume_uses_iteration_checkpoint(tmp_path: Path):
    path = tmp_path / "application.vstore"
    runtime_store = RuntimeStore(StoreConfig(path=path))
    runtime_store.start()
    store = VoodooStoreWorkflowStore(runtime_store)
    calls = {"tick": 0}

    def tick(ctx):
        calls["tick"] += 1
        return ComputeResult(value=2)

    task = Task(name="tick", compute=tick)
    workflow = Workflow(
        id="wf-iterative",
        tasks=[task],
        strategy=WorkflowStrategy.ITERATIVE,
        until=lambda run: run.task_results.get("tick", 0) >= 2,
        max_iterations=3,
        store=store,
    )
    store.save(
        workflow.id,
        {
            "workflow_id": workflow.id,
            "status": "running",
            "task_results": {"tick": 1},
            "task_statuses": {"tick": "completed"},
            "execution_ids": ["iteration-1-execution"],
            "completed_steps": ["iteration:1:tick"],
            "iterations": 1,
            "error": None,
            "updated_at": "2026-09-14T00:00:00+00:00",
        },
    )

    run = await workflow.resume(engine=ExecutionEngine())

    assert run.status == "completed"
    assert run.iterations == 2
    assert calls["tick"] == 1
    assert "iteration:1:tick" in run.completed_steps
    assert "iteration:2:tick" in run.completed_steps
    runtime_store.stop()
