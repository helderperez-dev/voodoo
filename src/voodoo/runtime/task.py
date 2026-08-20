"""Task — a first-class executable unit of intent.

A Task represents work. It maps onto the common execution model rather
than becoming a separate orchestration/queue runtime.

    Task(description, agent=..., depends_on=[...])
        → Intent
            → Capability resolution
            → Compute (agent / deterministic fn / worker / human)
            → Effect
            → State

Tasks are composable (``depends_on``) and carry their own constraints,
resources, timeout/retry policy and structured output type — all of which
compile into the runtime's existing primitives.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from voodoo.primitives.constraint import Constraint
from voodoo.primitives.intent import Intent
from voodoo.primitives.resource import Resource
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.engine import ComputeFn, ComputeResult, ExecutionEngine
from voodoo.runtime.engine import engine as default_engine
from voodoo.runtime.errors import ExecutionError, ExecutionTimeout
from voodoo.runtime.execution import Execution

__all__ = ["TaskStatus", "Task"]


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


@dataclass
class Task:
    """A first-class executable unit.

    Parameters
    ----------
    name / description:
        Identity and human-readable purpose.
    agent:
        Optional :class:`~voodoo.ai.agent.Agent` (or any object with an
        ``async run(prompt, context)`` method). When provided, the task's
        compute is the agent.
    compute:
        Optional explicit compute callable (sync or async) receiving the
        :class:`ExecutionContext`. Use this for deterministic compute,
        workers, or human approval callbacks.
    depends_on:
        Other tasks that must complete before this one starts.
    tools / capabilities / constraints / resources / timeout / retries:
        Compile onto the computational model.
    output:
        Optional structured-output type for validation.
    """

    name: str
    description: str = ""
    agent: Any = None
    compute: ComputeFn | None = None
    depends_on: list[Task] = field(default_factory=list)
    tools: list[Any] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    resources: Resource | None = None
    timeout: float | None = None
    retries: int = 0
    output: type | None = None
    condition: Callable[[dict[str, Any]], bool] | None = None
    #: Human-in-the-loop: the task's compute is a human decision
    #: (raises ``ApprovalRequired`` until approved, then completes).
    human: bool = False
    #: Capability to request approval for (used with ``human=True``).
    approval_capability: str | None = None

    id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    execution: Execution | None = None
    result: Any = None
    error: str | None = None

    # -- execution ---------------------------------------------------------

    async def run(
        self,
        *,
        context: dict[str, Any] | None = None,
        engine: ExecutionEngine = default_engine,
        parent: ExecutionContext | None = None,
        results: dict[str, Any] | None = None,
    ) -> Execution:
        """Execute this task through the common runtime.

        ``results`` carries upstream task results (keyed by task name) so
        ``condition`` and compute can depend on prior outputs.
        """
        results = results or {}

        # Conditional skip — compiles into the execution model as a no-op.
        if self.condition is not None and not self.condition(results):
            return self._skip(parent)

        self.status = TaskStatus.RUNNING
        params = dict(context or {})
        params["_upstream"] = results

        intent = self._build_intent(params)
        compute_fn = self._resolve_compute(results)
        actor = getattr(self.agent, "model", "task") if self.agent else "task"

        max_attempts = self.retries + 1
        last_error: Exception | None = None

        for _ in range(max_attempts):
            try:
                execution = await engine.execute(
                    intent,
                    compute_fn,
                    actor=actor,
                    capabilities=self.capabilities or None,
                    output_type=self.output,
                    parent=parent,
                )
                self.execution = execution
                self.result = execution.result
                self.status = (
                    TaskStatus.COMPLETED if execution.succeeded else TaskStatus.FAILED
                )
                if execution.failed:
                    self.error = execution.error
                return execution
            except ExecutionTimeout as e:
                last_error = e
                # retry with a fresh intent (same params)
                intent = self._build_intent(params)
            except ExecutionError as e:
                from voodoo.runtime.errors import ApprovalRequired

                # Human approval is not a retryable failure: the execution is
                # left `waiting` and resumed by engine.approve(). Record the
                # waiting state on the task and propagate so the caller
                # observes the pending approval.
                if isinstance(e, ApprovalRequired):
                    if e.execution_id is not None:
                        self.execution = engine.get(e.execution_id)
                    self.status = TaskStatus.WAITING
                    raise
                last_error = e
                intent = self._build_intent(params)

        self.status = TaskStatus.FAILED
        self.error = str(last_error) if last_error else "task failed"
        raise ExecutionError(self.error, context={"task": self.name})

    # -- internals ---------------------------------------------------------

    def _build_intent(self, params: dict[str, Any]) -> Intent:
        """Compile this task's constraints/capabilities/deadline onto an Intent."""
        intent = Intent(name=self.name, params=params)
        for c in self.constraints:
            intent.constrain(c)
        for cap in self.capabilities:
            intent.require(cap)
        if self.timeout is not None:
            intent.with_deadline(self.timeout)
        return intent

    def _skip(self, parent: ExecutionContext | None) -> Execution:
        """Produce a completed no-op execution for a skipped condition."""
        self.status = TaskStatus.SKIPPED
        intent = Intent(name=self.name, params={"skipped": True})
        skipped = Execution(
            trace_id=parent.trace_id if parent else intent.id,
            parent_execution_id=parent.execution_id if parent else None,
            intent=intent,
            actor=getattr(self.agent, "model", "task") if self.agent else "task",
        )
        skipped.complete(result=None)
        self.execution = skipped
        return skipped

    def _resolve_compute(self, results: dict[str, Any]) -> ComputeFn:
        if self.compute is not None:
            return self.compute
        if self.human:
            from voodoo.runtime.human import ask_human

            return ask_human(
                self.description or f"Approve task '{self.name}'?",
                capability=self.approval_capability,
            )
        if self.agent is not None:
            agent = self.agent
            output_type = self.output

            async def agent_compute(ctx: ExecutionContext) -> ComputeResult:
                prompt = self.description or self.name
                upstream = (
                    results.get("_upstream", {}) if isinstance(results, dict) else {}
                )
                if upstream:
                    prompt = f"{prompt}\n\nUpstream results: {upstream}"
                run = await agent.run(prompt, context=dict(ctx.state))
                value = run.output
                if output_type is not None and hasattr(output_type, "model_validate"):
                    try:
                        import json

                        value = output_type.model_validate(json.loads(run.output))
                    except Exception:  # noqa: BLE001
                        pass
                return ComputeResult(
                    value=value,
                    resources=Resource(
                        cost=run.cost,
                        tokens=(run.tokens_in + run.tokens_out) or None,
                        latency_ms=(
                            run.timings.get("total_ms") if run.timings else None
                        ),
                    ),
                )

            return agent_compute

        async def noop(ctx: ExecutionContext) -> ComputeResult:
            return ComputeResult(value=results)

        return noop

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "depends_on": [t.name for t in self.depends_on],
            "capabilities": self.capabilities,
            "has_agent": self.agent is not None,
            "has_compute": self.compute is not None,
            "timeout": self.timeout,
            "retries": self.retries,
            "execution_id": self.execution.id if self.execution else None,
        }
