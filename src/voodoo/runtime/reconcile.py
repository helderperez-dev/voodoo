"""Deterministic reconciliation between invalidation and Goal/Intent runtime.

Reconciliation decides whether affected semantic nodes require work. It does not
execute capabilities, bypass policy, or grant authority. The canonical
ExecutionEngine remains the only path from Intent to effects.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
from enum import StrEnum
from typing import Any

from voodoo.primitives.intent import Intent
from voodoo.runtime.goal import Goal
from voodoo.runtime.application_graph import (
    ApplicationGraph,
    ApplicationNode,
    ApplicationNodeKind,
    Invalidation,
)


class ReconcileAction(StrEnum):
    SATISFIED = "satisfied"
    WAIT = "wait"
    PROPOSE_INTENT = "propose_intent"
    REQUEST_HUMAN = "request_human"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReconcileDecision:
    node_id: str
    action: ReconcileAction
    reason: str
    intents: tuple[Intent, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)



GoalPredicate = Callable[[Goal, Any | None], bool]
GoalIntentFactory = Callable[[Goal, Any | None], Intent | tuple[Intent, ...]]
ReconcileHandler = Callable[
    [ApplicationNode, Invalidation, Any | None], ReconcileDecision
]


@dataclass(frozen=True, slots=True)
class GoalReconciliation:
    goal: Goal
    satisfied: GoalPredicate
    propose: GoalIntentFactory | None = None

    def __call__(
        self, node: ApplicationNode, invalidation: Invalidation, world: Any | None
    ) -> ReconcileDecision:
        snapshot = None
        if world is not None and self.goal.target_entity_id is not None:
            try:
                snapshot = world.snapshot(self.goal.target_entity_id)
            except KeyError:
                snapshot = None

        if self.satisfied(self.goal, snapshot):
            return ReconcileDecision(
                node_id=node.id,
                action=ReconcileAction.SATISFIED,
                reason="goal already satisfied by observed world",
                evidence={"revision": invalidation.revision},
            )
        if self.propose is None:
            return ReconcileDecision(
                node_id=node.id,
                action=ReconcileAction.BLOCKED,
                reason="goal is unsatisfied and has no intent proposal",
                evidence={"revision": invalidation.revision},
            )
        proposed = self.propose(self.goal, snapshot)
        intents = proposed if isinstance(proposed, tuple) else (proposed,)
        for intent in intents:
            intent.params.setdefault("_goal_id", self.goal.id)
            if self.goal.target_entity_id is not None:
                intent.params.setdefault("entity_id", self.goal.target_entity_id)
            for capability in self.goal.requires:
                intent.require(capability)
        return ReconcileDecision(
            node_id=node.id,
            action=ReconcileAction.PROPOSE_INTENT,
            reason="goal is unsatisfied by observed world",
            intents=intents,
            evidence={"revision": invalidation.revision},
        )


@dataclass(frozen=True, slots=True)
class ReconcileGuard:
    cooldown_seconds: float = 0.0
    suppress_duplicates: bool = True
    require_revision: bool = False


class ReconcileLedger:
    """Small in-process safety ledger; durable adapters may persist it later."""

    def __init__(self) -> None:
        self._proposals: dict[str, datetime] = {}

    @staticmethod
    def intent_key(node_id: str, intent: Intent) -> str:
        payload = json.dumps(
            {
                "node_id": node_id,
                "name": intent.name,
                "params": intent.params,
                "requires": sorted(intent.requires),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def recently_proposed(
        self, key: str, *, cooldown_seconds: float, now: datetime
    ) -> bool:
        previous = self._proposals.get(key)
        if previous is None:
            return False
        if cooldown_seconds <= 0:
            return True
        return now - previous < timedelta(seconds=cooldown_seconds)

    def record(self, key: str, *, now: datetime) -> None:
        self._proposals[key] = now


class Reconciler:
    """Bounded, vendor-neutral semantic reconciliation dispatcher."""

    def __init__(
        self,
        graph: ApplicationGraph,
        *,
        max_decisions: int = 128,
        guard: ReconcileGuard | None = None,
        ledger: ReconcileLedger | None = None,
    ) -> None:
        if max_decisions < 1:
            raise ValueError("max_decisions must be positive")
        self.graph = graph
        self.max_decisions = max_decisions
        self.guard = guard or ReconcileGuard()
        self.ledger = ledger or ReconcileLedger()
        self._handlers: dict[ApplicationNodeKind, ReconcileHandler] = {}

    def register(
        self, kind: ApplicationNodeKind, handler: ReconcileHandler
    ) -> Reconciler:
        self._handlers[kind] = handler
        return self

    def reconcile(
        self, invalidation: Invalidation, *, world: Any | None = None
    ) -> tuple[ReconcileDecision, ...]:
        if self.guard.require_revision and invalidation.revision is None:
            return tuple(
                ReconcileDecision(
                    node_id=node_id,
                    action=ReconcileAction.WAIT,
                    reason="fresh revision evidence is required",
                )
                for node_id in invalidation.affected[: self.max_decisions]
            )
        decisions: list[ReconcileDecision] = []
        for index, node_id in enumerate(invalidation.affected):
            if index >= self.max_decisions:
                break
            node = self.graph.get(node_id)
            if node is None:
                decisions.append(
                    ReconcileDecision(
                        node_id=node_id,
                        action=ReconcileAction.FAILED,
                        reason="affected node no longer exists",
                    )
                )
                continue
            handler = self._handlers.get(node.kind)
            if handler is None:
                decisions.append(
                    ReconcileDecision(
                        node_id=node.id,
                        action=ReconcileAction.WAIT,
                        reason=f"no reconciler registered for {node.kind.value}",
                    )
                )
                continue
            decision = handler(node, invalidation, world)
            if (
                decision.action is ReconcileAction.PROPOSE_INTENT
                and self.guard.suppress_duplicates
            ):
                now = datetime.now(UTC)
                accepted: list[Intent] = []
                for intent in decision.intents:
                    key = self.ledger.intent_key(node.id, intent)
                    if self.ledger.recently_proposed(
                        key,
                        cooldown_seconds=self.guard.cooldown_seconds,
                        now=now,
                    ):
                        continue
                    self.ledger.record(key, now=now)
                    accepted.append(intent)
                if not accepted:
                    decision = ReconcileDecision(
                        node_id=node.id,
                        action=ReconcileAction.WAIT,
                        reason="duplicate intent proposal suppressed",
                        evidence=dict(decision.evidence),
                    )
                elif len(accepted) != len(decision.intents):
                    decision = ReconcileDecision(
                        node_id=decision.node_id,
                        action=decision.action,
                        reason=decision.reason,
                        intents=tuple(accepted),
                        evidence=dict(decision.evidence),
                    )
            decisions.append(decision)
        return tuple(decisions)


__all__ = [
    "ReconcileAction",
    "ReconcileDecision",
    "ReconcileGuard",
    "ReconcileLedger",
    "ReconcileHandler",
    "GoalPredicate",
    "GoalIntentFactory",
    "GoalReconciliation",
    "Reconciler",
]
