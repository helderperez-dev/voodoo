"""Workflow — composable multi-step orchestration.

A :class:`Workflow` coordinates Tasks (and other compute participants)
under the Voodoo runtime. It is *not* a separate execution engine: every
strategy compiles into the same Intent → Capability → Execution → Effect →
State pipeline via :class:`~voodoo.runtime.task.Task`.

Workflow durability checkpoints orchestration progress only. Canonical
Executions remain owned by :class:`ExecutionEngine`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from voodoo.primitives.intent import Intent
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.engine import engine as default_engine
from voodoo.runtime.errors import WorkflowFailure
from voodoo.runtime.execution import Execution
from voodoo.runtime.task import Task, TaskStatus
from voodoo.runtime.workflow_store import WorkflowStore

__all__ = ["WorkflowStrategy", "Workflow", "WorkflowRun"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowStrategy(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    ITERATIVE = "iterative"
    DELEGATED = "delegated"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE = "adaptive"


@dataclass
class WorkflowRun:
    """Result and resumable orchestration checkpoint for a Workflow."""

    workflow_id: str
    status: str = "running"
    task_results: dict[str, Any] = field(default_factory=dict)
    task_statuses: dict[str, str] = field(default_factory=dict)
    executions: list[Execution] = field(default_factory=list)
    execution_ids: list[str] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
    error: str | None = None
    iterations: int = 0
    updated_at: str = field(default_factory=_now_iso)

    def describe(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "task_results": dict(self.task_results),
            "task_statuses": dict(self.task_statuses),
            "execution_ids": list(self.execution_ids),
            "completed_steps": list(self.completed_steps),
            "error": self.error,
            "iterations": self.iterations,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_checkpoint(cls, payload: dict[str, Any]) -> WorkflowRun:
        return cls(
            workflow_id=str(payload["workflow_id"]),
            status=str(payload.get("status", "running")),
            task_results=dict(payload.get("task_results") or {}),
            task_statuses=dict(payload.get("task_statuses") or {}),
            execution_ids=[str(value) for value in payload.get("execution_ids") or []],
            completed_steps=[
                str(value) for value in payload.get("completed_steps") or []
            ],
            error=payload.get("error"),
            iterations=int(payload.get("iterations") or 0),
            updated_at=str(payload.get("updated_at") or _now_iso()),
        )


@dataclass
class Workflow:
    """A composable execution plan that coordinates Tasks."""

    tasks: list[Task] = field(default_factory=list)
    strategy: WorkflowStrategy = WorkflowStrategy.SEQUENTIAL
    name: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    until: Callable[[WorkflowRun], bool] | None = None
    max_iterations: int = 1
    store: WorkflowStore | None = None

    def _validate_topology(self) -> None:
        """Validate task identity, dependency membership, and acyclicity."""
        names = [task.name for task in self.tasks]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(
                "Workflow task names must be unique; duplicate(s): "
                + ", ".join(duplicates)
            )

        members = {id(task) for task in self.tasks}
        for task in self.tasks:
            missing = [dep.name for dep in task.depends_on if id(dep) not in members]
            if missing:
                raise ValueError(
                    f"Task {task.name!r} depends on task(s) not in this workflow: "
                    + ", ".join(missing)
                )

        done: set[str] = set()
        remaining = list(self.tasks)
        while remaining:
            ready = [
                task
                for task in remaining
                if all(dep.name in done for dep in task.depends_on)
            ]
            if not ready:
                cycle = ", ".join(task.name for task in remaining)
                raise ValueError(f"Workflow dependency cycle detected among: {cycle}")
            for task in ready:
                done.add(task.name)
                remaining.remove(task)

    def _topological_order(self) -> list[Task]:
        """Return tasks in dependency order using Kahn's algorithm."""
        order: list[Task] = []
        done: set[str] = set()
        remaining = list(self.tasks)
        while remaining:
            ready = [
                task
                for task in remaining
                if all(dep.name in done for dep in task.depends_on)
            ]
            if not ready:
                cycle = ", ".join(task.name for task in remaining)
                raise ValueError(f"Workflow dependency cycle detected among: {cycle}")
            for task in ready:
                order.append(task)
                done.add(task.name)
                remaining.remove(task)
        return order

    def _ready_tasks(self, done: set[str]) -> list[Task]:
        return [
            task
            for task in self.tasks
            if task.name not in done
            and all(dependency.name in done for dependency in task.depends_on)
        ]

    async def run(
        self,
        *,
        engine: ExecutionEngine = default_engine,
        parent: ExecutionContext | None = None,
        context: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Execute a new Workflow run according to its strategy."""
        run = WorkflowRun(workflow_id=self.id)
        self._persist(run)
        return await self._execute_run(
            run, engine=engine, parent=parent, context=context
        )

    async def resume(
        self,
        *,
        engine: ExecutionEngine = default_engine,
        parent: ExecutionContext | None = None,
        context: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Resume this Workflow definition from its latest durable checkpoint.

        The caller supplies the same Workflow definition (Tasks/compute functions),
        while Store supplies orchestration progress. Completed checkpoint steps are
        not executed a second time.
        """
        if self.store is None:
            raise RuntimeError("Workflow.resume() requires a WorkflowStore")
        payload = self.store.load(self.id)
        if payload is None:
            raise KeyError(self.id)
        run = WorkflowRun.from_checkpoint(payload)
        if run.status == "completed":
            return run
        if run.status in {"failed", "cancelled"}:
            raise RuntimeError(
                f"workflow {self.id} is terminal and cannot resume: {run.status}"
            )
        run.status = "running"
        run.error = None
        self._persist(run)
        return await self._execute_run(
            run, engine=engine, parent=parent, context=context
        )

    async def _execute_run(
        self,
        run: WorkflowRun,
        *,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        context: dict[str, Any] | None,
    ) -> WorkflowRun:
        try:
            if self.strategy is not WorkflowStrategy.HIERARCHICAL:
                self._validate_topology()
            await self._dispatch(run, engine, parent, context)
            run.status = "completed"
            run.error = None
            self._persist(run)
        except Exception as error:
            run.status = "failed"
            run.error = str(error)
            self._persist(run)
            if isinstance(error, WorkflowFailure):
                raise
            raise WorkflowFailure(
                f"Workflow '{self.name or self.id}' failed: {error}",
                context={"workflow_id": self.id, "strategy": self.strategy.value},
            ) from error

        await self._emit(
            "workflow.completed",
            {"workflow_id": self.id, "status": run.status, "tasks": run.task_statuses},
        )
        return run

    async def _dispatch(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        context: dict[str, Any] | None,
    ) -> None:
        handlers: dict[
            WorkflowStrategy,
            Callable[
                [WorkflowRun, ExecutionEngine, ExecutionContext | None, dict | None],
                Awaitable[None],
            ],
        ] = {
            WorkflowStrategy.SEQUENTIAL: self._run_sequential,
            WorkflowStrategy.PARALLEL: self._run_parallel,
            WorkflowStrategy.CONDITIONAL: self._run_conditional,
            WorkflowStrategy.ITERATIVE: self._run_iterative,
            WorkflowStrategy.DELEGATED: self._run_delegated,
            WorkflowStrategy.HIERARCHICAL: self._run_hierarchical,
            WorkflowStrategy.ADAPTIVE: self._run_adaptive,
        }
        handler = handlers.get(self.strategy, self._run_sequential)
        await handler(run, engine, parent, context)

    async def _run_sequential(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
        *,
        step_prefix: str = "task",
    ) -> None:
        results: dict[str, Any] = dict(ctx or {})
        results.update(run.task_results)
        for task in self._topological_order():
            step = f"{step_prefix}:{task.name}"
            if step in run.completed_steps:
                continue
            execution = await task.run(
                context=ctx, engine=engine, parent=parent, results=results
            )
            self._record_execution(run, execution)
            run.task_statuses[task.name] = task.status.value
            run.task_results[task.name] = task.result
            results[task.name] = task.result
            engine.checkpoint(execution)
            if task.status is TaskStatus.FAILED:
                self._persist(run)
                raise WorkflowFailure(
                    f"Task '{task.name}' failed", context={"task": task.name}
                )
            run.completed_steps.append(step)
            self._persist(run)

    async def _run_parallel(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        await self._emit(
            "workflow.started", {"workflow_id": self.id, "strategy": "parallel"}
        )
        results: dict[str, Any] = dict(ctx or {})
        results.update(run.task_results)
        done = {
            task.name
            for task in self.tasks
            if f"task:{task.name}" in run.completed_steps
        }

        while len(done) < len(self.tasks):
            ready = self._ready_tasks(done)
            if not ready:
                unfinished = ", ".join(
                    task.name for task in self.tasks if task.name not in done
                )
                raise WorkflowFailure(
                    f"Workflow cannot make progress; unresolved tasks: {unfinished}",
                    context={"unfinished": unfinished},
                )
            coroutines = [
                task.run(context=ctx, engine=engine, parent=parent, results=results)
                for task in ready
            ]
            executions = await asyncio.gather(*coroutines, return_exceptions=True)
            for task, execution in zip(ready, executions, strict=True):
                if isinstance(execution, Exception):
                    run.task_statuses[task.name] = TaskStatus.FAILED.value
                    run.task_results[task.name] = None
                    self._persist(run)
                    raise WorkflowFailure(
                        f"Task '{task.name}' failed: {execution}",
                        context={"task": task.name},
                    )
                self._record_execution(run, execution)
                run.task_statuses[task.name] = task.status.value
                run.task_results[task.name] = task.result
                results[task.name] = task.result
                done.add(task.name)
                engine.checkpoint(execution)
                if task.status is TaskStatus.FAILED:
                    self._persist(run)
                    raise WorkflowFailure(
                        f"Task '{task.name}' failed", context={"task": task.name}
                    )
                step = f"task:{task.name}"
                if step not in run.completed_steps:
                    run.completed_steps.append(step)
                self._persist(run)

    async def _run_conditional(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        await self._emit(
            "workflow.started", {"workflow_id": self.id, "strategy": "conditional"}
        )
        await self._run_sequential(run, engine, parent, ctx)

    async def _run_iterative(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        await self._emit(
            "workflow.started", {"workflow_id": self.id, "strategy": "iterative"}
        )
        iteration = max(run.iterations - 1, 0) if run.iterations else 0
        while iteration < self.max_iterations:
            run.iterations = iteration + 1
            self._persist(run)
            await self._run_sequential(
                run,
                engine,
                parent,
                ctx,
                step_prefix=f"iteration:{run.iterations}",
            )
            if self.until is not None and self.until(run):
                return
            iteration += 1

    async def _run_delegated(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        await self._emit(
            "workflow.started", {"workflow_id": self.id, "strategy": "delegated"}
        )
        results: dict[str, Any] = dict(ctx or {})
        results.update(run.task_results)
        for task in self._topological_order():
            step = f"task:{task.name}"
            if step in run.completed_steps:
                continue
            child_parent = parent or ExecutionContext(actor="workflow")
            execution = await task.run(
                context=ctx, engine=engine, parent=child_parent, results=results
            )
            self._record_execution(run, execution)
            run.task_statuses[task.name] = task.status.value
            run.task_results[task.name] = task.result
            results[task.name] = task.result
            run.completed_steps.append(step)
            self._persist(run)

    async def _run_hierarchical(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        await self._emit(
            "workflow.started", {"workflow_id": self.id, "strategy": "hierarchical"}
        )
        results: dict[str, Any] = dict(ctx or {})
        results.update(run.task_results)
        for item in self.tasks:
            key = item.name or item.id if isinstance(item, Workflow) else item.name
            step = f"item:{key}"
            if step in run.completed_steps:
                continue
            if isinstance(item, Workflow):
                sub_run = await item.run(engine=engine, parent=parent, context=ctx)
                run.task_statuses[key] = sub_run.status
                run.task_results[key] = sub_run.task_results
                run.executions.extend(sub_run.executions)
                run.execution_ids.extend(
                    value
                    for value in sub_run.execution_ids
                    if value not in run.execution_ids
                )
            else:
                execution = await item.run(
                    context=ctx, engine=engine, parent=parent, results=results
                )
                self._record_execution(run, execution)
                run.task_statuses[item.name] = item.status.value
                run.task_results[item.name] = item.result
                results[item.name] = item.result
            run.completed_steps.append(step)
            self._persist(run)

    async def _run_adaptive(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        """Run the planner/supervisor strategy using declared capabilities."""
        if "adaptive:aggregate" in run.completed_steps:
            return
        await self._emit(
            "workflow.started", {"workflow_id": self.id, "strategy": "adaptive"}
        )
        from voodoo.runtime.adaptive import AdaptiveSupervisor
        from voodoo.runtime.planner import ComputeParticipant, Planner

        planner = Planner(engine=engine)
        for task in self._topological_order():
            kind = (
                "human"
                if task.human
                else ("agent" if task.agent is not None else "compute")
            )
            planner.register(
                ComputeParticipant(
                    name=task.name,
                    kind=kind,
                    capabilities=list(task.capabilities),
                    compute=task.compute,
                    agent=task.agent,
                )
            )
            if task.approval_capability:
                planner.require_approval(task.approval_capability)

        intent = self._build_adaptive_intent(ctx)
        supervisor = AdaptiveSupervisor(planner, engine=engine)
        adaptive_run = await supervisor.run(intent)
        run.task_statuses["_adaptive"] = adaptive_run.status
        run.task_results["_adaptive"] = adaptive_run.result
        if adaptive_run.execution_id:
            if adaptive_run.execution_id not in run.execution_ids:
                run.execution_ids.append(adaptive_run.execution_id)
        if adaptive_run.error:
            run.error = adaptive_run.error
            self._persist(run)
            raise WorkflowFailure(
                f"Adaptive workflow failed: {adaptive_run.error}",
                context={"decisions": adaptive_run.decisions},
            )
        run.completed_steps.append("adaptive:aggregate")
        self._persist(run)

    def _build_adaptive_intent(self, ctx: dict | None) -> Intent:
        """Build an aggregate Intent carrying every task's capabilities."""
        intent = Intent(name=f"workflow:{self.name or self.id}", params=dict(ctx or {}))
        seen: set[str] = set()
        for task in self.tasks:
            for capability in task.capabilities:
                if capability not in seen:
                    seen.add(capability)
                    intent.require(capability)
        return intent

    def _record_execution(self, run: WorkflowRun, execution: Execution) -> None:
        run.executions.append(execution)
        if execution.id not in run.execution_ids:
            run.execution_ids.append(execution.id)

    def _persist(self, run: WorkflowRun) -> None:
        if self.store is None:
            return
        run.updated_at = _now_iso()
        self.store.save(self.id, run.describe())

    async def _emit(self, event: str, payload: dict[str, Any]) -> None:
        try:
            from voodoo.mesh import mesh

            await mesh.broadcast(event, payload)
        except Exception:
            pass

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "strategy": self.strategy.value,
            "tasks": [task.describe() for task in self.tasks],
        }
