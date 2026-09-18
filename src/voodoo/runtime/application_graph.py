"""Semantic application graph for Voodoo.

The ApplicationGraph describes the structure of the running application. It is
not the World Model and it is not an execution engine. Runtime subsystems may
contribute semantic nodes and relationships so inspection, validation and later
dependency/reconciliation mechanisms share one representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable


class ApplicationNodeKind(StrEnum):
    APPLICATION = "application"
    PAGE = "page"
    API = "api"
    MODEL = "model"
    TASK = "task"
    CAPABILITY = "capability"
    GOAL = "goal"
    AGENT = "agent"
    TOOL = "tool"
    EFFECT = "effect"
    OBSERVER = "observer"
    RESOURCE = "resource"
    DEVICE = "device"
    SERVICE = "service"
    NODE = "node"
    EXTENSION = "extension"


@dataclass(frozen=True, slots=True)
class ApplicationNode:
    id: str
    kind: ApplicationNodeKind
    name: str
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ApplicationEdge:
    source: str
    relation: str
    target: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "metadata": dict(self.metadata),
        }


class ApplicationGraph:
    """Canonical in-process semantic graph for one Voodoo application."""

    def __init__(self, application_id: str = "application") -> None:
        self.application_id = application_id
        self._nodes: dict[str, ApplicationNode] = {}
        self._edges: set[tuple[str, str, str]] = set()
        self._edge_records: list[ApplicationEdge] = []
        self.add_node(
            ApplicationNode(
                id=application_id,
                kind=ApplicationNodeKind.APPLICATION,
                name=application_id,
            )
        )

    @property
    def nodes(self) -> tuple[ApplicationNode, ...]:
        return tuple(self._nodes.values())

    @property
    def edges(self) -> tuple[ApplicationEdge, ...]:
        return tuple(self._edge_records)

    def add_node(self, node: ApplicationNode) -> ApplicationNode:
        existing = self._nodes.get(node.id)
        if existing is not None and existing != node:
            raise ValueError(f"Application node {node.id!r} is already registered")
        self._nodes[node.id] = node
        return node

    def node(
        self,
        kind: ApplicationNodeKind,
        name: str,
        *,
        node_id: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApplicationNode:
        return self.add_node(
            ApplicationNode(
                id=node_id or f"{kind.value}:{name}",
                kind=kind,
                name=name,
                source=source,
                metadata=metadata or {},
            )
        )

    def get(self, node_id: str) -> ApplicationNode | None:
        return self._nodes.get(node_id)

    def connect(
        self,
        source: str,
        relation: str,
        target: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ApplicationEdge:
        if source not in self._nodes:
            raise KeyError(f"Unknown application graph source: {source}")
        if target not in self._nodes:
            raise KeyError(f"Unknown application graph target: {target}")
        key = (source, relation, target)
        if key in self._edges:
            return next(
                edge
                for edge in self._edge_records
                if (edge.source, edge.relation, edge.target) == key
            )
        edge = ApplicationEdge(source, relation, target, metadata or {})
        self._edges.add(key)
        self._edge_records.append(edge)
        return edge

    def dependents(self, node_id: str, relation: str | None = None) -> tuple[ApplicationNode, ...]:
        ids = {
            edge.source
            for edge in self._edge_records
            if edge.target == node_id and (relation is None or edge.relation == relation)
        }
        return tuple(self._nodes[node_id] for node_id in ids)

    def dependencies(self, node_id: str, relation: str | None = None) -> tuple[ApplicationNode, ...]:
        ids = {
            edge.target
            for edge in self._edge_records
            if edge.source == node_id and (relation is None or edge.relation == relation)
        }
        return tuple(self._nodes[target] for target in ids)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for edge in self._edge_records:
            if edge.source not in self._nodes:
                errors.append(f"edge source does not exist: {edge.source}")
            if edge.target not in self._nodes:
                errors.append(f"edge target does not exist: {edge.target}")
        return errors

    def describe(self) -> dict[str, Any]:
        return {
            "application_id": self.application_id,
            "nodes": [node.describe() for node in self.nodes],
            "edges": [edge.describe() for edge in self.edges],
        }


class ApplicationGraphContributor:
    """Small stable seam used by Runtime subsystems and future extensions."""

    def contribute(self, graph: ApplicationGraph) -> None:
        raise NotImplementedError


def build_application_graph(app: Any, contributors: Iterable[Any] = ()) -> ApplicationGraph:
    """Build a useful graph from stable Runtime surfaces.

    Discovery is deliberately conservative. Only semantic information already
    exposed by Voodoo is included; arbitrary Python objects are not crawled.
    """
    graph = ApplicationGraph()

    for route in getattr(app, "routes", ()):
        path = getattr(route, "path", None)
        if not path:
            continue
        methods = sorted(getattr(route, "methods", ()) or ())
        safe_page_methods = {"GET", "HEAD"}
        kind = (
            ApplicationNodeKind.API
            if methods and not set(methods).issubset(safe_page_methods)
            else ApplicationNodeKind.PAGE
        )
        node = graph.node(
            kind,
            path,
            node_id=f"{kind.value}:{path}",
            metadata={"methods": methods},
        )
        graph.connect(graph.application_id, "contains", node.id)

    try:
        from voodoo.runtime.engine import engine

        description = engine.capabilities.describe()
        for name in description.get("capabilities", ()):
            node = graph.node(ApplicationNodeKind.CAPABILITY, str(name))
            graph.connect(graph.application_id, "provides", node.id)
    except Exception:
        # Inspection must remain available while an application is only partly
        # configured. Validation surfaces structural errors separately.
        pass

    for contributor in contributors:
        contribute = getattr(contributor, "contribute", None)
        if contribute is not None:
            contribute(graph)

    return graph


__all__ = [
    "ApplicationEdge",
    "ApplicationGraph",
    "ApplicationGraphContributor",
    "ApplicationNode",
    "ApplicationNodeKind",
    "build_application_graph",
]
