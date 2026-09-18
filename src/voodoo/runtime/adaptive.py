"""Adaptive runtime — a bounded, inspectable supervisor around ExecutionEngine.

The supervisor consumes a deterministic :class:`~voodoo.runtime.planner.Plan`
and executes every step through the canonical runtime. AI agents are compute
participants, not a second execution engine. Every retry, fallback and
participant decision remains inspectable and bounded by ``max_iterations``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.primitives.intent import Intent
from voodoo.primitives.resource import Resource
from voodoo.runtime.constraint import ResourceAccountant
from voodoo.runtime.engine import ComputeResult, ExecutionEngine
from voodoo.runtime.engine import engine as default_engine
from voodoo.runtime.errors import (
    ApprovalRequired,
    CapabilityDenied,
    ExecutionError,
    ExecutionTimeout,
    ResourceExceeded,
)
from voodoo.runtime.planner import ComputeParticipant, Plan, Planner, PlanStep

__all__ = [
    "SupervisorDecision",
    "SupervisorConfig",
    "AdaptiveDecisionRecord",
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
    """Hard bounds and resource budget for adaptive execution."""

    max_retries: int = 2
    max_iterations: int = 10
    budget: Resource | None = None


@dataclass
class AdaptiveDecisionRecord:
    """Structured supervisor decision with execution lineage when available."""

    decision: SupervisorDecision
    detail: str = ""
    step: str | None = None
    iteration: int = 0
    execution_id: str | None = None
    trace_id: str | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "detail": self.detail,
            "step": self.step,
            "iteration": self.iteration,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
        }


@dataclass
class AdaptiveRun:
    """Outcome of one bounded adaptive execution."""

    intent: Intent
    status: str = "running"
    execution_id: str | None = None
    trace_id: str | None = None
    decisions: list[str] = field(default_factory=list)
    decision_records: list[AdaptiveDecisionRecord] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    step_results: dict[str, Any] = field(default_factory=dict)
    iterations: int = 0
    result: Any | None = None
    error: str | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "intent": self.intent.name,
            "status": self.status,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "decisions": self.decisions,
            "decision_records": [record.describe() for record in self.decision_records],
            "steps": self.steps,
            "step_results": self.step_results,
            "iterations": self.iterations,
            "result": self.result,
            "error": self.error,
        }


class AdaptiveSupervisor:
    """Execute a Plan using bounded retries, fallbacks and agent participants."""

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
        self,
        run: AdaptiveRun,
        decision: SupervisorDecision,
        detail: str = "",
        *,
        step: str | None = None,
        execution: Any | None = None,
    ) -> None:
        run.decisions.append(decision.value + (f" ({detail})" if detail else ""))
        run.decision_records.append(
            AdaptiveDecisionRecord(
                decision=decision,
                detail=detail,
                step=step,
                iteration=run.iterations,
                execution_id=getattr(execution, "id", None),
                trace_id=getattr(execution, "trace_id", None),
            )
        )

    def _claim_iteration(self, run: AdaptiveRun, *, step: str) -> bool:
        """Consume one supervisor attempt or fail at the hard iteration bound."""
        if run.iterations >= self.config.max_iterations:
            run.status = "failed"
            run.error = (
                f"adaptive execution exceeded max_iterations="
                f"{self.config.max_iterations}"
            )
            self._record(run, SupervisorDecision.FAIL, run.error, step=step)
            return False
        run.iterations += 1
        return True

    def _check_budget(self, run: AdaptiveRun, execution: Any, *, step: str) -> bool:
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
        except ResourceExceeded as error:
            run.status = "failed"
            run.error = str(error)
            self._record(
                run,
                SupervisorDecision.FAIL,
                "budget exhausted",
                step=step,
                execution=execution,
            )
            return False
        return True

    def _step_intent(
        self,
        root: Intent,
        step: PlanStep,
        *,
        participant_name: str,
        context: dict[str, Any],
        results: dict[str, Any],
    ) -> Intent:
        """Build a step-local intent without mutating the root goal."""
        params = dict(root.params)
        params.update(context)
        params["_adaptive_root_intent_id"] = root.id
        params["_adaptive_participant"] = participant_name
        params["_adaptive_results"] = dict(results)
        step_intent = Intent(
            name=f"{root.name}:{participant_name}",
            params=params,
            deadline=root.deadline,
            constraints=list(root.constraints),
        )
        for capability in step.capabilities:
            step_intent.require(capability)
        return step_intent

    def _participant_compute(
        self,
        participant: ComputeParticipant,
        *,
        root_intent: Intent,
        step: PlanStep,
        context: dict[str, Any],
        results: dict[str, Any],
    ) -> Callable[..., Any] | None:
        """Resolve deterministic compute or adapt an Agent into compute."""
        if participant.compute is not None:
            return participant.compute
        if participant.agent is None:
            return None

        agent = participant.agent

        async def agent_compute(ctx: Any) -> ComputeResult:
            prompt = (
                f"Achieve intent '{root_intent.name}' using capability "
                f"{', '.join(step.capabilities) or participant.name}."
            )
            agent_context = dict(context)
            agent_context.update(ctx.state)
            if results:
                agent_context["upstream"] = dict(results)
                prompt += f"\n\nUpstream results: {results}"
            run = await agent.run(prompt, context=agent_context)
            return ComputeResult(
                value=run.output,
                resources=Resource(
                    cost=run.cost,
                    tokens=(run.tokens_in + run.tokens_out) or None,
                    latency_ms=(run.timings.get("total_ms") if run.timings else None),
                ),
            )

        return agent_compute

    async def _execute_participant(
        self,
        run: AdaptiveRun,
        root_intent: Intent,
        step: PlanStep,
        participant: ComputeParticipant,
        *,
        context: dict[str, Any],
        results: dict[str, Any],
        compute_override: Callable[..., Any] | None = None,
    ) -> Any | None:
        if not self._claim_iteration(run, step=participant.name):
            return None
        compute = compute_override or self._participant_compute(
            participant,
            root_intent=root_intent,
            step=step,
            context=context,
            results=results,
        )
        if compute is None:
            run.status = "failed"
            run.error = f"step {participant.name} has no compute"
            self._record(run, SupervisorDecision.FAIL, run.error, step=participant.name)
            return None

        step_intent = self._step_intent(
            root_intent,
            step,
            participant_name=participant.name,
            context=context,
            results=results,
        )
        execution = await self.engine.execute(
            step_intent,
            compute,
            actor=f"adaptive:{participant.name}",
            capabilities=step.capabilities or None,
        )
        run.execution_id = execution.id
        run.trace_id = execution.trace_id
        run.result = execution.result
        run.step_results[participant.name] = execution.result
        self._record(
            run,
            SupervisorDecision.CONTINUE,
            "step completed",
            step=participant.name,
            execution=execution,
        )
        if not self._check_budget(run, execution, step=participant.name):
            return None
        return execution

    async def _fallback(
        self,
        run: AdaptiveRun,
        root_intent: Intent,
        step: PlanStep,
        *,
        context: dict[str, Any],
        results: dict[str, Any],
        cause: Exception,
    ) -> bool:
        if not step.fallback:
            return False
        fallback = self.planner.participants.get(step.fallback)
        if fallback is None:
            return False
        self._record(
            run,
            SupervisorDecision.FALLBACK,
            f"{step.participant} -> {step.fallback}: {cause}",
            step=step.participant,
        )
        try:
            execution = await self._execute_participant(
                run,
                root_intent,
                step,
                fallback,
                context=context,
                results=results,
            )
        except (ExecutionError, ExecutionTimeout, CapabilityDenied) as error:
            run.status = "failed"
            run.error = str(error)
            self._record(run, SupervisorDecision.FAIL, str(error), step=fallback.name)
            return False
        return execution is not None and run.status != "failed"

    async def _run_step(
        self,
        run: AdaptiveRun,
        intent: Intent,
        step: PlanStep,
        participant: ComputeParticipant,
        *,
        context: dict[str, Any],
        compute: Callable[..., Any] | None,
    ) -> bool:
        retries = 0
        while True:
            try:
                execution = await self._execute_participant(
                    run,
                    intent,
                    step,
                    participant,
                    context=context,
                    results=run.step_results,
                    compute_override=compute,
                )
                return execution is not None
            except ApprovalRequired:
                run.status = "waiting"
                self._record(
                    run,
                    SupervisorDecision.REQUEST_APPROVAL,
                    step.participant,
                    step=step.participant,
                )
                return False
            except CapabilityDenied as error:
                if await self._fallback(
                    run,
                    intent,
                    step,
                    context=context,
                    results=run.step_results,
                    cause=error,
                ):
                    return True
                run.status = "failed"
                run.error = str(error)
                self._record(
                    run, SupervisorDecision.FAIL, str(error), step=step.participant
                )
                return False
            except ExecutionTimeout as error:
                if retries < self.config.max_retries:
                    retries += 1
                    self._record(
                        run,
                        SupervisorDecision.RETRY,
                        f"attempt {retries}",
                        step=step.participant,
                    )
                    continue
                if await self._fallback(
                    run,
                    intent,
                    step,
                    context=context,
                    results=run.step_results,
                    cause=error,
                ):
                    return True
                run.status = "timed_out"
                run.error = str(error)
                self._record(
                    run, SupervisorDecision.FAIL, str(error), step=step.participant
                )
                return False
            except ExecutionError as error:
                if (
                    retries < self.config.max_retries
                    and self.engine.constraints.retry_hint(intent=intent, error=error)
                ):
                    retries += 1
                    self._record(
                        run,
                        SupervisorDecision.RETRY,
                        f"constraint hint ({retries})",
                        step=step.participant,
                    )
                    continue
                if await self._fallback(
                    run,
                    intent,
                    step,
                    context=context,
                    results=run.step_results,
                    cause=error,
                ):
                    return True
                run.status = "failed"
                run.error = str(error)
                self._record(
                    run, SupervisorDecision.FAIL, str(error), step=step.participant
                )
                return False

    async def run(
        self,
        intent: Intent,
        *,
        compute: Callable[..., Any] | None = None,
        plan: Plan | None = None,
        context: dict[str, Any] | None = None,
    ) -> AdaptiveRun:
        """Execute a goal with bounded, step-local adaptive behavior."""
        run = AdaptiveRun(intent=intent)
        context = dict(context or {})
        plan = plan or self.planner.plan(intent, context=context)

        if self.config.max_iterations <= 0:
            run.status = "failed"
            run.error = "max_iterations must be greater than zero"
            self._record(run, SupervisorDecision.FAIL, run.error)
            return run

        if plan.unresolved:
            run.status = "failed"
            run.error = f"no compute participant for: {', '.join(plan.unresolved)}"
            self._record(run, SupervisorDecision.FAIL, run.error)
            return run

        for step in plan.steps:
            participant = self.planner.participants.get(step.participant)
            if participant is None:
                run.status = "failed"
                run.error = f"unknown participant: {step.participant}"
                self._record(
                    run, SupervisorDecision.FAIL, run.error, step=step.participant
                )
                return run

            run.steps.append(step.participant)
            self._record(
                run,
                SupervisorDecision.CONTINUE,
                f"step {step.participant} ({step.kind})",
                step=step.participant,
            )

            if step.kind == "human" or step.requires_approval:
                run.status = "waiting"
                self._record(
                    run,
                    SupervisorDecision.REQUEST_APPROVAL,
                    step.participant,
                    step=step.participant,
                )
                return run

            if not await self._run_step(
                run,
                intent,
                step,
                participant,
                context=context,
                compute=compute,
            ):
                return run

        run.status = "completed"
        return run
