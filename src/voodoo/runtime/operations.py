"""Operational inspection projection for Voodoo Runtime.

The inspector is read-only. It projects the runtime's existing sources of truth
(Executions, Goals, approvals, Policy and World) into one UI/API-friendly view.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

__all__ = ["OperationalRuntime"]


@dataclass
class OperationalRuntime:
    """Read-only projection over a live Voodoo runtime."""

    engine: Any
    goals: Any | None = None
    world: Any | None = None

    def snapshot(self) -> dict[str, Any]:
        executions = sorted(
            self.engine.executions.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        execution_rows = [item.model_dump(mode="json") for item in executions]
        goal_runs = list(self.goals.runs.values()) if self.goals is not None else []
        goal_rows = [run.describe() for run in goal_runs]
        approvals = [item.describe() for item in self.engine.approvals.pending()]
        entities = self._entities()
        execution_statuses = Counter(item.status.value for item in executions)
        goal_statuses = Counter(run.goal.status.value for run in goal_runs)

        payload = {
            "summary": {
                "executions": len(execution_rows),
                "active_executions": sum(
                    1 for item in executions if item.status.active
                ),
                "waiting_executions": execution_statuses.get("waiting", 0),
                "failed_executions": execution_statuses.get("failed", 0)
                + execution_statuses.get("timed_out", 0),
                "goals": len(goal_rows),
                "active_goals": sum(
                    count
                    for status, count in goal_statuses.items()
                    if status not in {"completed", "failed", "cancelled"}
                ),
                "pending_approvals": len(approvals),
                "entities": len(entities),
            },
            "goals": goal_rows,
            "executions": execution_rows,
            "approvals": approvals,
            "entities": entities,
            "policy": self.engine.capabilities.policy.describe(),
            "capabilities": self.engine.capabilities.describe(),
        }
        return json.loads(json.dumps(payload, default=str))

    def _entities(self) -> list[dict[str, Any]]:
        if self.world is None:
            return []
        rows: list[dict[str, Any]] = []
        for entity in self.world.entities():
            relationships = self.world.relationships(entity.id)
            observations = self.world.history(entity.id)
            rows.append(
                {
                    "id": entity.id,
                    "type": entity.type,
                    "properties": dict(entity.properties),
                    "metadata": dict(entity.metadata),
                    "relationship_count": len(relationships),
                    "observation_count": len(observations),
                    "updated_at": entity.updated_at.isoformat(),
                }
            )
        return rows
