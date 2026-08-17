"""Constraint enforcement & resource accounting (Phase 4).

A single :class:`ConstraintEnforcer` evaluates whether an execution is
still allowed (before and during execution) and a single
:class:`ResourceAccountant` tracks resource consumption against budgets.

Centralizing this means Agent, Tool, Worker, Workflow and Task do not
each implement their own retry/cost/limit logic — they ask the runtime.

Evaluation outcomes map onto the runtime's decision vocabulary:

    continue | stop | retry | fallback | wait | request approval | fail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.primitives.resource import Resource
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.errors import ConstraintViolation, ResourceExceeded

__all__ = [
    "Decision",
    "ConstraintEnforcer",
    "ResourceAccountant",
]


class Decision(StrEnum):
    CONTINUE = "continue"
    STOP = "stop"
    RETRY = "retry"
    FALLBACK = "fallback"
    WAIT = "wait"
    REQUEST_APPROVAL = "request_approval"
    FAIL = "fail"


@dataclass
class ConstraintEnforcer:
    """Evaluate constraints against a context before/during execution.

    Constraints describe limits (cost, latency, iterations, tokens, tool
    calls, approval, deadlines). The enforcer checks the active context's
    constraints and the provided runtime measurements.
    """

    def evaluate(
        self,
        context: ExecutionContext,
        *,
        cost: float | None = None,
        latency_ms: float | None = None,
        iterations: int | None = None,
        tokens: int | None = None,
        tool_calls: int | None = None,
        execution_id: str | None = None,
    ) -> Decision:
        """Evaluate all constraints; return a :class:`Decision`."""
        if context.cancelled or context.deadline_expired:
            return Decision.STOP

        measurements = {
            "cost": cost,
            "latency": latency_ms,
            "iterations": iterations,
            "tokens": tokens,
            "tool_calls": tool_calls,
        }
        for c in context.constraints:
            if c.kind == "approval":
                if c.value is True:
                    return Decision.REQUEST_APPROVAL
                continue
            value = measurements.get(c.kind)
            if value is None:
                continue
            try:
                if not c.evaluate(value):
                    return Decision.FAIL
            except TypeError:
                continue
        return Decision.CONTINUE

    def enforce(
        self,
        context: ExecutionContext,
        *,
        cost: float | None = None,
        latency_ms: float | None = None,
        iterations: int | None = None,
        tokens: int | None = None,
        tool_calls: int | None = None,
        execution_id: str | None = None,
    ) -> None:
        """Raise a structured error when a constraint is violated."""
        decision = self.evaluate(
            context,
            cost=cost,
            latency_ms=latency_ms,
            iterations=iterations,
            tokens=tokens,
            tool_calls=tool_calls,
            execution_id=execution_id,
        )
        if decision is Decision.FAIL:
            raise ConstraintViolation(
                "A runtime constraint was violated",
                execution_id=execution_id,
                trace_id=context.trace_id,
                context={
                    "cost": cost,
                    "latency_ms": latency_ms,
                    "iterations": iterations,
                    "tokens": tokens,
                    "tool_calls": tool_calls,
                },
            )
        if decision is Decision.STOP:
            from voodoo.runtime.errors import ExecutionCancelled

            reason = "deadline expired" if context.deadline_expired else "cancelled"
            raise ExecutionCancelled(
                f"Execution stopped: {reason}",
                execution_id=execution_id,
                trace_id=context.trace_id,
            )
        if decision is Decision.REQUEST_APPROVAL:
            from voodoo.runtime.errors import ApprovalRequired

            raise ApprovalRequired(
                "Human approval required by constraint",
                execution_id=execution_id,
                trace_id=context.trace_id,
            )


    def retry_hint(
        self,
        context: ExecutionContext | None = None,
        *,
        intent: Any | None = None,
        error: Exception | None = None,
    ) -> bool:
        """Check whether the active constraints suggest a retry.

        A constraint with ``kind="retry"`` and ``value=True`` signals that
        the supervisor should retry the step rather than fail. This is the
        hook the adaptive runtime uses to translate constraint decisions
        into supervisor decisions.

        When ``intent`` is provided, its constraints are also checked (so
        the hint works outside the execution context manager).
        """
        sources: list[Any] = []
        if context is not None:
            sources.append(context.constraints)
        if intent is not None:
            sources.append(intent.constraints)
        for constraints in sources:
            for c in constraints:
                if c.kind == "retry" and c.value is True:
                    return True
        return False


@dataclass
class ResourceAccountant:
    """Track resource consumption against budgets.

    Budgets are expressed as a :class:`Resource` (max cost, max tokens,
    max latency). Each :meth:`account` call accumulates usage and checks
    the budget, raising :class:`ResourceExceeded` when a limit is blown.
    """

    budget: Resource = field(default_factory=Resource)
    consumed: Resource = field(default_factory=Resource)

    def account(self, usage: Resource, *, execution_id: str | None = None) -> Resource:
        """Accumulate ``usage`` and enforce the budget."""
        self.consumed = self.consumed.add(usage)

        if self.budget.cost and self.consumed.cost > self.budget.cost:
            raise ResourceExceeded(
                f"Cost budget exceeded: {self.consumed.cost} > {self.budget.cost}",
                execution_id=execution_id,
                context={"consumed": self.consumed.describe(), "budget": self.budget.describe()},
            )
        if self.budget.tokens and self.consumed.tokens and self.consumed.tokens > self.budget.tokens:
            raise ResourceExceeded(
                f"Token budget exceeded: {self.consumed.tokens} > {self.budget.tokens}",
                execution_id=execution_id,
                context={"consumed": self.consumed.describe(), "budget": self.budget.describe()},
            )
        if (
            self.budget.latency_ms
            and self.consumed.latency_ms
            and self.consumed.latency_ms > self.budget.latency_ms
        ):
            raise ResourceExceeded(
                f"Latency budget exceeded: {self.consumed.latency_ms}ms > "
                f"{self.budget.latency_ms}ms",
                execution_id=execution_id,
                context={"consumed": self.consumed.describe(), "budget": self.budget.describe()},
            )
        return self.consumed

    def remaining(self) -> Resource:
        """Return the remaining budget as a Resource."""
        return Resource(
            cost=max(self.budget.cost - self.consumed.cost, 0.0) if self.budget.cost else 0.0,
            tokens=max((self.budget.tokens or 0) - (self.consumed.tokens or 0), 0)
            if self.budget.tokens
            else None,
            latency_ms=max((self.budget.latency_ms or 0) - (self.consumed.latency_ms or 0), 0.0)
            if self.budget.latency_ms
            else None,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "budget": self.budget.describe(),
            "consumed": self.consumed.describe(),
            "remaining": self.remaining().describe(),
        }
