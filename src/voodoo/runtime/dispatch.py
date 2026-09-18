"""Thin bridge from reconciliation decisions to scheduling and placement.

Dispatch prepares governed work. It never executes an Intent and never grants
capabilities; canonical Execution remains the authority boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from voodoo.runtime.fabric import PlacementDecision, RuntimeFabric
from voodoo.runtime.reconcile import ReconcileAction, ReconcileDecision
from voodoo.runtime.work_scheduler import (
    RuntimeScheduler,
    ScheduledWork,
    SchedulingDecision,
    WorkEligibility,
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
    ) -> None:
        self.scheduler = scheduler or RuntimeScheduler()
        self.fabric = fabric

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
            work = ScheduledWork(intent=intent)
            eligibility = self.scheduler.evaluate(
                work,
                completed=completed,
                running=running,
                unavailable_resources=unavailable_resources,
                backpressured=backpressured,
            )
            if eligibility.status is not WorkEligibility.ELIGIBLE:
                plans.append(DispatchPlan(work=work, scheduling=eligibility))
                continue

            placement = None
            if self.fabric is not None:
                placement = self.fabric.place(work.placement)
            plans.append(
                DispatchPlan(work=work, scheduling=eligibility, placement=placement)
            )
        return tuple(plans)


__all__ = ["DispatchPlan", "RuntimeDispatcher"]
