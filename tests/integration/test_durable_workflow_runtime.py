from __future__ import annotations

from pathlib import Path

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
