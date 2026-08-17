"""Capability — explicit permission to do something.

A Capability represents something an entity is explicitly allowed to do.
It is more fundamental than role-based authorization.

    capability("email.send")
    capability("database.read")
    capability("payment.execute")

Capabilities are:
    explicit     — a named action, not an implicit role
    composable   — multiple capabilities combine
    revocable     — can be revoked at any time
    delegatable   — transferable without transferring identity
    scoped        — can target specific resources
    inspectable   — machine-readable
    time-limited  — can expire
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


class Capability(BaseModel):
    """An explicit, composable, revocable permission.

    Semantics:
        explicit     — `name` identifies the action (e.g. "email.send")
        scoped       — `scope` limits to a specific resource
        constrained  — `constraints` carry fine-grained limits
        delegatable  — `delegate()` transfers without transferring identity
        revocable    — `revoke()` immediately invalidates
        time-limited — `expires_at` for temporal scoping
        inspectable  — `describe()` for machine-readable semantics
    """

    name: str
    scope: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    delegate_to: str | None = None
    expires_at: datetime | None = None
    revoked: bool = False
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    issued_by: str | None = None

    # -- validity ----------------------------------------------------------

    @property
    def expired(self) -> bool:
        """Whether this capability has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    @property
    def valid(self) -> bool:
        """Whether this capability is currently valid."""
        return not self.revoked and not self.expired

    # -- delegation --------------------------------------------------------

    def delegate(self, to: str, **constraint_overrides: Any) -> Capability:
        """Delegate this capability to another entity.

        The delegate receives the same permission but cannot exceed
        the original constraints. Additional constraints may narrow scope.
        """
        merged = {**self.constraints, **constraint_overrides}
        return Capability(
            name=self.name,
            scope=self.scope,
            constraints=merged,
            delegate_to=to,
            expires_at=self.expires_at,
            issued_by=self.issued_by or f"delegated:{self.name}",
        )

    # -- revocation --------------------------------------------------------

    def revoke(self) -> None:
        """Immediately invalidate this capability."""
        self.revoked = True

    # -- convenience constructors -----------------------------------------

    @staticmethod
    def timed(name: str, expires_in: float, **kwargs: Any) -> Capability:
        """Create a time-limited capability."""
        return Capability(
            name=name,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            **kwargs,
        )

    @staticmethod
    def scoped(name: str, resource: str, **kwargs: Any) -> Capability:
        """Create a resource-scoped capability."""
        return Capability(name=name, scope=resource, **kwargs)

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description."""
        return {
            "name": self.name,
            "scope": self.scope,
            "valid": self.valid,
            "expired": self.expired,
            "revoked": self.revoked,
            "delegated_to": self.delegate_to,
            "constraints": self.constraints,
        }
