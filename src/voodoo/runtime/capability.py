"""Capability resolution — enforceable runtime authority.

This is the layer that turns :class:`~voodoo.primitives.capability.Capability`
from a conceptual model into an enforced runtime property.

Given an actor, an intent and a requested operation, the resolver decides:

    allowed | denied | requires approval

Authorization failures become structured
:class:`~voodoo.runtime.errors.CapabilityDenied` errors rather than
silent misses. Every meaningful agent action is attributable to a
capability, which is the core security property of Voodoo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.primitives.capability import Capability
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.errors import ApprovalRequired, CapabilityDenied

__all__ = ["Resolution", "CapabilityResolver"]


class Resolution(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class CapabilityResolver:
    """Resolve whether an actor may perform an operation.

    Capabilities are registered per name. A request is allowed when a
    valid, non-expired, non-revoked capability matches the requested
    name (and scope, if a scope is required). Capabilities flagged with
    an ``approval`` constraint surface as ``REQUIRES_APPROVAL``.
    """

    capabilities: dict[str, Capability] = field(default_factory=dict)
    approval_capabilities: set[str] = field(default_factory=set)

    def register(self, capability: Capability) -> None:
        """Register a capability template (by name)."""
        self.capabilities[capability.name] = capability

    def require_approval(self, name: str) -> None:
        """Mark a capability as requiring human approval before use."""
        self.approval_capabilities.add(name)

    def resolve(
        self,
        name: str,
        *,
        scope: str | None = None,
        context: ExecutionContext | None = None,
    ) -> Resolution:
        """Resolve a capability request.

        Context-granted capabilities take precedence (they are the
        delegated authority for an in-flight execution). Otherwise the
        registry is consulted.
        """
        if context is not None and context.has_capability(name, scope=scope):
            if name in self.approval_capabilities:
                return Resolution.REQUIRES_APPROVAL
            return Resolution.ALLOWED

        cap = self.capabilities.get(name)
        if cap is None or not cap.valid:
            return Resolution.DENIED
        if scope is not None and cap.scope is not None and cap.scope != scope:
            return Resolution.DENIED
        if name in self.approval_capabilities:
            return Resolution.REQUIRES_APPROVAL
        return Resolution.ALLOWED

    def authorize(
        self,
        name: str,
        *,
        scope: str | None = None,
        context: ExecutionContext | None = None,
        execution_id: str | None = None,
    ) -> None:
        """Authorize or raise a structured error.

        Raises :class:`CapabilityDenied` when denied and
        :class:`ApprovalRequired` when human approval is needed.
        """
        res = self.resolve(name, scope=scope, context=context)
        if res is Resolution.DENIED:
            raise CapabilityDenied(
                f"Capability '{name}' denied for actor "
                f"'{context.actor if context else 'unknown'}'",
                execution_id=execution_id,
                trace_id=context.trace_id if context else None,
                context={"capability": name, "scope": scope},
            )
        if res is Resolution.REQUIRES_APPROVAL:
            raise ApprovalRequired(
                f"Capability '{name}' requires human approval",
                execution_id=execution_id,
                trace_id=context.trace_id if context else None,
                context={"capability": name, "scope": scope},
            )

    def describe(self) -> dict[str, Any]:
        return {
            "capabilities": [c.name for c in self.capabilities.values()],
            "approval_required": sorted(self.approval_capabilities),
        }
