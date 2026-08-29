"""Effect — a change caused outside pure computation.

An Effect represents a side effect: writing data, sending an email,
charging a payment, controlling a device.

    COMPUTATION → INTENT → CAPABILITY → EFFECT

Effects are explicit. The framework can answer:
    what effect is about to happen?
    why is it happening?
    which intent caused it?
    which capability authorizes it?
    is it reversible?
    is it idempotent?
    did it succeed?

The more dangerous the effect, the stronger the constraints should be.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EffectStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Effect(BaseModel):
    """An explicit side effect.

    Semantics:
        name        — what effect (e.g. "send_email")
        intent      — `intent_id` links to the causing intent
        capability  — `capability_name` that authorized it
        reversible  — can this effect be undone?
        idempotent  — is repeating it safe?
        status      — lifecycle tracking
        result      — outcome data
        inspectable — `describe()` for machine-readable semantics
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    intent_id: str | None = None
    capability_name: str | None = None
    reversible: bool = False
    idempotent: bool = False
    idempotency_key: str | None = None
    status: EffectStatus = EffectStatus.PENDING
    result: Any | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executed_at: datetime | None = None
    # Authorization context (Sprint 19, ROADMAP §55)
    actor: str | None = None
    principal: str | None = None
    resource: str | None = None
    scope: str | None = None

    # -- lifecycle ---------------------------------------------------------

    def mark_executing(self) -> None:
        """Mark as currently executing."""
        self.status = EffectStatus.EXECUTING

    def mark_succeeded(self, result: Any | None = None) -> None:
        """Mark as successfully completed."""
        self.result = result
        self.status = EffectStatus.SUCCEEDED
        self.executed_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """Mark as failed."""
        self.error = error
        self.status = EffectStatus.FAILED
        self.executed_at = datetime.now(UTC)

    def mark_rolled_back(self) -> None:
        """Mark as rolled back (only if reversible)."""
        if not self.reversible:
            raise ValueError(f"Effect '{self.name}' is not reversible")
        self.status = EffectStatus.ROLLED_BACK

    # -- queries -----------------------------------------------------------

    @property
    def succeeded(self) -> bool:
        return self.status == EffectStatus.SUCCEEDED

    @property
    def failed(self) -> bool:
        return self.status == EffectStatus.FAILED

    @property
    def pending(self) -> bool:
        return self.status == EffectStatus.PENDING

    @property
    def completed(self) -> bool:
        return self.status in (EffectStatus.SUCCEEDED, EffectStatus.FAILED)

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "intent_id": self.intent_id,
            "capability": self.capability_name,
            "actor": self.actor,
            "principal": self.principal,
            "resource": self.resource,
            "scope": self.scope,
            "reversible": self.reversible,
            "idempotent": self.idempotent,
            "idempotency_key": self.idempotency_key,
            "succeeded": self.succeeded,
            "has_result": self.result is not None,
        }
