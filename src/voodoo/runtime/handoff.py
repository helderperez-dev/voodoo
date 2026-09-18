"""Explicit authority-preserving handoff from prepared work to Execution."""

from __future__ import annotations

from typing import Any

from voodoo.runtime.dispatch import DispatchPlan
from voodoo.runtime.engine import ComputeFn, ExecutionEngine
from voodoo.runtime.execution import Execution
from voodoo.runtime.lineage import LineageEvent, lineage
from voodoo.runtime.work_scheduler import WorkEligibility


class ExecutionHandoff:
    """Submit only eligible prepared work to the canonical ExecutionEngine."""

    def __init__(self, engine: ExecutionEngine) -> None:
        self.engine = engine

    async def execute(
        self,
        plan: DispatchPlan,
        compute: ComputeFn | None = None,
        *,
        actor: str = "system",
        principal: Any | None = None,
    ) -> Execution:
        if plan.scheduling.status is not WorkEligibility.ELIGIBLE:
            raise RuntimeError(

            )
        metadata = plan.work.intent.params.setdefault("_runtime", {})
        if plan.placement is not None:
            metadata["placement"] = {
                "node_id": plan.placement.node_id,
                "reasons": list(plan.placement.reasons),
            }
        execution = await self.engine.execute(
            plan.work.intent,
            compute,
            actor=actor,
            principal=principal,
        )
        lineage.record(
            LineageEvent(
                kind="execution",
                subject_id=execution.id,
                parent_id=plan.work.intent.id,
                reason=f"canonical execution {execution.status.value}",
                metadata={"trace_id": execution.trace_id},
            )
        )
        return execution


__all__ = ["ExecutionHandoff"]
