"""Time — a first-class runtime concept.

Time is not reduced to setTimeout, cron, or timestamps.

Future systems are persistent and asynchronous. They:
    wait, resume, expire, retry, schedule, observe, react, defer

The runtime conceptually understands:
    now, duration, deadline, expiration, schedule,
    before, after, interval, temporal state

Time works naturally with other primitives:
    a capability may expire
    an intent may have a deadline
    a state may have temporal validity
    an effect may be scheduled
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel


class TimeSpec(BaseModel):
    """Temporal specification for an operation.

    Semantics:
        deadline     — when the operation must complete
        expires_at   — when the operation becomes invalid
        schedule     — cron-like or interval specification
        retry_after  — delay before retrying on failure (seconds)
        max_retries  — maximum retry attempts
        interval     — periodic execution interval (seconds)
    """

    deadline: datetime | None = None
    expires_at: datetime | None = None
    schedule: str | None = None
    retry_after: float | None = None
    max_retries: int | None = None
    interval: float | None = None

    # -- factories ---------------------------------------------------------

    @staticmethod
    def with_deadline(seconds: float) -> TimeSpec:
        """Create a spec with a deadline from now."""
        return TimeSpec(deadline=datetime.now(UTC) + timedelta(seconds=seconds))

    @staticmethod
    def with_expiration(seconds: float) -> TimeSpec:
        """Create a spec that expires after the given seconds."""
        return TimeSpec(expires_at=datetime.now(UTC) + timedelta(seconds=seconds))

    @staticmethod
    def with_retry(retry_after: float, max_retries: int = 3) -> TimeSpec:
        """Create a spec with retry settings."""
        return TimeSpec(retry_after=retry_after, max_retries=max_retries)

    @staticmethod
    def with_interval(seconds: float) -> TimeSpec:
        """Create a periodic execution spec."""
        return TimeSpec(interval=seconds)

    # -- queries -----------------------------------------------------------

    @property
    def expired(self) -> bool:
        """Whether the expiration has passed."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    @property
    def deadline_passed(self) -> bool:
        """Whether the deadline has passed."""
        if self.deadline is None:
            return False
        return datetime.now(UTC) >= self.deadline

    @property
    def remaining(self) -> float | None:
        """Seconds remaining until deadline. None if no deadline."""
        if self.deadline is None:
            return None
        delta = (self.deadline - datetime.now(UTC)).total_seconds()
        return max(delta, 0.0)

    def to_schedule_record(self, name: str, task_type: str) -> dict:
        """Convert this TimeSpec into a schedule record (Sprint 5).

        Returns a dict with kind/spec/next_run_at for the scheduler.
        Returns None if this TimeSpec has no schedule or interval.
        """
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        if self.schedule is not None:
            # cron-like or at/after spec
            return {
                "name": name,
                "kind": "cron" if " " in self.schedule else "at",
                "spec": self.schedule,
                "next_run_at": now,
                "task_type": task_type,
            }
        if self.interval is not None:
            return {
                "name": name,
                "kind": "interval",
                "spec": str(int(self.interval))
                if self.interval == int(self.interval)
                else str(self.interval),
                "next_run_at": now + timedelta(seconds=self.interval),
                "task_type": task_type,
            }
        return None

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description."""
        return {
            "has_deadline": self.deadline is not None,
            "deadline_passed": self.deadline_passed,
            "expired": self.expired,
            "remaining_seconds": self.remaining,
            "has_schedule": self.schedule is not None,
            "has_retry": self.retry_after is not None,
            "max_retries": self.max_retries,
            "interval": self.interval,
        }
