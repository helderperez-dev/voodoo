"""Constraint — what the system must or must not do.

Constraints are not configuration. They are part of the semantics of execution.

    cost < $0.10
    latency < 100ms
    data must remain local
    capability expires in 10 minutes
    human approval required

A future runtime uses constraints to determine:
    whether an operation is allowed
    where it can execute
    which Compute implementation to use
    whether an Effect can happen
    whether an Intent can be delegated
    whether a capability is sufficient

Constraints compose naturally:

    Intent
      + Capability
      + Constraints
            ↓
         Execution
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Constraint(BaseModel):
    """A typed constraint on execution.

    Semantics:
        kind        — category ("cost", "latency", "locality", "approval", etc.)
        operator    — comparison ("<", "<=", "==", ">=", ">", "!=")
        value       — the threshold or requirement
        description — optional human-readable explanation
    """

    kind: str
    operator: str = "<="
    value: Any = None
    description: str | None = None

    # -- evaluation --------------------------------------------------------

    def evaluate(self, actual: Any) -> bool:
        """Check whether `actual` satisfies this constraint."""
        ops = {
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">=": lambda a, b: a >= b,
            ">": lambda a, b: a > b,
        }
        op = ops.get(self.operator)
        if op is None:
            raise ValueError(f"Unknown operator: {self.operator}")
        try:
            return op(actual, self.value)
        except TypeError:
            return False

    # -- convenience constructors -----------------------------------------

    @staticmethod
    def cost(maximum: float) -> Constraint:
        """Maximum cost constraint."""
        return Constraint(
            kind="cost", operator="<=", value=maximum, description=f"cost <= {maximum}"
        )

    @staticmethod
    def latency(maximum_ms: float) -> Constraint:
        """Maximum latency constraint."""
        return Constraint(
            kind="latency",
            operator="<=",
            value=maximum_ms,
            description=f"latency <= {maximum_ms}ms",
        )

    @staticmethod
    def locality(must_be: str = "local") -> Constraint:
        """Data locality constraint."""
        return Constraint(
            kind="locality",
            operator="==",
            value=must_be,
            description=f"data must be {must_be}",
        )

    @staticmethod
    def determinism(required: bool = True) -> Constraint:
        """Determinism requirement."""
        return Constraint(
            kind="determinism",
            operator="==",
            value=required,
            description="execution must be deterministic",
        )

    @staticmethod
    def approval_required() -> Constraint:
        """Human approval required."""
        return Constraint(
            kind="approval",
            operator="==",
            value=True,
            description="human approval required",
        )

    @staticmethod
    def max_amount(amount: float) -> Constraint:
        """Maximum amount constraint (e.g. for payment capabilities)."""
        return Constraint(
            kind="amount",
            operator="<=",
            value=amount,
            description=f"amount <= {amount}",
        )

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description."""
        return {
            "kind": self.kind,
            "operator": self.operator,
            "value": self.value,
            "description": self.description,
        }
