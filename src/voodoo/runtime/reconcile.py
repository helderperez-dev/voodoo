"""Deterministic reconciliation between invalidation and Goal/Intent runtime.

Reconciliation decides whether affected semantic nodes require work. It does not
execute capabilities, bypass policy, or grant authority. The canonical
ExecutionEngine remains the only path from Intent to effects.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.primitives.intent import Intent
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


ReconcileHandler = Callable[[ApplicationNode, Invalidation, Any | None], ReconcileDecision]


class Reconciler:
    """Bounded, vendor-neutral semantic reconciliation dispatcher."""

    def __init__(self, graph: ApplicationGraph, *, max_decisions: int = 128) -> None:
        if max_decisions < 1:
            raise ValueError("max_decisions must be positive")
        self.graph = graph
        self.max_decisions = max_decisions
        self._handlers: dict[ApplicationNodeKind, ReconcileHandler] = {}

    def register(
        self, kind: ApplicationNodeKind, handler: ReconcileHandler
    ) -> Reconciler:
        self._handlers[kind] = handler
        return self

    def reconcile(
        self, invalidation: Invalidation, *, world: Any | None = None
    ) -> tuple[ReconcileDecision, ...]:
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
            decisions.append(handler(node, invalidation, world))
        return tuple(decisions)


__all__ = [
    "ReconcileAction",
    "ReconcileDecision",
    "ReconcileHandler",
    "Reconciler",
]
