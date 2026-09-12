"""Workflow — composable multi-step orchestration.

A :class:`Workflow` coordinates Tasks (and other compute participants)
under the Voodoo runtime. It is *not* a separate execution engine: every
strategy compiles into the same Intent → Capability → Execution → Effect →
State pipeline via :class:`~voodoo.runtime.task.Task`.

Supported strategies:

    sequential
    parallel        (dependency-aware)
    conditional     (per-task condition)
    iterative       (repeat until predicate / max iterations)
    delegated       (tasks delegate to sub-agents via child executions)
    hierarchical    (nested workflows)
    adaptive        (planner-driven)

``Crew`` is intentionally **not** used — Voodoo-native terminology only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from voodoo.primitives.intent import Intent
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.engine import engine as default_engine
from voodoo.runtime.errors import WorkflowFailure
from voodoo.runtime.execution import Execution
from voodoo.runtime.task import Task, TaskStatus

__all__ = ["WorkflowStrategy", "Workflow", "WorkflowRun"]


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
    """Result of running a :class:`Workflow`."""

    workflow_id: str
    status: str = "running"
    task_results: dict[str, Any] = field(default_factory=dict)
    task_statuses: dict[str, str] = field(default_factory=dict)
    executions: list[Execution] = field(default_factory=list)
    error: str | None = None
    iterations: int = 0


@dataclass
class Workflow:
    """A composable execution plan that coordinates Tasks."""

    tasks: list[Task] = field(default_factory=list)
    strategy: WorkflowStrategy = WorkflowStrategy.SEQUENTIAL
    name: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    until: Callable[[WorkflowRun], bool] | None = None
    max_iterations: int = 1

    # -- topology ----------------------------------------------------------

    def _validate_topology(self) -> None:
        """Validate task identity, dependency membership, and acyclicity.

        Task names are durable result/dependency keys, so they must be unique.
        Dependencies must belong to this workflow. Cycles are rejected before
        any task executes instead of silently running declaration order or
        allowing a partial parallel run to look successful.
        """
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

    # -- execution ---------------------------------------------------------

    async def run(
        self,
        *,
        engine: ExecutionEngine = default_engine,
        parent: ExecutionContext | None = None,
        context: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Execute the workflow according to its strategy."""
        run = WorkflowRun(workflow_id=self.id)
        try:
            if self.strategy is not WorkflowStrategy.HIERARCHICAL:
                self._validate_topology()
            await self._dispatch(run, engine, parent, context)
            run.status = "completed"
        except Exception as error:  # noqa: BLE001
            run.status = "failed"
            run.error = str(error)
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
        """Dispatch one validated workflow to its strategy implementation."""
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

    # -- strategies --------------------------------------------------------

    async def _run_sequential(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        results: dict[str, Any] = dict(ctx or {})
        for task in self._topological_order():
            execution = await task.run(
                context=ctx, engine=engine, parent=parent, results=results
            )
            run.executions.append(execution)
            run.task_statuses[task.name] = task.status.value
            run.task_results[task.name] = task.result
            results[task.name] = task.result
            engine.checkpoint(execution)
            if task.status is TaskStatus.FAILED:
                raise WorkflowFailure(
                    f"Task '{task.name}' failed", context={"task": task.name}
                )

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
        done: set[str] = set()

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
                # gather(return_exceptions=True) is typed as Execution |
                # BaseException. Narrow the full exception base so mypy and
                # runtime behavior agree (CancelledError is a BaseException).
                if isinstance(execution, BaseException):
                    run.task_statuses[task.name] = TaskStatus.FAILED.value
                    run.task_results[task.name] = None
                    raise WorkflowFailure(
                        f"Task '{task.name}' failed: {execution}",
                        context={"task": task.name},
                    )
                run.executions.append(execution)
                run.task_statuses[task.name] = task.status.value
                run.task_results[task.name] = task.result
                results[task.name] = task.result
                done.add(task.name)
                engine.checkpoint(execution)
                if task.status is TaskStatus.FAILED:
                    raise WorkflowFailure(
                        f"Task '{task.name}' failed", context={"task": task.name}
                    )

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
        results: dict[str, Any] = dict(ctx or {})
        for task in self._topological_order():
            execution = await task.run(
                context=ctx, engine=engine, parent=parent, results=results
            )
            run.executions.append(execution)
            run.task_statuses[task.name] = task.status.value
            run.task_results[task.name] = task.result
            results[task.name] = task.result

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
        iteration = 0
        while iteration < self.max_iterations:
            run.iterations = iteration + 1
            await self._run_sequential(run, engine, parent, ctx)
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
        for task in self._topological_order():
            child_parent = parent or ExecutionContext(actor="workflow")
            execution = await task.run(
                context=ctx, engine=engine, parent=child_parent, results=results
            )
            run.executions.append(execution)
            run.task_statuses[task.name] = task.status.value
            run.task_results[task.name] = task.result
            results[task.name] = task.result

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
        for item in self.tasks:
            if isinstance(item, Workflow):
                sub_run = await item.run(engine=engine, parent=parent, context=ctx)
                run.task_statuses[item.name or item.id] = sub_run.status
                run.task_results[item.name or item.id] = sub_run.task_results
                run.executions.extend(sub_run.executions)
            else:
                execution = await item.run(
                    context=ctx, engine=engine, parent=parent, results=results
                )
                run.executions.append(execution)
                run.task_statuses[item.name] = item.status.value
                run.task_results[item.name] = item.result
                results[item.name] = item.result

    async def _run_adaptive(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        """Run the planner/supervisor strategy using declared capabilities."""
        await self._emit(
            "workflow.started", {"workflow_id": self.id, "strategy": "adaptive"}
        )
        from voodoo.runtime.adaptive import AdaptiveSupervisor
        from voodoo.runtime.planner import ComputeParticipant, Planner

        planner = Planner(engine=engine)
        for task in self._topological_order():
            kind: Literal["human", "agent", "compute"] = (
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
        if adaptive_run.error:
            run.error = adaptive_run.error
            raise WorkflowFailure(
                f"Adaptive workflow failed: {adaptive_run.error}",
                context={"decisions": adaptive_run.decisions},
            )

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

    # -- mesh --------------------------------------------------------------

    async def _emit(self, event: str, payload: dict[str, Any]) -> None:
        try:
            from voodoo.mesh import mesh

            await mesh.broadcast(event, payload)
        except Exception:  # noqa: BLE001
            pass

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "strategy": self.strategy.value,
            "tasks": [task.describe() for task in self.tasks],
        }
