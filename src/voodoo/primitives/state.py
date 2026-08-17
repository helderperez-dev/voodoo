"""State — the durable truth of the system.

State represents what the system knows to be true. It is durable, inspectable,
and independent from the execution process that manipulates it.

A database is one possible implementation of persistence.
State is the conceptual model.

    process != application

The process is temporary.
The state is the durable identity of the system.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class State(BaseModel):
    """A durable, versioned, inspectable piece of system truth.

    Semantics:
        identity    — `id` and `kind` uniquely identify the state entity
        version     — monotonically incremented on each mutation
        ownership   — `owner` tracks who owns this state
        lifetime    — `expires_at` for temporal validity
        mutation    — `mutate()` produces a new version
        history     — `checkpoint()` / `restore()` for persistence
        consistency — version enables optimistic concurrency
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str = "entity"
    data: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    owner: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # -- mutation ----------------------------------------------------------

    def mutate(self, **changes: Any) -> State:
        """Return a new State with mutations applied (version incremented)."""
        data = {**self.data, **changes}
        now = datetime.now(UTC)
        return self.model_copy(
            update={
                "data": data,
                "version": self.version + 1,
                "updated_at": now,
            }
        )

    # -- persistence -------------------------------------------------------

    def checkpoint(self) -> dict[str, Any]:
        """Serialize for durable persistence."""
        return self.model_dump(mode="json")

    @classmethod
    def restore(cls, data: dict[str, Any]) -> State:
        """Restore from persisted data."""
        return cls.model_validate(data)

    # -- temporal validity -------------------------------------------------

    @property
    def expired(self) -> bool:
        """Whether this state has passed its temporal validity."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    @property
    def valid(self) -> bool:
        """Whether this state is currently valid (not expired)."""
        return not self.expired

    def expire_in(self, seconds: float) -> State:
        """Return a copy with expiration set."""
        return self.model_copy(
            update={"expires_at": datetime.now(UTC) + timedelta(seconds=seconds)}
        )

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description of this state."""
        return {
            "id": self.id,
            "kind": self.kind,
            "version": self.version,
            "owner": self.owner,
            "expired": self.expired,
            "field_count": len(self.data),
        }
