"""Execution Graph — observable parent/child execution structure.

The graph makes the runtime's execution tree inspectable: every node is
traceable to an execution, with dependencies, events, results, errors,
timing, resources and effects.

This is not a separate execution system — it is a read view over the
:class:`~voodoo.runtime.engine.ExecutionEngine`'s recorded executions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voodoo.runtime.execution import Execution

__all__ = ["ExecutionNode", "ExecutionGraph"]


@dataclass
class ExecutionNode:
    """A single node in the execution graph."""

    execution: Execution
    children: list[ExecutionNode] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.execution.id

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.execution.id,
            "trace_id": self.execution.trace_id,
            "parent_execution_id": self.execution.parent_execution_id,
            "status": self.execution.status.value,
            "intent": self.execution.intent.name if self.execution.intent else None,
            "actor": self.execution.actor,
            "duration_seconds": self.execution.duration_seconds,
            "cost": self.execution.cost,
            "effects": [e.name for e in self.execution.effects],
            "children": [c.describe() for c in self.children],
        }


@dataclass
class ExecutionGraph:
    """Build a forest of executions from the engine's records.

    Roots are executions without a parent; children are linked via
    ``parent_execution_id``.
    """

    nodes: dict[str, ExecutionNode] = field(default_factory=dict)
    roots: list[ExecutionNode] = field(default_factory=list)

    @classmethod
    def from_executions(cls, executions: list[Execution]) -> ExecutionGraph:
        graph = cls()
        for ex in executions:
            graph.nodes[ex.id] = ExecutionNode(execution=ex)
        for node in graph.nodes.values():
            parent_id = node.execution.parent_execution_id
            if parent_id and parent_id in graph.nodes:
                graph.nodes[parent_id].children.append(node)
            else:
                graph.roots.append(node)
        return graph

    def describe(self) -> list[dict[str, Any]]:
        return [root.describe() for root in self.roots]

    def find(self, execution_id: str) -> ExecutionNode | None:
        return self.nodes.get(execution_id)
