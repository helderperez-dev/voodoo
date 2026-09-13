"""Goal-driven operational runtime.

A Goal is a durable-friendly statement of desired outcome. It is intentionally
above Intent: a Goal may decompose into multiple Intents, each of which is still
planned and executed through the existing AdaptiveSupervisor/ExecutionEngine.

    World → Goal → Intent(s) → Plan → Execution → Effect → Observation → World

GoalRuntime does not create another execution engine. It coordinates the
existing runtime and records the relationship between a long-lived objective
and the adaptive executions used to pursue it.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from voodoo.primitives.intent import Intent
from voodoo.runtime.adaptive import AdaptiveRun, AdaptiveSupervisor
from voodoo.runtime.world_execution import bind_world

__all__ = [
    "GoalStatus",
    "Goal",
    "GoalIntentRun",
    "GoalRun",
    "GoalDecomposer",
    "GoalRuntime",
]


def _now() -> datetime:
    return datetime.now(UTC)


class GoalStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
        }


@dataclass
class Goal:
    """A desired operational outcome that may require multiple Intents."""

    name: str
    objective: str = ""
    target_entity_id: str | None = None
    requires: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"goal_{uuid4().hex}")
    status: GoalStatus = GoalStatus.CREATED
    intent_ids: list[str] = field(default_factory=list)
    result: Any | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def transition(self, status: GoalStatus) -> None:
        self.status = status
        self.updated_at = _now()

    def complete(self, result: Any | None = None) -> None:
        self.result = result
        self.error = None
        self.transition(GoalStatus.COMPLETED)

    def fail(self, error: str) -> None:
        self.error = error
        self.transition(GoalStatus.FAILED)

    def cancel(self) -> None:
        self.transition(GoalStatus.CANCELLED)

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "objective": self.objective,
            "target_entity_id": self.target_entity_id,
            "requires": list(self.requires),
            "status": self.status.value,
            "intent_ids": list(self.intent_ids),
            "has_result": self.result is not None,
            "error": self.error,
        }


@dataclass
class GoalIntentRun:
    """One Intent pursued on behalf of a Goal."""

    intent_id: str
    intent_name: str
    status: str
    execution_id: str | None = None
    trace_id: str | None = None
    result: Any | None = None
    error: str | None = None
    decisions: list[str] = field(default_factory=list)

    @classmethod
    def from_adaptive(cls, intent: Intent, run: AdaptiveRun) -> GoalIntentRun:
        return cls(
            intent_id=intent.id,
            intent_name=intent.name,
            status=run.status,
            execution_id=run.execution_id,
            trace_id=run.trace_id,
            result=run.result,
            error=run.error,
            decisions=list(run.decisions),
        )


@dataclass
class GoalRun:
    """Inspectable attempt to achieve a Goal."""

    goal: Goal
    intent_runs: list[GoalIntentRun] = field(default_factory=list)
    current_index: int = 0
    started_at: datetime = field(default_factory=_now)
    completed_at: datetime | None = None

    @property
    def status(self) -> GoalStatus:
        return self.goal.status

    @property
    def result(self) -> Any | None:
        return self.goal.result

    @property
    def error(self) -> str | None:
        return self.goal.error

    def describe(self) -> dict[str, Any]:
        return {
            "goal": self.goal.describe(),
            "current_index": self.current_index,
            "intent_runs": [
                {
                    "intent_id": item.intent_id,
                    "intent_name": item.intent_name,
                    "status": item.status,
                    "execution_id": item.execution_id,
                    "trace_id": item.trace_id,
                    "result": item.result,
                    "error": item.error,
                    "decisions": list(item.decisions),
                }
                for item in self.intent_runs
            ],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


GoalDecomposer = Callable[
    [Goal, Any | None], list[Intent] | Awaitable[list[Intent]]
]


class GoalRuntime:
    """Coordinate Goal → Intent(s) over the existing adaptive runtime."""

    def __init__(
        self,
        supervisor: AdaptiveSupervisor,
        *,
        world: Any | None = None,
    ) -> None:
        self.supervisor = supervisor
        self.world = world
        self.runs: dict[str, GoalRun] = {}
        if world is not None:
            bind_world(self.supervisor.engine, world)

    async def achieve(
        self,
        goal: Goal,
        *,
        intents: list[Intent] | None = None,
        decomposer: GoalDecomposer | None = None,
        context: dict[str, Any] | None = None,
    ) -> GoalRun:
        """Pursue a Goal through one or more canonical Intents."""
        if goal.status.terminal:
            raise ValueError(f"goal {goal.id} is already terminal: {goal.status.value}")

        goal.transition(GoalStatus.PLANNING)
        planned = intents or await self._decompose(goal, decomposer)
        if not planned:
            goal.fail("goal produced no intents")
            run = GoalRun(goal=goal, completed_at=_now())
            self.runs[goal.id] = run
            return run

        self._prepare_intents(goal, planned)
        run = GoalRun(goal=goal)
        self.runs[goal.id] = run
        goal.transition(GoalStatus.RUNNING)

        base_context = dict(context or {})
        base_context["goal_id"] = goal.id
        base_context["goal_name"] = goal.name
        if goal.target_entity_id is not None:
            base_context["target_entity_id"] = goal.target_entity_id

        for index, intent in enumerate(planned):
            run.current_index = index
            adaptive = await self.supervisor.run(intent, context=base_context)
            record = GoalIntentRun.from_adaptive(intent, adaptive)
            run.intent_runs.append(record)

            if adaptive.status == "waiting":
                goal.transition(GoalStatus.WAITING)
                return run
            if adaptive.status != "completed":
                goal.fail(adaptive.error or f"intent {intent.name} failed")
                run.completed_at = _now()
                return run

        results = [item.result for item in run.intent_runs]
        goal.complete(results[-1] if len(results) == 1 else results)
        run.current_index = len(planned)
        run.completed_at = _now()
        return run

    async def _decompose(
        self,
        goal: Goal,
        decomposer: GoalDecomposer | None,
    ) -> list[Intent]:
        snapshot = self._snapshot(goal.target_entity_id)
        if decomposer is not None:
            result = decomposer(goal, snapshot)
            if inspect.isawaitable(result):
                result = await result
            return list(result)

        intent = Intent(
            name=goal.name,
            description=goal.objective,
            params={"_goal_id": goal.id},
        )
        if goal.target_entity_id is not None:
            intent.params["entity_id"] = goal.target_entity_id
        for capability in goal.requires:
            intent.require(capability)
        return [intent]

    def _snapshot(self, entity_id: str | None) -> Any | None:
        if self.world is None or entity_id is None:
            return None
        try:
            return self.world.snapshot(entity_id)
        except KeyError:
            return None

    @staticmethod
    def _prepare_intents(goal: Goal, intents: list[Intent]) -> None:
        goal.intent_ids.clear()
        for intent in intents:
            intent.params.setdefault("_goal_id", goal.id)
            if goal.target_entity_id is not None:
                intent.params.setdefault("entity_id", goal.target_entity_id)
            goal.intent_ids.append(intent.id)
