"""Capability resolution — enforceable runtime authority.

This is the layer that turns :class:`~voodoo.primitives.capability.Capability`
from a conceptual model into an enforced runtime property.

Given an actor, an intent and a requested operation, the resolver decides:

    allowed | denied | requires approval

Capability possession is necessary but no longer always sufficient. When a
contextual policy engine is attached, the granted capability is evaluated
against actor, intent, target entity and current world state before compute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.primitives.capability import Capability
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.errors import ApprovalRequired, CapabilityDenied
from voodoo.runtime.policy import PolicyDecision, PolicyEngine, PolicyResult

__all__ = ["Resolution", "CapabilityResolver", "SENSITIVE_CAPABILITIES"]


SENSITIVE_CAPABILITIES: frozenset[str] = frozenset(
    {
        "filesystem.write",
        "network.request",
        "shell.execute",
        "secrets.read",
        "payment.execute",
        "email.send",
    }
)


class Resolution(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class CapabilityResolver:
    """Resolve possessed authority and contextual permission to exercise it."""

    capabilities: dict[str, Capability] = field(default_factory=dict)
    approval_capabilities: set[str] = field(default_factory=set)
    policy: PolicyEngine = field(default_factory=PolicyEngine)
    last_policy_result: PolicyResult | None = None

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
        """Resolve capability possession, then contextual operational policy."""
        if name in SENSITIVE_CAPABILITIES:
            baseline = self._resolve_sensitive(name, scope=scope, context=context)
        else:
            baseline = self._resolve_standard(name, scope=scope, context=context)

        if baseline is not Resolution.ALLOWED:
            self.last_policy_result = None
            return baseline

        policy_result = self.policy.evaluate(name, scope=scope, context=context)
        self.last_policy_result = policy_result
        if policy_result.decision is PolicyDecision.DENY:
            return Resolution.DENIED
        if policy_result.decision is PolicyDecision.REQUIRE_APPROVAL:
            return Resolution.REQUIRES_APPROVAL
        return Resolution.ALLOWED

    def _resolve_sensitive(
        self,
        name: str,
        *,
        scope: str | None = None,
        context: ExecutionContext | None = None,
    ) -> Resolution:
        """Resolve a sensitive capability — requires explicit grant."""
        if context is not None and context.has_capability(name, scope=scope):
            return self._check_approval(name)
        cap = self.capabilities.get(name)
        if cap is not None and cap.valid:
            if scope is not None and cap.scope is not None and cap.scope != scope:
                return Resolution.DENIED
            return self._check_approval(name)
        return Resolution.DENIED

    def _resolve_standard(
        self,
        name: str,
        *,
        scope: str | None = None,
        context: ExecutionContext | None = None,
    ) -> Resolution:
        """Resolve a standard capability — normal registry rules."""
        if context is not None and context.has_capability(name, scope=scope):
            return self._check_approval(name)
        cap = self.capabilities.get(name)
        if cap is None or not cap.valid:
            return Resolution.DENIED
        if scope is not None and cap.scope is not None and cap.scope != scope:
            return Resolution.DENIED
        return self._check_approval(name)

    def _check_approval(self, name: str) -> Resolution:
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
        """Authorize or raise a structured capability/policy error."""
        resolution = self.resolve(name, scope=scope, context=context)
        policy = self.last_policy_result
        policy_context = policy.describe() if policy is not None else None

        if resolution is Resolution.DENIED:
            reason = policy.reason if policy and policy.reason else "capability denied"
            raise CapabilityDenied(
                f"Capability '{name}' denied for actor "
                f"'{context.actor if context else 'unknown'}': {reason}",
                execution_id=execution_id,
                trace_id=context.trace_id if context else None,
                context={
                    "capability": name,
                    "scope": scope,
                    "policy": policy_context,
                },
            )
        if resolution is Resolution.REQUIRES_APPROVAL:
            reason = policy.reason if policy and policy.reason else "human approval required"
            raise ApprovalRequired(
                f"Capability '{name}' requires human approval: {reason}",
                execution_id=execution_id,
                trace_id=context.trace_id if context else None,
                context={
                    "capability": name,
                    "scope": scope,
                    "policy": policy_context,
                },
            )

    def describe(self) -> dict[str, Any]:
        return {
            "capabilities": [cap.name for cap in self.capabilities.values()],
            "approval_required": sorted(self.approval_capabilities),
            "sensitive": sorted(SENSITIVE_CAPABILITIES),
            "policy": self.policy.describe(),
        }
