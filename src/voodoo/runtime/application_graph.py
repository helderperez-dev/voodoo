"""Semantic application graph for Voodoo.

The ApplicationGraph describes the structure of the running application. It is
not the World Model and it is not an execution engine. Runtime subsystems may
contribute semantic nodes and relationships so inspection, validation and later
dependency/reconciliation mechanisms share one representation.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from typing import Any


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
        if existing is not None:
            if existing != node:
                raise ValueError(f"Application node {node.id!r} is already registered")
            return existing
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

    def dependents(
        self, node_id: str, relation: str | None = None
    ) -> tuple[ApplicationNode, ...]:
        ids = {
            edge.source
            for edge in self._edge_records
            if edge.target == node_id and (relation is None or edge.relation == relation)
        }
        return tuple(self._nodes[node_id] for node_id in ids)

    def dependencies(
        self, node_id: str, relation: str | None = None
    ) -> tuple[ApplicationNode, ...]:
        ids = {
            edge.target
            for edge in self._edge_records
            if edge.source == node_id and (relation is None or edge.relation == relation)
        }
        return tuple(self._nodes[target] for target in ids)

    def affected(
        self, node_id: str, *, relations: set[str] | None = None
    ) -> tuple[ApplicationNode, ...]:
        """Return transitive dependents affected by a semantic node change."""
        if node_id not in self._nodes:
            raise KeyError(f"Unknown application graph node: {node_id}")
        seen: set[str] = set()
        pending = [node_id]
        while pending:
            target = pending.pop()
            for edge in self._edge_records:
                if edge.target != target:
                    continue
                if relations is not None and edge.relation not in relations:
                    continue
                if edge.source in seen or edge.source == node_id:
                    continue
                seen.add(edge.source)
                pending.append(edge.source)
        return tuple(self._nodes[item] for item in sorted(seen))

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
            "nodes": [
                node.describe() for node in sorted(self.nodes, key=lambda item: item.id)
            ],
            "edges": [
                edge.describe()
                for edge in sorted(
                    self.edges, key=lambda item: (item.source, item.relation, item.target)
                )
            ],
        }

    @property
    def fingerprint(self) -> str:
        """Stable content identity for snapshots, caches and change detection."""
        payload = json.dumps(
            self.describe(), sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        payload = self.describe()
        payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class ChangeReason(StrEnum):
    STRUCTURE = "structure"
    STATE = "state"
    OBSERVATION = "observation"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"


@dataclass(frozen=True, slots=True)
class Invalidation:
    source: str
    affected: tuple[str, ...]
    reason: ChangeReason
    revision: str | None = None


class InvalidationEngine:
    """Deterministically translate a semantic change into affected graph nodes.

    This engine understands only Voodoo semantic relationships. External
    systems integrate by contributing generic resources, observations,
    capabilities and effects; vendor SDKs never belong in the Runtime core.
    """

    def __init__(self, graph: ApplicationGraph) -> None:
        self.graph = graph

    def invalidate(
        self,
        source: str,
        *,
        reason: ChangeReason = ChangeReason.STATE,
        revision: str | None = None,
        relations: set[str] | None = None,
    ) -> Invalidation:
        affected = tuple(
            node.id for node in self.graph.affected(source, relations=relations)
        )
        return Invalidation(
            source=source,
            affected=affected,
            reason=reason,
            revision=revision,
        )


@dataclass(frozen=True, slots=True)
class ApplicationGraphChange:
    added_nodes: tuple[str, ...] = ()
    removed_nodes: tuple[str, ...] = ()
    added_edges: tuple[tuple[str, str, str], ...] = ()
    removed_edges: tuple[tuple[str, str, str], ...] = ()

    @property
    def changed(self) -> bool:
        return bool(
            self.added_nodes
            or self.removed_nodes
            or self.added_edges
            or self.removed_edges
        )


def diff_application_graph(
    previous: ApplicationGraph, current: ApplicationGraph
) -> ApplicationGraphChange:
    previous_nodes = {node.id for node in previous.nodes}
    current_nodes = {node.id for node in current.nodes}
    previous_edges = {
        (edge.source, edge.relation, edge.target) for edge in previous.edges
    }
    current_edges = {
        (edge.source, edge.relation, edge.target) for edge in current.edges
    }
    return ApplicationGraphChange(
        added_nodes=tuple(sorted(current_nodes - previous_nodes)),
        removed_nodes=tuple(sorted(previous_nodes - current_nodes)),
        added_edges=tuple(sorted(current_edges - previous_edges)),
        removed_edges=tuple(sorted(previous_edges - current_edges)),
    )


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    name: str
    version: str
    requires_voodoo: str | None = None
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class ExtensionRegistry:
    """Explicit activation registry. Installed does not mean enabled."""

    def __init__(self) -> None:
        self._extensions: dict[str, Extension] = {}

    def use(self, extension: Extension) -> Extension:
        name = extension.manifest.name
        existing = self._extensions.get(name)
        if existing is not None and existing is not extension:
            raise ValueError(f"Extension {name!r} is already enabled")
        self._extensions[name] = extension
        return extension

    def all(self) -> tuple[Extension, ...]:
        return tuple(self._extensions.values())

    def contribute(self, graph: ApplicationGraph) -> None:
        for extension in self.all():
            extension.contribute(graph)


class Extension:
    """Stable Runtime-facing contract for external Voodoo integrations."""

    manifest: ExtensionManifest

    def contribute(self, graph: ApplicationGraph) -> None:
        extension = graph.node(
            ApplicationNodeKind.EXTENSION,
            self.manifest.name,
            metadata={
                "version": self.manifest.version,
                "requires_voodoo": self.manifest.requires_voodoo,
                **self.manifest.metadata,
            },
        )
        graph.connect(graph.application_id, "uses", extension.id)
        for capability in self.manifest.capabilities:
            capability_id = f"capability:{capability}"
            if graph.get(capability_id) is None:
                graph.node(ApplicationNodeKind.CAPABILITY, capability)
            graph.connect(extension.id, "provides", capability_id)


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

    try:
        from voodoo.data.base import _get_table_name, _models

        for model in _models:
            name = model.__name__
            node = graph.node(
                ApplicationNodeKind.MODEL,
                name,
                source=f"{model.__module__}:{model.__qualname__}",
                metadata={"table": _get_table_name(model)},
            )
            graph.connect(graph.application_id, "contains", node.id)
    except Exception:
        pass

    try:
        from voodoo.workers.queue import _workers

        for name, worker in _workers.items():
            node = graph.node(
                ApplicationNodeKind.TASK,
                name,
                source=f"{worker.__module__}:{worker.__qualname__}",
            )
            graph.connect(graph.application_id, "contains", node.id)
    except Exception:
        pass

    try:
        from voodoo.ai.tools.registry import default_registry

        for spec in default_registry.all():
            node = graph.node(
                ApplicationNodeKind.TOOL,
                spec.name,
                source=spec.source or None,
                metadata={"version": spec.version},
            )
            graph.connect(graph.application_id, "contains", node.id)
            for permission in spec.permissions:
                capability_id = f"capability:{permission}"
                if graph.get(capability_id) is None:
                    graph.node(ApplicationNodeKind.CAPABILITY, permission)
                graph.connect(node.id, "requires", capability_id)
    except Exception:
        pass

    for contributor in contributors:
        contribute = getattr(contributor, "contribute", None)
        if contribute is not None:
            contribute(graph)

    return graph


__all__ = [
    "ApplicationEdge",
    "ApplicationGraph",
    "ApplicationGraphChange",
    "ChangeReason",
    "Invalidation",
    "InvalidationEngine",
    "Extension",
    "ExtensionRegistry",
    "ExtensionManifest",
    "ApplicationGraphContributor",
    "diff_application_graph",
    "ApplicationNode",
    "ApplicationNodeKind",
    "build_application_graph",
]
