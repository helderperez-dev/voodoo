"""Adaptive runtime — a supervisor loop around the execution engine.

The supervisor executes an intent by consulting the :class:`Planner` per
step, then steering execution with explicit decisions:

    continue | retry | delegate | fallback | wait | request_approval | fail

Each decision is recorded on the :class:`AdaptiveRun` so adaptive
behavior stays inspectable (the same observability contract as the rest
of the runtime: execution_id, trace_id, status, decisions, result).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.primitives.intent import Intent
from voodoo.primitives.resource import Resource
from voodoo.runtime.constraint import ResourceAccountant
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.engine import engine as default_engine
from voodoo.runtime.errors import (
    ApprovalRequired,
    CapabilityDenied,
    ExecutionError,
    ExecutionTimeout,
    ResourceExceeded,
)
from voodoo.runtime.planner import Plan, Planner

__all__ = [
    "SupervisorDecision",
    "SupervisorConfig",
    "AdaptiveRun",
    "AdaptiveSupervisor",
]


class SupervisorDecision(StrEnum):
    CONTINUE = "continue"
    RETRY = "retry"
    DELEGATE = "delegate"
    FALLBACK = "fallback"
    WAIT = "wait"
    REQUEST_APPROVAL = "request_approval"
    FAIL = "fail"


@dataclass
class SupervisorConfig:
    """Knobs for the adaptive loop."""

    max_retries: int = 2
    max_iterations: int = 10
    #: Optional resource budget. When set, the supervisor accumulates
    #: per-step cost/tokens/latency and stops with ``ResourceExceeded``
    #: before the budget is blown.
    budget: Resource | None = None


@dataclass
class AdaptiveRun:
    """Outcome of an adaptive execution — inspectable like any Execution."""

    intent: Intent
    status: str = "running"
    execution_id: str | None = None
    trace_id: str | None = None
    decisions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    result: Any | None = None
    error: str | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "intent": self.intent.name,
            "status": self.status,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "decisions": self.decisions,
            "steps": self.steps,
            "result": self.result,
            "error": self.error,
        }


class AdaptiveSupervisor:
    """Supervisor loop that plans per step and steers execution."""

    def __init__(
        self,
        planner: Planner,
        *,
        engine: ExecutionEngine = default_engine,
        config: SupervisorConfig | None = None,
    ) -> None:
        self.planner = planner
        self.engine = engine
        self.config = config or SupervisorConfig()
        self._accountant = ResourceAccountant(budget=self.config.budget or Resource())

    def _record(
        self, run: AdaptiveRun, decision: SupervisorDecision, detail: str = ""
    ) -> None:
        run.decisions.append(decision.value + (f" ({detail})" if detail else ""))

    def _check_budget(self, run: AdaptiveRun, execution: Any) -> bool:
        """Accumulate per-step resource usage and check the budget.

        Returns True when the step is within budget, False when the
        budget is exhausted (and records a ``fail`` decision).
        """
        if self.config.budget is None:
            return True
        latency_ms = None
        if execution.duration_seconds is not None:
            latency_ms = execution.duration_seconds * 1000
        usage = Resource(
            cost=execution.cost or 0.0,
            latency_ms=latency_ms,
            tokens=None,
        )
        try:
            self._accountant.account(usage, execution_id=execution.id)
        except ResourceExceeded as e:
            run.status = "failed"
            run.error = str(e)
            self._record(run, SupervisorDecision.FAIL, "budget exhausted")
            return False
        return True

    # -- core loop ---------------------------------------------------------

    async def run(  # noqa: C901
        self,
        intent: Intent,
        *,
        compute: Callable[..., Any] | None = None,
        plan: Plan | None = None,
        context: dict[str, Any] | None = None,
    ) -> AdaptiveRun:
        """Execute an intent adaptively.

        ``compute`` is the primary compute callable. When a planner is
        wired with participants, the plan is consulted for fallbacks and
        approval requirements. The supervisor records a decision for every
        steering action.
        """
        run = AdaptiveRun(intent=intent)
        plan = plan or self.planner.plan(intent)

        if plan.unresolved:
            run.status = "failed"
            run.error = f"no compute participant for: {', '.join(plan.unresolved)}"
            self._record(run, SupervisorDecision.FAIL, run.error)
            return run

        retries = 0
        step_idx = 0
        while step_idx < len(plan.steps):
            step = plan.steps[step_idx]
            run.steps.append(step.participant)
            self._record(
                run,
                SupervisorDecision.CONTINUE,
                f"step {step.participant} ({step.kind})",
            )

            participant = self.planner.participants.get(step.participant)
            step_compute = compute or (participant.compute if participant else None)

            if step.kind == "human" or step.requires_approval:
                run.status = "waiting"
                self._record(run, SupervisorDecision.REQUEST_APPROVAL, step.participant)
                return run

            if step_compute is None:
                run.status = "failed"
                run.error = f"step {step.participant} has no compute"
                self._record(run, SupervisorDecision.FAIL, run.error)
                return run

            try:
                execution = await self.engine.execute(
                    intent, step_compute, actor="adaptive"
                )
                run.execution_id = execution.id
                run.trace_id = execution.trace_id
                run.result = execution.result
                self._record(run, SupervisorDecision.CONTINUE, "step completed")
                if not self._check_budget(run, execution):
                    return run
                step_idx += 1
            except ApprovalRequired:
                run.status = "waiting"
                self._record(run, SupervisorDecision.REQUEST_APPROVAL, step.participant)
                return run
            except CapabilityDenied as e:
                if step.fallback:
                    fallback = self.planner.participants.get(step.fallback)
                    if fallback and fallback.compute:
                        self._record(
                            run,
                            SupervisorDecision.FALLBACK,
                            f"{step.participant} -> {step.fallback}",
                        )
                        execution = await self.engine.execute(
                            intent, fallback.compute, actor="adaptive"
                        )
                        run.execution_id = execution.id
                        run.trace_id = execution.trace_id
                        run.result = execution.result
                        self._record(
                            run, SupervisorDecision.CONTINUE, "fallback completed"
                        )
                        if not self._check_budget(run, execution):
                            return run
                        step_idx += 1
                        continue
                run.status = "failed"
                run.error = str(e)
                self._record(run, SupervisorDecision.FAIL, str(e))
                return run
            except ExecutionTimeout as e:
                if retries < self.config.max_retries:
                    retries += 1
                    self._record(run, SupervisorDecision.RETRY, f"attempt {retries}")
                    continue
                run.status = "timed_out"
                run.error = str(e)
                self._record(run, SupervisorDecision.FAIL, str(e))
                return run
            except ExecutionError as e:
                # Constraint → adaptive retry hook: when the intent's
                # constraints suggest retry, let the supervisor try again
                # (up to max_retries) before failing.
                if (
                    retries < self.config.max_retries
                    and self.engine.constraints.retry_hint(intent=intent, error=e)
                ):
                    retries += 1
                    self._record(
                        run, SupervisorDecision.RETRY, f"constraint hint ({retries})"
                    )
                    continue
                run.status = "failed"
                run.error = str(e)
                self._record(run, SupervisorDecision.FAIL, str(e))
                return run

        run.status = "completed"
        return run
