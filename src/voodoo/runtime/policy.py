"""Contextual operational policy for capability-mediated action.

Capabilities answer whether an actor possesses a kind of authority. Policy
answers whether that authority may be exercised *now*, against a particular
world entity, for a particular intent and observed state.

Policy is deliberately downstream of capability possession and upstream of
compute. It never executes effects itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.runtime.context import ExecutionContext
from voodoo.world.models import WorldSnapshot

__all__ = [
    "PolicyDecision",
    "PolicyRequest",
    "PolicyResult",
    "PolicyEngine",
    "PolicyRule",
]


class PolicyDecision(StrEnum):
    """Possible policy outcomes.

    ``ABSTAIN`` means the rule does not apply. The aggregate engine is fail-safe
    with respect to explicit rules: deny dominates approval, approval dominates
    allow. If every rule abstains, capability resolution remains authoritative
    and the request is allowed.
    """

    ABSTAIN = "abstain"
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyRequest:
    """One contextual authorization question."""

    actor: str
    capability: str
    scope: str | None
    context: ExecutionContext | None
    target_entity_id: str | None = None
    world: WorldSnapshot | None = None

    @property
    def intent(self):
        return self.context.intent if self.context is not None else None


@dataclass(frozen=True)
class PolicyResult:
    """Inspectable result of evaluating one or more policy rules."""

    decision: PolicyDecision
    reason: str = ""
    policy: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "policy": self.policy,
            "metadata": dict(self.metadata),
        }


PolicyRule = Callable[[PolicyRequest], PolicyResult | PolicyDecision | None]


@dataclass
class _RegisteredPolicy:
    name: str
    rule: PolicyRule


class PolicyEngine:
    """Evaluate contextual authorization rules deterministically."""

    def __init__(self, *, world: Any | None = None) -> None:
        self.world = world
        self._rules: list[_RegisteredPolicy] = []

    def use_world(self, world: Any | None) -> None:
        """Attach a WorldModel-like query service used to build snapshots."""
        self.world = world

    def register(self, rule: PolicyRule, *, name: str | None = None) -> None:
        """Register one rule in deterministic insertion order."""
        self._rules.append(
            _RegisteredPolicy(
                name=name or getattr(rule, "__name__", rule.__class__.__name__),
                rule=rule,
            )
        )

    def clear(self) -> None:
        self._rules.clear()

    def evaluate(
        self,
        capability: str,
        *,
        scope: str | None = None,
        context: ExecutionContext | None = None,
    ) -> PolicyResult:
        """Evaluate all applicable rules and return the strongest outcome."""
        target_entity_id = self._target_entity_id(context)
        snapshot = self._snapshot(target_entity_id)
        request = PolicyRequest(
            actor=context.actor if context is not None else "unknown",
            capability=capability,
            scope=scope,
            context=context,
            target_entity_id=target_entity_id,
            world=snapshot,
        )

        strongest = PolicyResult(PolicyDecision.ALLOW, reason="no policy denied action")
        priority = {
            PolicyDecision.ABSTAIN: 0,
            PolicyDecision.ALLOW: 1,
            PolicyDecision.REQUIRE_APPROVAL: 2,
            PolicyDecision.DENY: 3,
        }
        for registered in self._rules:
            raw = registered.rule(request)
            result = self._normalize(raw, registered.name)
            if priority[result.decision] > priority[strongest.decision]:
                strongest = result
            if strongest.decision is PolicyDecision.DENY:
                break
        return strongest

    def describe(self) -> dict[str, Any]:
        return {
            "rules": [registered.name for registered in self._rules],
            "world_attached": self.world is not None,
        }

    def _snapshot(self, target_entity_id: str | None) -> WorldSnapshot | None:
        if self.world is None or target_entity_id is None:
            return None
        try:
            return self.world.snapshot(target_entity_id)
        except KeyError:
            return None

    @staticmethod
    def _target_entity_id(context: ExecutionContext | None) -> str | None:
        if context is None:
            return None
        metadata_target = context.metadata.get("target_entity_id")
        if metadata_target is not None:
            return str(metadata_target)
        if context.intent is None:
            return None
        params = context.intent.params
        target = params.get("_target_entity_id", params.get("entity_id"))
        return str(target) if target is not None else None

    @staticmethod
    def _normalize(
        raw: PolicyResult | PolicyDecision | None,
        policy_name: str,
    ) -> PolicyResult:
        if raw is None:
            return PolicyResult(PolicyDecision.ABSTAIN, policy=policy_name)
        if isinstance(raw, PolicyDecision):
            return PolicyResult(raw, policy=policy_name)
        if raw.policy is not None:
            return raw
        return PolicyResult(
            decision=raw.decision,
            reason=raw.reason,
            policy=policy_name,
            metadata=dict(raw.metadata),
        )
