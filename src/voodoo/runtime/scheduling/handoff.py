"""Explicit authority-preserving handoff from prepared work to Execution."""

from __future__ import annotations

from typing import Any

from voodoo.runtime.scheduling.dispatch import DispatchPlan
from voodoo.runtime.execution.engine import ComputeFn, ExecutionEngine
from voodoo.runtime.execution import Execution
from voodoo.runtime.inspection.lineage import LineageEvent, RuntimeLineage
from voodoo.runtime.inspection.lineage import lineage as default_lineage
from voodoo.runtime.scheduling.work import WorkEligibility


class RemoteExecutionRequired(RuntimeError):
    """Placement selected another node; transport must perform the handoff."""


class ExecutionHandoff:
    """Submit only eligible prepared work to the canonical ExecutionEngine."""

    def __init__(
        self,
        engine: ExecutionEngine,
        *,
        local_node_id: str | None = None,
        lineage: RuntimeLineage | None = None,
    ) -> None:
        self.engine = engine
        self.local_node_id = local_node_id
        self.lineage = lineage or default_lineage

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
                f"work is not eligible for execution: {plan.scheduling.status.value} "
                f"({plan.scheduling.reason})"
            )
        if plan.placement is not None:
            if self.local_node_id is None:
                raise RemoteExecutionRequired(
                    f"work is placed on node {plan.placement.node_id!r}; "
                    "local node identity is required before execution"
                )
            if plan.placement.node_id != self.local_node_id:
                raise RemoteExecutionRequired(
                    f"work is placed on remote node {plan.placement.node_id!r}; "
                    "a FabricExecutor transport must perform the handoff"
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
        self.lineage.record(
            LineageEvent(
                kind="execution",
                subject_id=execution.id,
                parent_id=plan.work.intent.id,
                reason=f"canonical execution {execution.status.value}",
                metadata={"trace_id": execution.trace_id},
            )
        )
        return execution


__all__ = ["ExecutionHandoff", "RemoteExecutionRequired"]
