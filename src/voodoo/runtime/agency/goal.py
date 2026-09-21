"""Goal-driven operational runtime with durable checkpoints.

A Goal sits above Intent and may span many canonical Executions. GoalRuntime
coordinates existing AdaptiveSupervisor/ExecutionEngine semantics; persistence
only checkpoints orchestration state so process restarts do not erase agency.
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
from voodoo.runtime.agency.adaptive import AdaptiveRun, AdaptiveSupervisor
from voodoo.runtime.agency.goal_store import GoalStore
from voodoo.runtime.execution import ExecutionStatus
from voodoo.runtime.execution.world import bind_world

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
        return self in {GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED}


@dataclass
class Goal:
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
            "metadata": dict(self.metadata),
            "status": self.status.value,
            "intent_ids": list(self.intent_ids),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class GoalIntentRun:
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

    def describe(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "intent_name": self.intent_name,
            "status": self.status,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "result": self.result,
            "error": self.error,
            "decisions": list(self.decisions),
        }


@dataclass
class GoalRun:
    goal: Goal
    planned_intents: list[Intent] = field(default_factory=list)
    intent_runs: list[GoalIntentRun] = field(default_factory=list)
    current_index: int = 0
    context: dict[str, Any] = field(default_factory=dict)
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
            "planned_intents": [
                intent.model_dump(mode="json") for intent in self.planned_intents
            ],
            "current_index": self.current_index,
            "context": dict(self.context),
            "intent_runs": [item.describe() for item in self.intent_runs],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


GoalDecomposer = Callable[[Goal, Any | None], list[Intent] | Awaitable[list[Intent]]]


class GoalRuntime:
    """Coordinate durable Goal → Intent(s) over the existing adaptive runtime."""

    def __init__(
        self,
        supervisor: AdaptiveSupervisor,
        *,
        world: Any | None = None,
        store: GoalStore | None = None,
    ) -> None:
        self.supervisor = supervisor
        self.world = world
        self.store = store
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
        if goal.status.terminal:
            raise ValueError(f"goal {goal.id} is already terminal: {goal.status.value}")

        goal.transition(GoalStatus.PLANNING)
        planned = intents or await self._decompose(goal, decomposer)
        if not planned:
            goal.fail("goal produced no intents")
            run = GoalRun(goal=goal, completed_at=_now())
            self.runs[goal.id] = run
            self._persist(run)
            return run

        self._prepare_intents(goal, planned)
        base_context = dict(context or {})
        base_context.update({"goal_id": goal.id, "goal_name": goal.name})
        if goal.target_entity_id is not None:
            base_context["target_entity_id"] = goal.target_entity_id
        self._refresh_world_context(goal, base_context)

        run = GoalRun(
            goal=goal,
            planned_intents=list(planned),
            context=base_context,
        )
        self.runs[goal.id] = run
        goal.transition(GoalStatus.RUNNING)
        self._persist(run)
        return await self._continue(run)

    async def resume(self, goal_id: str) -> GoalRun:
        """Resume a persisted Goal from its last safe orchestration checkpoint."""
        run = self.runs.get(goal_id)
        if run is None:
            if self.store is None:
                raise KeyError(goal_id)
            payload = self.store.load(goal_id)
            if payload is None:
                raise KeyError(goal_id)
            run = self._restore(payload)
            self.runs[goal_id] = run

        if run.goal.status.terminal:
            return run

        if run.goal.status is GoalStatus.WAITING:
            if not self._reconcile_waiting(run):
                self._persist(run)
                return run

        run.goal.transition(GoalStatus.RUNNING)
        self._refresh_world_context(run.goal, run.context)
        self._persist(run)
        return await self._continue(run)

    def recover(self) -> list[GoalRun]:
        """Reload unfinished Goal runs after process restart without executing them."""
        if self.store is None:
            return []
        recovered: list[GoalRun] = []
        for payload in self.store.load_unfinished():
            run = self._restore(payload)
            self.runs[run.goal.id] = run
            recovered.append(run)
        return recovered

    async def _continue(self, run: GoalRun) -> GoalRun:
        for index in range(run.current_index, len(run.planned_intents)):
            intent = run.planned_intents[index]
            run.current_index = index
            # Each Intent is planned against the latest observed World projection,
            # not a stale snapshot captured at Goal creation time.
            self._refresh_world_context(run.goal, run.context)
            if run.intent_runs:
                run.context["prior_results"] = {
                    item.intent_id: item.result
                    for item in run.intent_runs
                    if item.status == "completed"
                }
            self._persist(run)
            adaptive = await self.supervisor.run(intent, context=run.context)
            record = GoalIntentRun.from_adaptive(intent, adaptive)
            if adaptive.status == "waiting" and record.execution_id is None:
                record.execution_id = self._find_waiting_execution(intent.id)
            run.intent_runs.append(record)

            if adaptive.status == "waiting":
                run.goal.transition(GoalStatus.WAITING)
                self._persist(run)
                return run
            if adaptive.status != "completed":
                run.goal.fail(adaptive.error or f"intent {intent.name} failed")
                run.completed_at = _now()
                self._persist(run)
                return run

            run.current_index = index + 1
            self._persist(run)

        results = [
            item.result for item in run.intent_runs if item.status == "completed"
        ]
        run.goal.complete(results[-1] if len(results) == 1 else results)
        run.current_index = len(run.planned_intents)
        run.completed_at = _now()
        self._persist(run)
        return run

    def _refresh_world_context(self, goal: Goal, context: dict[str, Any]) -> None:
        """Refresh the JSON-friendly World projection used by bounded planning."""
        snapshot = self._snapshot(goal.target_entity_id)
        if snapshot is None:
            context.pop("world", None)
            return
        context["world"] = dict(snapshot.entity.properties)
        context["world_observations"] = {
            key: {
                "source": observation.source,
                "confidence": observation.confidence,
                "observed_at": observation.observed_at.isoformat(),
                "execution_id": observation.execution_id,
            }
            for key, observation in snapshot.latest_observations.items()
        }

    def _reconcile_waiting(self, run: GoalRun) -> bool:
        if not run.intent_runs:
            return False
        record = run.intent_runs[-1]
        if record.status != "waiting" or record.execution_id is None:
            return False
        execution = self.supervisor.engine.executions.get(record.execution_id)
        if execution is None:
            return False
        if execution.status is ExecutionStatus.WAITING:
            return False
        if execution.status is ExecutionStatus.COMPLETED:
            record.status = "completed"
            record.result = execution.result
            record.error = None
            run.current_index += 1
            return True
        if execution.status.terminal:
            record.status = "failed"
            record.error = execution.error or "waiting execution did not complete"
            run.goal.fail(record.error)
            run.completed_at = _now()
        return False

    def _find_waiting_execution(self, intent_id: str) -> str | None:
        for execution in reversed(list(self.supervisor.engine.executions.values())):
            if (
                execution.intent is not None
                and execution.intent.id == intent_id
                and execution.status is ExecutionStatus.WAITING
            ):
                return execution.id
        return None

    def _persist(self, run: GoalRun) -> None:
        if self.store is not None:
            self.store.save(run.goal.id, run.describe())

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

    @staticmethod
    def _restore(payload: dict[str, Any]) -> GoalRun:
        raw_goal = payload["goal"]
        goal = Goal(
            id=raw_goal["id"],
            name=raw_goal["name"],
            objective=raw_goal.get("objective", ""),
            target_entity_id=raw_goal.get("target_entity_id"),
            requires=list(raw_goal.get("requires", [])),
            metadata=dict(raw_goal.get("metadata", {})),
            status=GoalStatus(raw_goal["status"]),
            intent_ids=list(raw_goal.get("intent_ids", [])),
            result=raw_goal.get("result"),
            error=raw_goal.get("error"),
            created_at=datetime.fromisoformat(raw_goal["created_at"]),
            updated_at=datetime.fromisoformat(raw_goal["updated_at"]),
        )
        intent_runs = [GoalIntentRun(**item) for item in payload.get("intent_runs", [])]
        return GoalRun(
            goal=goal,
            planned_intents=[
                Intent.model_validate(item)
                for item in payload.get("planned_intents", [])
            ],
            intent_runs=intent_runs,
            current_index=int(payload.get("current_index", 0)),
            context=dict(payload.get("context", {})),
            started_at=datetime.fromisoformat(payload["started_at"]),
            completed_at=(
                datetime.fromisoformat(payload["completed_at"])
                if payload.get("completed_at")
                else None
            ),
        )
