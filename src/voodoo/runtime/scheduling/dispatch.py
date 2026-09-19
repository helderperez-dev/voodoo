"""Thin bridge from reconciliation decisions to scheduling and placement.

Dispatch prepares governed work. It never executes an Intent and never grants
capabilities; canonical Execution remains the authority boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from voodoo.runtime.distributed.fabric import PlacementDecision, RuntimeFabric
from voodoo.runtime.inspection.lineage import LineageEvent, RuntimeLineage
from voodoo.runtime.inspection.lineage import lineage as default_lineage
from voodoo.runtime.reconciliation.reconcile import ReconcileAction, ReconcileDecision
from voodoo.runtime.scheduling.work import (
    RuntimeScheduler,
    ScheduledWork,
    SchedulingDecision,
    WorkEligibility,
    scheduled_work_from_intent,
)


@dataclass(frozen=True, slots=True)
class DispatchPlan:
    work: ScheduledWork
    scheduling: SchedulingDecision
    placement: PlacementDecision | None = None


class RuntimeDispatcher:
    def __init__(
        self,
        scheduler: RuntimeScheduler | None = None,
        *,
        fabric: RuntimeFabric | None = None,
        lineage: RuntimeLineage | None = None,
    ) -> None:
        self.scheduler = scheduler or RuntimeScheduler()
        self.fabric = fabric
        self.lineage = lineage or default_lineage

    def prepare(
        self,
        decision: ReconcileDecision,
        *,
        completed: set[str] | None = None,
        running: dict[str, int] | None = None,
        unavailable_resources: set[str] | None = None,
        backpressured: set[str] | None = None,
    ) -> tuple[DispatchPlan, ...]:
        if decision.action is not ReconcileAction.PROPOSE_INTENT:
            return ()

        plans: list[DispatchPlan] = []
        for intent in decision.intents:
            work = scheduled_work_from_intent(intent)
            self.lineage.record(
                LineageEvent(
                    kind="intent.proposed",
                    subject_id=intent.id,
                    parent_id=decision.node_id,
                    reason=decision.reason,
                )
            )
            eligibility = self.scheduler.evaluate(
                work,
                completed=completed,
                running=running,
                unavailable_resources=unavailable_resources,
                backpressured=backpressured,
            )
            self.lineage.record(
                LineageEvent(
                    kind="schedule.decision",
                    subject_id=intent.id,
                    parent_id=decision.node_id,
                    reason=eligibility.reason,
                    metadata={"status": eligibility.status.value},
                )
            )
            if eligibility.status is not WorkEligibility.ELIGIBLE:
                plans.append(DispatchPlan(work=work, scheduling=eligibility))
                continue

            placement = None
            if self.fabric is not None:
                placement = self.fabric.place(work.placement)
                self.lineage.record(
                    LineageEvent(
                        kind="placement.decision",
                        subject_id=intent.id,
                        parent_id=decision.node_id,
                        reason=", ".join(placement.reasons),
                        metadata={"node_id": placement.node_id},
                    )
                )
            plans.append(
                DispatchPlan(work=work, scheduling=eligibility, placement=placement)
            )
        return tuple(plans)


__all__ = ["DispatchPlan", "RuntimeDispatcher"]
