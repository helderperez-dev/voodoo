"""Planner — resolve an Intent to a compute participant + execution strategy.

The planner maps intent requirements to registered compute participants
(agents, deterministic compute, tools, workers, humans, workflows).
Resolution is deterministic-first: an exact capability match chooses the
most specific participant, secondary matches become fallbacks, and
approval-gated capabilities surface as ``requires_approval`` steps.

Sprint 27 adds a bounded operational context seam. The planner may rank
otherwise-authorized participants using explicit World/runtime context, but it
does not grant authority and it does not delegate policy decisions to AI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from voodoo.primitives.intent import Intent
from voodoo.runtime.workflow import WorkflowStrategy

__all__ = [
    "ParticipantKind",
    "PlanningContext",
    "ParticipantRanker",
    "ComputeParticipant",
    "PlanStep",
    "Plan",
    "Planner",
]

ParticipantKind = Literal["agent", "compute", "tool", "worker", "human", "workflow"]


@dataclass(frozen=True)
class PlanningContext:
    """Structured operational context used only for participant selection.

    ``world`` is a JSON-friendly projection supplied by the caller (normally a
    target entity's current properties). It is evidence/context, never an
    authority grant. ``prior_results`` lets bounded replanning prefer a compute
    participant based on already-observed execution results.
    """

    goal_id: str | None = None
    target_entity_id: str | None = None
    world: Mapping[str, Any] = field(default_factory=dict)
    prior_results: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> PlanningContext:
        if value is None:
            return cls()
        raw_world = value.get("world") or value.get("world_state") or {}
        raw_results = value.get("upstream") or value.get("prior_results") or {}
        return cls(
            goal_id=value.get("goal_id"),
            target_entity_id=value.get("target_entity_id"),
            world=raw_world if isinstance(raw_world, Mapping) else {},
            prior_results=raw_results if isinstance(raw_results, Mapping) else {},
            metadata=value,
        )


ParticipantRanker = Callable[["ComputeParticipant", PlanningContext], float]


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
    #: explicit operational selection hints; never an authority grant
    metadata: dict[str, Any] = field(default_factory=dict)


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
    """Deterministic capability → compute resolution with bounded context ranking."""

    def __init__(
        self,
        engine: Any | None = None,
        *,
        ranker: ParticipantRanker | None = None,
    ) -> None:
        self.engine = engine
        self.participants: dict[str, ComputeParticipant] = {}
        self._approval_capabilities: set[str] = set()
        self.ranker = ranker

    def register(self, participant: ComputeParticipant) -> None:
        """Register a compute participant."""
        self.participants[participant.name] = participant

    def require_approval(self, capability: str) -> None:
        """Mark a capability as needing human approval."""
        self._approval_capabilities.add(capability)

    @staticmethod
    def _world_get(world: Mapping[str, Any], path: str) -> Any:
        node: Any = world
        for part in path.split("."):
            if not isinstance(node, Mapping) or part not in node:
                return None
            node = node[part]
        return node

    def _operational_score(
        self, participant: ComputeParticipant, context: PlanningContext
    ) -> float:
        """Score explicit deterministic operational hints.

        Supported metadata:
        - ``available=False`` makes a participant ineligible.
        - ``entity_id`` prefers a participant colocated with the target entity.
        - ``when`` is a mapping of dotted World property paths to exact expected
          values. A mismatch makes the participant ineligible.
        - ``priority`` is a numeric tie-breaker.
        """
        metadata = participant.metadata
        if metadata.get("available") is False:
            return float("-inf")
        conditions = metadata.get("when") or {}
        if isinstance(conditions, Mapping):
            for path, expected in conditions.items():
                if self._world_get(context.world, str(path)) != expected:
                    return float("-inf")
        score = float(metadata.get("priority", 0.0) or 0.0)
        if (
            context.target_entity_id
            and metadata.get("entity_id") == context.target_entity_id
        ):
            score += 100.0
        if self.ranker is not None:
            score += float(self.ranker(participant, context))
        return score

    def _match(
        self,
        capability: str,
        context: PlanningContext | None = None,
    ) -> list[ComputeParticipant]:
        """Participants able to satisfy a capability, best candidate first.

        Authority still comes from capability/policy enforcement in the runtime.
        Planning context only ranks participants that already advertise the
        required capability. Equal candidates retain registration order so
        existing deterministic primary/fallback semantics stay stable.
        """
        context = context or PlanningContext()
        ranked: list[tuple[float, int, ComputeParticipant]] = []
        for order, participant in enumerate(self.participants.values()):
            if capability not in participant.capabilities:
                continue
            score = self._operational_score(participant, context)
            if score == float("-inf"):
                continue
            ranked.append((score, order, participant))
        return [
            participant
            for _, _, participant in sorted(
                ranked,
                key=lambda item: (
                    -item[0],
                    len(item[2].capabilities),
                    item[1],
                ),
            )
        ]

    def _pick_strategy(
        self, intent: Intent, context: PlanningContext | None = None
    ) -> WorkflowStrategy:
        matched = [self._match(c, context) for c in intent.requires]
        kinds = {m[0].kind for m in matched if m}
        if "human" in kinds:
            return WorkflowStrategy.SEQUENTIAL
        if len([m for m in matched if m]) > 1:
            return WorkflowStrategy.PARALLEL
        return WorkflowStrategy.SEQUENTIAL

    def plan(
        self,
        intent: Intent,
        *,
        strategy: WorkflowStrategy | None = None,
        context: PlanningContext | Mapping[str, Any] | None = None,
    ) -> Plan:
        """Resolve an intent to a plan using explicit operational context."""
        planning_context = (
            context
            if isinstance(context, PlanningContext)
            else PlanningContext.from_mapping(context)
        )
        plan = Plan(
            intent=intent,
            strategy=strategy or self._pick_strategy(intent, planning_context),
        )

        for capability in intent.requires:
            matches = self._match(capability, planning_context)
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
                    "metadata": dict(p.metadata),
                }
                for p in self.participants.values()
            ],
            "approval_capabilities": sorted(self._approval_capabilities),
        }
