"""Voodoo-specific operational UI components.

This layer visualizes canonical runtime concepts. It never creates a parallel
source of truth: callers pass Execution/Goal/Approval/Entity/Device-like
objects or rows from ``OperationalRuntime.snapshot()``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from voodoo.ui.component import Component
from voodoo.ui.interactive import Button
from voodoo.ui.library import Heading, Text
from voodoo.ui.product import (
    EmptyState,
    EventRow,
    Metric,
    StatusBadge,
    Timeline,
)

EventHandler = Callable[..., Any] | str


def _read(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _nested(value: Any, *keys: str, default: Any = None) -> Any:
    current = value
    for key in keys:
        current = _read(current, key, None)
        if current is None:
            return default
    return current


def _status(value: Any, default: str = "unknown") -> str:
    raw = _read(value, "status", default)
    enum_value = getattr(raw, "value", raw)
    return str(enum_value or default).lower()


def _identifier(value: Any, default: str = "unknown") -> str:
    for key in ("id", "execution_id", "goal_id", "device_id", "agent_id"):
        found = _read(value, key)
        if found is not None:
            return str(found)
    return default


class RuntimeStatus(Component):
    """High-signal summary of an ``OperationalRuntime.snapshot()`` payload."""

    style = "runtime-status"

    def __init__(self, snapshot: Mapping[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        summary = snapshot.get("summary", {})
        failed = int(summary.get("failed_executions", 0) or 0)
        waiting = int(summary.get("waiting_executions", 0) or 0)
        runtime_state = "degraded" if failed else "healthy"
        self.children = (
            _SystemHeading("Runtime", StatusBadge(runtime_state, pulse=not failed)),
            _MetricStrip(
                Metric("Executions", summary.get("executions", 0)),
                Metric("Active", summary.get("active_executions", 0)),
                Metric("Waiting", waiting),
                Metric("Approvals", summary.get("pending_approvals", 0)),
                Metric("Entities", summary.get("entities", 0)),
            ),
        )


class AgentStatus(Component):
    """Canonical agent identity/status summary."""

    style = "agent-status"

    def __init__(self, agent: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        name = _read(agent, "name") or _identifier(agent, "Agent")
        status = _status(agent, "idle")
        model = _read(agent, "model") or _nested(agent, "model", "name")
        capabilities = _read(agent, "capabilities", []) or []
        self.children = (
            _SystemHeading(str(name), StatusBadge(status)),
            Text(f"{len(capabilities)} capabilities", class_="vd-system-meta"),
            Text(str(model), class_="vd-system-meta") if model else None,
        )


class DeviceCard(Component):
    """Operational device object with identity, connection and capability count."""

    style = "device-card"

    def __init__(self, device: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        device_id = _identifier(device, "device")
        name = _read(device, "name") or device_id
        status = (
            _read(device, "connection_state") or _read(device, "status") or "unknown"
        )
        capabilities = _read(device, "capabilities", []) or []
        last_seen = _read(device, "last_seen_at") or _read(device, "updated_at")
        self.children = (
            _SystemHeading(
                str(name), StatusBadge(str(getattr(status, "value", status)))
            ),
            Text(device_id, class_="vd-system-id"),
            _SystemFacts(
                _Fact("Capabilities", len(capabilities)),
                _Fact("Last seen", str(last_seen) if last_seen else "Unknown"),
            ),
        )


class ExecutionStatus(Component):
    """Compact rendering of one canonical Execution."""

    style = "execution-status"

    def __init__(self, execution: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        execution_id = _identifier(execution, "execution")
        status = _status(execution)
        intent_name = (
            _nested(execution, "intent", "name")
            or _read(execution, "intent")
            or "Execution"
        )
        duration = _read(execution, "duration_seconds")
        self.children = (
            _SystemHeading(str(intent_name), StatusBadge(status)),
            Text(execution_id, class_="vd-system-id"),
            Text(
                f"{float(duration):.2f}s" if isinstance(duration, (int, float)) else "",
                class_="vd-system-meta",
            )
            if duration is not None
            else None,
        )


class ExecutionTimeline(Timeline):
    """Chronological view generated directly from canonical executions."""

    def __init__(self, executions: Iterable[Any], **kwargs: Any) -> None:
        rows: list[EventRow] = []
        for execution in executions:
            intent = (
                _nested(execution, "intent", "name")
                or _read(execution, "intent")
                or "Execution"
            )
            created = _read(execution, "created_at") or _read(execution, "started_at")
            rows.append(
                EventRow(
                    str(intent),
                    detail=_identifier(execution),
                    timestamp=str(created) if created else None,
                    status=_status(execution),
                )
            )
        super().__init__(*rows, label="Execution timeline", **kwargs)


class ApprovalCard(Component):
    """Human-in-the-loop decision surface over a canonical Approval."""

    style = "approval-card"

    def __init__(
        self,
        approval: Any,
        *,
        on_approve: EventHandler | None = None,
        on_deny: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        approval_id = _identifier(
            approval, str(_read(approval, "approval_id", "approval"))
        )
        reason = (
            _read(approval, "reason")
            or _read(approval, "message")
            or "Human approval required."
        )
        capability = _read(approval, "capability") or _read(
            approval, "capability_name"
        )
        actions: list[Component] = []
        if on_deny is not None:
            actions.append(
                Button("Deny", on_click=on_deny, variant="ghost", value=approval_id)
            )
        if on_approve is not None:
            actions.append(
                Button(
                    "Approve", on_click=on_approve, variant="primary", value=approval_id
                )
            )
        self.children = (
            _SystemHeading("Approval required", StatusBadge("waiting")),
            Text(str(reason), class_="vd-system-description"),
            Text(str(capability), class_="vd-system-id") if capability else None,
            _ActionRow(*actions) if actions else None,
        )


class WorldEntityInspector(Component):
    """Readable projection of an Entity or OperationalRuntime entity row."""

    style = "world-entity-inspector"

    def __init__(self, entity: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        entity_id = _identifier(entity, "entity")
        entity_type = _read(entity, "type", "entity")
        properties = _read(entity, "properties", {}) or {}
        relation_count = _read(entity, "relationship_count")
        observation_count = _read(entity, "observation_count")
        property_rows = [
            _PropertyRow(str(key), value) for key, value in dict(properties).items()
        ]
        self.children = (
            _SystemHeading(str(entity_type).title(), StatusBadge("active")),
            Text(entity_id, class_="vd-system-id"),
            _SystemFacts(
                _Fact(
                    "Relationships",
                    relation_count if relation_count is not None else "—",
                ),
                _Fact(
                    "Observations",
                    observation_count if observation_count is not None else "—",
                ),
            ),
            _PropertyList(*property_rows)
            if property_rows
            else EmptyState(
                "No observed properties", "This entity has no projected properties yet."
            ),
        )


class ObservationFeed(Timeline):
    """Chronological evidence feed for World observations."""

    def __init__(self, observations: Iterable[Any], **kwargs: Any) -> None:
        rows: list[EventRow] = []
        for observation in observations:
            property_name = (
                _read(observation, "property")
                or _read(observation, "key")
                or "Observation"
            )
            value = _read(observation, "value")
            source = _read(observation, "source")
            confidence = _read(observation, "confidence")
            observed_at = _read(observation, "observed_at")
            meta_parts = []
            if source:
                meta_parts.append(f"source: {source}")
            if confidence is not None:
                meta_parts.append(f"confidence: {confidence}")
            rows.append(
                EventRow(
                    str(property_name),
                    detail=str(value),
                    timestamp=str(observed_at) if observed_at else None,
                    meta=" · ".join(meta_parts) if meta_parts else None,
                )
            )
        super().__init__(*rows, label="Observation feed", **kwargs)


class CapabilityList(Component):
    """Compact list of explicit authority/capability names."""

    style = "capability-list"

    def __init__(self, capabilities: Iterable[Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        items = []
        for capability in capabilities:
            name = _read(capability, "name") or str(capability)
            items.append(_Capability(str(name)))
        self.children = (
            tuple(items)
            if items
            else (Text("No capabilities", class_="vd-system-meta"),)
        )


class PolicyDecision(Component):
    """Human-readable contextual policy decision."""

    style = "policy-decision"

    def __init__(self, decision: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        outcome = (
            _read(decision, "decision")
            or _read(decision, "outcome")
            or _read(decision, "status")
            or "unknown"
        )
        raw = str(getattr(outcome, "value", outcome)).lower()
        reason = _read(decision, "reason") or _read(decision, "explanation")
        capability = _read(decision, "capability")
        self.children = (
            _SystemHeading("Policy", StatusBadge(raw)),
            Text(str(reason), class_="vd-system-description") if reason else None,
            Text(str(capability), class_="vd-system-id") if capability else None,
        )


class EdgeNode(DeviceCard):
    """DeviceCard specialization for an Edge participant."""

    style = "edge-node"


class TelemetryPanel(Component):
    """Small live metric grid for operational telemetry."""

    style = "telemetry-panel"

    def __init__(self, metrics: Mapping[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.children = tuple(
            Metric(str(name).replace("_", " ").title(), value)
            for name, value in metrics.items()
        )


class _SystemHeading(Component):
    auto_id = False

    def __init__(self, title: str, status: Component | None = None) -> None:
        super().__init__(class_="vd-system-heading")
        self.children = (
            Heading(title, level=3, size="md"),
            status,
        )


class _MetricStrip(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-system-metric-strip")


class _SystemFacts(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-system-facts")


class _Fact(Component):
    auto_id = False

    def __init__(self, label: str, value: Any) -> None:
        super().__init__(
            Text(label, class_="vd-system-fact-label"),
            Text(value, class_="vd-system-fact-value"),
            class_="vd-system-fact",
        )


class _ActionRow(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-system-actions")


class _PropertyList(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-property-list")


class _PropertyRow(Component):
    auto_id = False

    def __init__(self, key: str, value: Any) -> None:
        super().__init__(
            Text(key, class_="vd-property-key"),
            Text(value, class_="vd-property-value"),
            class_="vd-property-row",
        )


class _Capability(Component):
    auto_id = False

    def __init__(self, name: str) -> None:
        super().__init__(name, class_="vd-capability")
