"""Regression tests for runtime correctness invariants.

These tests cover failure paths that are easy to miss in happy-path runtime
coverage: durable timing metadata and invalid workflow dependency graphs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from voodoo.runtime import ComputeResult, Task, Workflow, WorkflowStrategy
from voodoo.runtime.errors import WorkflowFailure
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.storage.execution import SQLiteExecutionStore


def test_execution_duration_survives_store_round_trip(tmp_path) -> None:
    """Persisted timestamps remain sufficient to calculate duration."""
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    completed = started + timedelta(seconds=2.5)
    execution = Execution(
        trace_id="trace-duration",
        status=ExecutionStatus.COMPLETED,
        started_at=started,
        completed_at=completed,
    )

    store = SQLiteExecutionStore(tmp_path / "runtime.db")
    store.save(execution)
    restored = next(item for item in store.load_all() if item.id == execution.id)
    store.close()

    assert restored.duration_seconds == pytest.approx(2.5)
    assert restored.describe()["duration_seconds"] == pytest.approx(2.5)


@pytest.mark.asyncio
async def test_sequential_workflow_rejects_cycle_before_compute() -> None:
    calls: list[str] = []

    async def compute_a(ctx):
        calls.append("a")
        return ComputeResult(value="a")

    async def compute_b(ctx):
        calls.append("b")
        return ComputeResult(value="b")

    task_a = Task(name="a", compute=compute_a)
    task_b = Task(name="b", compute=compute_b, depends_on=[task_a])
    task_a.depends_on = [task_b]

    workflow = Workflow(tasks=[task_a, task_b])
    with pytest.raises(WorkflowFailure, match="cycle"):
        await workflow.run()

    assert calls == []


@pytest.mark.asyncio
async def test_parallel_workflow_rejects_cycle_instead_of_completing_partial() -> None:
    task_a = Task(name="a")
    task_b = Task(name="b", depends_on=[task_a])
    task_a.depends_on = [task_b]

    workflow = Workflow(
        tasks=[task_a, task_b],
        strategy=WorkflowStrategy.PARALLEL,
    )
    with pytest.raises(WorkflowFailure, match="cycle"):
        await workflow.run()


@pytest.mark.asyncio
async def test_workflow_rejects_dependency_not_in_workflow() -> None:
    external = Task(name="external")
    dependent = Task(name="dependent", depends_on=[external])
    workflow = Workflow(tasks=[dependent])

    with pytest.raises(WorkflowFailure, match="not in this workflow"):
        await workflow.run()


@pytest.mark.asyncio
async def test_workflow_rejects_duplicate_task_names() -> None:
    first = Task(name="same")
    second = Task(name="same")
    workflow = Workflow(tasks=[first, second])

    with pytest.raises(WorkflowFailure, match="unique"):
        await workflow.run()
