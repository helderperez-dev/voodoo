"""Planner — resolve an Intent to a compute participant + execution strategy.

The planner maps intent requirements to registered compute participants
(agents, deterministic compute, tools, workers, humans, workflows).
Resolution is deterministic-first: an exact capability match chooses the
most specific participant, secondary matches become fallbacks, and
approval-gated capabilities surface as ``requires_approval`` steps.

The resulting :class:`Plan` drives execution: ``WorkflowStrategy.ADAPTIVE``
and :class:`~voodoo.runtime.adaptive.AdaptiveSupervisor` consume it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from voodoo.primitives.intent import Intent
from voodoo.runtime.workflow import WorkflowStrategy

__all__ = [
    "ParticipantKind",
    "ComputeParticipant",
    "PlanStep",
    "Plan",
    "Planner",
]

ParticipantKind = Literal["agent", "compute", "tool", "worker", "human", "workflow"]


@dataclass
class ComputeParticipant:
    """A registered compute participant that can satisfy capabilities."""

    name: str
    kind: ParticipantKind
    capabilities: list[str] = field(default_factory=list)
    description: str = ""
    #: callable run as deterministic compute (kind == "compute")
    compute: Callable[..., Any] | None = None
    #: agent instance to run (kind == "agent")
    agent: Any | None = None


@dataclass
class PlanStep:
    """A planned execution step for one required capability."""

    participant: str
    kind: ParticipantKind
    capabilities: list[str] = field(default_factory=list)
    requires_approval: bool = False
    fallback: str | None = None


@dataclass
class Plan:
    """The outcome of planning: strategy + per-capability step assignment."""

    intent: Intent
    strategy: WorkflowStrategy
    steps: list[PlanStep] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)

    def describe(self) -> dict[str, Any]:
        """Machine-readable plan for ``inspect plan``."""
        return {
            "intent": self.intent.name,
            "strategy": self.strategy.value,
            "steps": [
                {
                    "participant": s.participant,
                    "kind": s.kind,
                    "capabilities": s.capabilities,
                    "requires_approval": s.requires_approval,
                    "fallback": s.fallback,
                }
                for s in self.steps
            ],
            "unresolved": self.unresolved,
            "decisions": self.decisions,
        }


class Planner:
    """Deterministic capability → compute resolution."""

    def __init__(self, engine: Any | None = None) -> None:
        self.engine = engine
        self.participants: dict[str, ComputeParticipant] = {}
        self._approval_capabilities: set[str] = set()

    # -- registration ------------------------------------------------------

    def register(self, participant: ComputeParticipant) -> None:
        """Register a compute participant."""
        self.participants[participant.name] = participant

    def require_approval(self, capability: str) -> None:
        """Mark a capability as needing human approval."""
        self._approval_capabilities.add(capability)

    # -- resolution --------------------------------------------------------

    def _match(self, capability: str) -> list[ComputeParticipant]:
        """Participants able to satisfy a capability, most-specific first.

        "Most-specific" = the participant with the fewest other
        capabilities (narrowest authority) wins, so a dedicated tool is
        preferred over a general-purpose agent.
        """
        matches = [
            p for p in self.participants.values() if capability in p.capabilities
        ]
        return sorted(matches, key=lambda p: len(p.capabilities))

    def _pick_strategy(self, intent: Intent) -> WorkflowStrategy:
        matched = [self._match(c) for c in intent.requires]
        kinds = {m[0].kind for m in matched if m}
        if "human" in kinds:
            return WorkflowStrategy.SEQUENTIAL
        if len([m for m in matched if m]) > 1:
            return WorkflowStrategy.PARALLEL
        return WorkflowStrategy.SEQUENTIAL

    def plan(
        self, intent: Intent, *, strategy: WorkflowStrategy | None = None
    ) -> Plan:
        """Resolve an intent to a plan: strategy + one step per capability."""
        plan = Plan(intent=intent, strategy=strategy or self._pick_strategy(intent))

        for capability in intent.requires:
            matches = self._match(capability)
            if not matches:
                plan.unresolved.append(capability)
                plan.decisions.append(f"{capability} -> unresolved")
                continue
            primary = matches[0]
            plan.steps.append(
                PlanStep(
                    participant=primary.name,
                    kind=primary.kind,
                    capabilities=[capability],
                    requires_approval=capability in self._approval_capabilities,
                    fallback=matches[1].name if len(matches) > 1 else None,
                )
            )
            plan.decisions.append(
                f"{capability} -> {primary.name} ({primary.kind})"
                + (f" fallback={matches[1].name}" if len(matches) > 1 else "")
            )
        return plan

    def describe(self) -> dict[str, Any]:
        """Registered surface for ``inspect capabilities`` style views."""
        return {
            "participants": [
                {
                    "name": p.name,
                    "kind": p.kind,
                    "capabilities": p.capabilities,
                }
                for p in self.participants.values()
            ],
            "approval_capabilities": sorted(self._approval_capabilities),
        }
