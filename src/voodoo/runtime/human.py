"""Human-in-the-Loop — humans as first-class compute participants.

Human approval participates in the execution model like any other
compute: an execution that requires approval enters the ``waiting``
state with a pending :class:`Approval`. A human then decides:

    engine.approve(execution_id, by="admin")   → resumed as child execution
    engine.deny(execution_id, by="admin")      → execution fails

The :class:`Human` compute participant raises
:class:`~voodoo.runtime.errors.ApprovalRequired` until the runtime
re-executes it with an approval decision in the context metadata —
making the whole flow deterministic and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from voodoo.primitives.intent import Intent
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.engine import ComputeFn, ComputeResult
from voodoo.runtime.errors import ApprovalRequired

if TYPE_CHECKING:
    from voodoo.runtime.execution import Execution

__all__ = ["ApprovalStatus", "Approval", "ApprovalRegistry", "Human", "ask_human"]


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class Approval:
    """A pending human decision attached to a waiting execution."""

    execution_id: str
    trace_id: str
    capability: str | None = None
    question: str = ""
    requested_by: str = "system"
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    reason: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # resumable payload — what to re-run once approved
    intent: Intent | None = None
    compute: ComputeFn | None = None
    output_type: type | None = None
    context: ExecutionContext | None = None

    @property
    def decided(self) -> bool:
        return self.status is not ApprovalStatus.PENDING

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "capability": self.capability,
            "question": self.question,
            "requested_by": self.requested_by,
            "status": self.status.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "reason": self.reason,
        }


@dataclass
class ApprovalRegistry:
    """Tracks pending and decided approvals."""

    records: dict[str, Approval] = field(default_factory=dict)

    def create(
        self,
        *,
        execution: Execution,
        capability: str | None = None,
        question: str = "",
        requested_by: str = "system",
        intent: Intent | None = None,
        compute: ComputeFn | None = None,
        output_type: type | None = None,
        context: ExecutionContext | None = None,
    ) -> Approval:
        approval = Approval(
            execution_id=execution.id,
            trace_id=execution.trace_id,
            capability=capability,
            question=question or (f"Capability '{capability}' requested" if capability else "Approval required"),
            requested_by=requested_by,
            intent=intent,
            compute=compute,
            output_type=output_type,
            context=context,
        )
        self.records[execution.id] = approval
        return approval

    def get(self, execution_id: str) -> Approval | None:
        return self.records.get(execution_id)

    def pending(self) -> list[Approval]:
        return [a for a in self.records.values() if a.status is ApprovalStatus.PENDING]

    def decide(
        self, execution_id: str, status: ApprovalStatus, *, by: str, reason: str | None = None
    ) -> Approval | None:
        approval = self.records.get(execution_id)
        if approval is None or approval.decided:
            return None
        approval.status = status
        approval.decided_by = by
        approval.decided_at = datetime.now(UTC)
        approval.reason = reason
        return approval


def ask_human(question: str, *, capability: str | None = None) -> ComputeFn:
    """Build a compute participant that waits for a human decision.

    On first run it raises :class:`ApprovalRequired` (the execution enters
    ``waiting``). When the runtime resumes it after
    ``engine.approve(...)`` the decision is present in the context
    metadata and the compute completes with the decision as its value.
    """

    async def human_compute(ctx: ExecutionContext) -> ComputeResult:
        decision = ctx.metadata.get("approval")
        if decision == ApprovalStatus.APPROVED.value:
            return ComputeResult(
                value=ctx.metadata.get("approval_note") or "approved",
                states=[],
            )
        raise ApprovalRequired(
            question,
            execution_id=ctx.execution_id,
            trace_id=ctx.trace_id,
            context={"capability": capability, "question": question, "human": True},
        )

    return human_compute


#: Class alias matching the spec's "Compute = Human" vocabulary.
Human = ask_human
