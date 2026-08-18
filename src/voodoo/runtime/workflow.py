"""Workflow — composable multi-step orchestration.

A :class:`Workflow` coordinates Tasks (and other compute participants)
under the Voodoo runtime. It is *not* a separate execution engine: every
strategy compiles into the same Intent → Capability → Compute → Effect →
State pipeline via :class:`~voodoo.runtime.task.Task`.

Supported strategies (implemented incrementally, per the spec order):

    sequential
    parallel        (dependency-aware)
    conditional     (per-task condition)
    iterative       (repeat until predicate / max iterations)
    delegated       (tasks delegate to sub-agents via child executions)
    hierarchical    (nested workflows)
    adaptive        (planner-driven; future milestone)

``Crew`` is intentionally **not** used — Voodoo-native terminology only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
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
    """The result of running a :class:`Workflow`.

    Captures per-task results (keyed by task name), the executions
    produced, and overall status — making the workflow inspectable and
    durable enough to recover from interruption.
    """

    workflow_id: str
    status: str = "running"
    task_results: dict[str, Any] = field(default_factory=dict)
    task_statuses: dict[str, str] = field(default_factory=dict)
    executions: list[Execution] = field(default_factory=list)
    error: str | None = None
    iterations: int = 0


@dataclass
class Workflow:
    """A composable execution plan that coordinates Tasks.

    Example
    -------
    ::

        research = Task(name="research", agent=researcher)
        write = Task(name="write", agent=writer, depends_on=[research])
        review = Task(name="review", agent=reviewer, depends_on=[write])

        workflow = Workflow(tasks=[research, write, review])
        run = await workflow.run()
    """

    tasks: list[Task] = field(default_factory=list)
    strategy: WorkflowStrategy = WorkflowStrategy.SEQUENTIAL
    name: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))

    # iterative strategy controls
    until: Callable[[WorkflowRun], bool] | None = None
    max_iterations: int = 1

    # -- topology ----------------------------------------------------------

    def _topological_order(self) -> list[Task]:
        """Return tasks in dependency order (Kahn's algorithm)."""
        order: list[Task] = []
        done: set[str] = set()
        remaining = list(self.tasks)
        # guard against empty
        while remaining:
            progressed = False
            for task in list(remaining):
                if all(d.name in done for d in task.depends_on):
                    order.append(task)
                    done.add(task.name)
                    remaining.remove(task)
                    progressed = True
            if not progressed:
                # cycle — fall back to declared order
                order.extend(remaining)
                break
        return order

    def _ready_tasks(self, done: set[str]) -> list[Task]:
        return [
            t
            for t in self.tasks
            if t.name not in done and all(d.name in done for d in t.depends_on)
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
        strategy = self.strategy

        try:
            if strategy is WorkflowStrategy.SEQUENTIAL:
                await self._run_sequential(run, engine, parent, context)
            elif strategy is WorkflowStrategy.PARALLEL:
                await self._run_parallel(run, engine, parent, context)
            elif strategy is WorkflowStrategy.CONDITIONAL:
                await self._run_conditional(run, engine, parent, context)
            elif strategy is WorkflowStrategy.ITERATIVE:
                await self._run_iterative(run, engine, parent, context)
            elif strategy is WorkflowStrategy.DELEGATED:
                await self._run_delegated(run, engine, parent, context)
            elif strategy is WorkflowStrategy.HIERARCHICAL:
                await self._run_hierarchical(run, engine, parent, context)
            elif strategy is WorkflowStrategy.ADAPTIVE:
                await self._run_adaptive(run, engine, parent, context)
            else:
                # adaptive is a future milestone — fall back to sequential.
                await self._run_sequential(run, engine, parent, context)

            run.status = "completed"
        except Exception as e:  # noqa: BLE001
            run.status = "failed"
            run.error = str(e)
            raise WorkflowFailure(
                f"Workflow '{self.name or self.id}' failed: {e}",
                context={"workflow_id": self.id, "strategy": strategy.value},
            ) from e

        await self._emit(
            "workflow.completed",
            {"workflow_id": self.id, "status": run.status, "tasks": run.task_statuses},
        )
        return run

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
                break
            coros = [
                task.run(context=ctx, engine=engine, parent=parent, results=results)
                for task in ready
            ]
            executions = await asyncio.gather(*coros, return_exceptions=True)
            for task, ex in zip(ready, executions, strict=True):
                if isinstance(ex, Exception):
                    run.task_statuses[task.name] = TaskStatus.FAILED.value
                    run.task_results[task.name] = None
                    raise WorkflowFailure(
                        f"Task '{task.name}' failed: {ex}", context={"task": task.name}
                    )
                run.executions.append(ex)
                run.task_statuses[task.name] = task.status.value
                run.task_results[task.name] = task.result
                results[task.name] = task.result
                done.add(task.name)
                engine.checkpoint(ex)
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
            # Each task runs as a child execution (delegation).
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
        # Treat nested Workflow objects in self.tasks as sub-workflows.
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

    # -- mesh --------------------------------------------------------------

    async def _run_adaptive(
        self,
        run: WorkflowRun,
        engine: ExecutionEngine,
        parent: ExecutionContext | None,
        ctx: dict | None,
    ) -> None:
        """Adaptive strategy: build a Planner from the workflow's tasks and
        let the :class:`AdaptiveSupervisor` steer execution step-by-step.

        Each task's declared capabilities register it as a compute
        participant; the planner resolves the sequence and the supervisor
        records decisions on the run.
        """
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
            for cap in task.capabilities:
                if cap not in seen:
                    seen.add(cap)
                    intent.require(cap)
        return intent

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
            "tasks": [t.describe() for t in self.tasks],
        }
