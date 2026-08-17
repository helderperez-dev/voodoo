"""Intent — what the system is trying to accomplish.

An Intent represents an outcome to achieve, not a function to call.

    function call:  "execute this operation"
    intent:         "achieve this outcome under these conditions"

An Intent has a lifecycle:
    created → queued → evaluating → executing → completed
                                        ↕ paused
                                        ↘ rejected / expired / cancelled

An Intent may require:
    multiple capabilities, multiple effects, multiple compute operations,
    human approval, AI reasoning, retries, waiting, external events.

Intent provides the conceptual bridge between traditional applications
and autonomous systems. AI should consume and produce Intents,
not control the application directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from voodoo.primitives.constraint import Constraint


class IntentStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    EVALUATING = "evaluating"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Intent(BaseModel):
    """An outcome the system is trying to accomplish.

    Semantics:
        outcome    — `name` + `params` describe what to achieve
        lifecycle  — `status` tracks progression through the state machine
        capability  — `requires` lists needed capabilities
        constraint  — `constraints` define execution limits
        temporal    — `deadline` for time-bounded execution
        effects     — `effect_ids` tracks produced side effects
        inspectable — `describe()` for machine-readable semantics
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    status: IntentStatus = IntentStatus.CREATED
    deadline: datetime | None = None
    requires: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    effect_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: Any | None = None
    error: str | None = None

    # -- lifecycle transitions --------------------------------------------

    def _transition(self, new_status: IntentStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def queue(self) -> None:
        """Move to queued status."""
        self._transition(IntentStatus.QUEUED)

    def evaluate(self) -> None:
        """Begin evaluating capability/constraint requirements."""
        self._transition(IntentStatus.EVALUATING)

    def execute(self) -> None:
        """Begin execution."""
        self._transition(IntentStatus.EXECUTING)

    def pause(self) -> None:
        """Pause execution."""
        self._transition(IntentStatus.PAUSED)

    def resume(self) -> None:
        """Resume from paused."""
        self._transition(IntentStatus.EXECUTING)

    def complete(self, result: Any | None = None) -> None:
        """Mark as completed with optional result."""
        self.result = result
        self._transition(IntentStatus.COMPLETED)

    def reject(self, reason: str = "") -> None:
        """Mark as rejected."""
        self.error = reason
        self._transition(IntentStatus.REJECTED)

    def cancel(self) -> None:
        """Cancel the intent."""
        self._transition(IntentStatus.CANCELLED)

    # -- queries -----------------------------------------------------------

    @property
    def expired(self) -> bool:
        """Whether the deadline has passed."""
        if self.deadline is None:
            return False
        return datetime.now(UTC) >= self.deadline

    @property
    def active(self) -> bool:
        """Whether this intent is still in progress."""
        return self.status in (
            IntentStatus.CREATED,
            IntentStatus.QUEUED,
            IntentStatus.EVALUATING,
            IntentStatus.EXECUTING,
            IntentStatus.PAUSED,
        )

    @property
    def finished(self) -> bool:
        """Whether this intent has reached a terminal state."""
        return self.status in (
            IntentStatus.COMPLETED,
            IntentStatus.REJECTED,
            IntentStatus.EXPIRED,
            IntentStatus.CANCELLED,
        )

    # -- composition -------------------------------------------------------

    def require(self, capability_name: str) -> Intent:
        """Add a required capability. Returns self for chaining."""
        if capability_name not in self.requires:
            self.requires.append(capability_name)
        return self

    def constrain(self, constraint: Constraint) -> Intent:
        """Add an execution constraint. Returns self for chaining."""
        self.constraints.append(constraint)
        return self

    def with_deadline(self, seconds: float) -> Intent:
        """Set a deadline. Returns self for chaining."""
        self.deadline = datetime.now(UTC) + timedelta(seconds=seconds)
        return self

    def add_effect(self, effect_id: str) -> Intent:
        """Record a produced effect. Returns self for chaining."""
        if effect_id not in self.effect_ids:
            self.effect_ids.append(effect_id)
        return self

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "active": self.active,
            "expired": self.expired,
            "requires": self.requires,
            "constraint_count": len(self.constraints),
            "effect_count": len(self.effect_ids),
            "has_result": self.result is not None,
        }
