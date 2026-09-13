from types import SimpleNamespace

from voodoo.adapters.voodoo_css import VoodooCSSAdapter
from voodoo.ui import (
    AgentStatus,
    ApprovalCard,
    CapabilityList,
    DeviceCard,
    EdgeNode,
    ExecutionStatus,
    ExecutionTimeline,
    ObservationFeed,
    PolicyDecision,
    RuntimeStatus,
    TelemetryPanel,
    WorldEntityInspector,
)
from voodoo.ui.rendering import render_page
from voodoo.ui.styles import current_adapter, set_style_adapter


def _native():
    original = current_adapter()
    set_style_adapter(VoodooCSSAdapter())
    return original


def test_runtime_status_projects_operational_snapshot():
    original = _native()
    try:
        snapshot = {
            "summary": {
                "executions": 12,
                "active_executions": 2,
                "waiting_executions": 1,
                "failed_executions": 0,
                "pending_approvals": 1,
                "entities": 5,
            }
        }
        html = RuntimeStatus(snapshot).render()
        assert "Runtime" in html
        assert "Healthy" in html
        assert "Executions" in html
        assert ">12<" in html
    finally:
        set_style_adapter(original)


def test_runtime_status_becomes_degraded_when_failures_exist():
    original = _native()
    try:
        html = RuntimeStatus({"summary": {"failed_executions": 2}}).render()
        assert "Degraded" in html
    finally:
        set_style_adapter(original)


def test_agent_and_device_components_do_not_create_parallel_state():
    original = _native()
    try:
        agent = SimpleNamespace(
            id="agent-1",
            name="Ops Agent",
            status="running",
            model="provider:model",
            capabilities=["world.read", "device.command"],
        )
        device = {
            "id": "edge-1",
            "name": "Workshop Node",
            "status": "online",
            "capabilities": ["temperature.read"],
            "updated_at": "now",
        }
        agent_html = AgentStatus(agent).render()
        device_html = DeviceCard(device).render()
        edge_html = EdgeNode(device).render()
        assert "Ops Agent" in agent_html
        assert "Running" in agent_html
        assert "Workshop Node" in device_html
        assert "Online" in device_html
        assert "vd-edge-node" in edge_html
    finally:
        set_style_adapter(original)


def test_execution_components_project_canonical_fields():
    original = _native()
    try:
        execution = SimpleNamespace(
            id="exec-1",
            status=SimpleNamespace(value="completed"),
            intent=SimpleNamespace(name="device.inspect"),
            duration_seconds=0.42,
            created_at="2026-09-13T00:00:00Z",
        )
        html = ExecutionStatus(execution).render()
        timeline = ExecutionTimeline([execution]).render()
        assert "device.inspect" in html
        assert "Completed" in html
        assert "exec-1" in html
        assert "0.42s" in html
        assert "device.inspect" in timeline
        assert "Execution timeline" in timeline
    finally:
        set_style_adapter(original)


def test_approval_card_wires_python_actions_semantically():
    original = _native()

    async def approve(value):
        return value

    async def deny(value):
        return value

    try:
        html = ApprovalCard(
            {"id": "ap-1", "reason": "Refund needs review", "capability": "refund.issue"},
            on_approve=approve,
            on_deny=deny,
        ).render()
        assert "Approval required" in html
        assert "Refund needs review" in html
        assert html.count("data-vd-event-click=") == 2
        assert "onclick=" not in html
        assert 'value="ap-1"' in html
    finally:
        set_style_adapter(original)


def test_world_entity_inspector_uses_projected_world_data():
    original = _native()
    try:
        entity = {
            "id": "robot-1",
            "type": "robot",
            "properties": {"battery.level": 0.82, "mode": "idle"},
            "relationship_count": 3,
            "observation_count": 14,
        }
        html = WorldEntityInspector(entity).render()
        assert "Robot" in html
        assert "robot-1" in html
        assert "battery.level" in html
        assert "0.82" in html
        assert "Relationships" in html
    finally:
        set_style_adapter(original)


def test_observation_capability_policy_and_telemetry_components():
    original = _native()
    try:
        observations = [
            {
                "property": "battery.level",
                "value": 0.82,
                "source": "bms",
                "confidence": 0.99,
                "observed_at": "now",
            }
        ]
        assert "battery.level" in ObservationFeed(observations).render()
        caps = CapabilityList(["world.read", {"name": "device.command"}]).render()
        assert "world.read" in caps
        assert "device.command" in caps
        decision = PolicyDecision(
            {"decision": "waiting", "reason": "Human approval required", "capability": "refund.issue"}
        ).render()
        assert "Human approval required" in decision
        telemetry = TelemetryPanel({"cpu_usage": "12%", "latency_ms": 8}).render()
        assert "Cpu Usage" in telemetry
        assert "12%" in telemetry
    finally:
        set_style_adapter(original)


def test_native_page_includes_voodoo_system_styles():
    original = _native()
    try:
        html = render_page(RuntimeStatus({"summary": {}}))
        assert "Voodoo System Components" in html
        assert ".vd-runtime-status" in html
        assert ".vd-approval-card" in html
    finally:
        set_style_adapter(original)
