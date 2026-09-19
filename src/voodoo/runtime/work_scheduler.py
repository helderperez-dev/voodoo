"""Compatibility facade for :mod:`voodoo.runtime.scheduling.work`."""

from voodoo.runtime.scheduling.work import (
    RuntimeScheduler,
    ScheduledWork,
    SchedulingDecision,
    WorkEligibility,
    scheduled_work_from_intent,
)

__all__ = [
    "RuntimeScheduler",
    "ScheduledWork",
    "SchedulingDecision",
    "WorkEligibility",
    "scheduled_work_from_intent",
]
