"""Tests for the Mesh Network: emit/on/expose, event envelope, namespaces."""

from __future__ import annotations

import json

import pytest

from voodoo.mesh import MeshNetwork, _make_envelope, _validate_namespace, mesh

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_mesh():
    """Fresh mesh instance state between tests."""
    mesh.event_handlers.clear()
    mesh.active_nodes.clear()
    mesh.exposed_functions.clear()
    yield
    mesh.event_handlers.clear()
    mesh.active_nodes.clear()
    mesh.exposed_functions.clear()


# ---------------------------------------------------------------------------
# Namespace enforcement
# ---------------------------------------------------------------------------


def test_validate_namespace_accepts_dotted_event():
    _validate_namespace("agent.started")  # should not raise
    _validate_namespace("mesh.node.connected")


def test_validate_namespace_rejects_non_namespaced_event():
    with pytest.raises(ValueError, match="namespaced"):
        _validate_namespace("started")


@pytest.mark.asyncio
async def test_broadcast_rejects_non_namespaced_event():
    with pytest.raises(ValueError, match="namespaced"):
        await mesh.broadcast("started", {})


@pytest.mark.asyncio
async def test_emit_rejects_non_namespaced_event():
    with pytest.raises(ValueError, match="namespaced"):
        await mesh.emit("started", {})


@pytest.mark.asyncio
async def test_on_rejects_non_namespaced_event():
    with pytest.raises(ValueError, match="namespaced"):

        @mesh.on("not_namespaced")
        def handler(payload):
            pass


# ---------------------------------------------------------------------------
# emit / on
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_fires_local_handler():
    received = []

    @mesh.on("test.fired")
    async def handler(payload):
        received.append(payload)

    await mesh.emit("test.fired", {"key": "value"})
    assert received == [{"key": "value"}]


@pytest.mark.asyncio
async def test_emit_fires_sync_handler():
    received = []

    @mesh.on("test.sync")
    def handler(payload):
        received.append(payload)

    await mesh.emit("test.sync", {"x": 1})
    assert received == [{"x": 1}]


@pytest.mark.asyncio
async def test_emit_fires_multiple_handlers():
    results = []

    @mesh.on("test.multi")
    async def h1(payload):
        results.append(1)

    @mesh.on("test.multi")
    async def h2(payload):
        results.append(2)

    await mesh.emit("test.multi", {})
    assert results == [1, 2]


@pytest.mark.asyncio
async def test_emit_is_alias_for_broadcast():
    """emit() should behave identically to broadcast()."""
    received = []

    @mesh.on("test.alias")
    async def handler(payload):
        received.append(payload)

    await mesh.emit("test.alias", {"data": True})
    assert received == [{"data": True}]


# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------


def test_make_envelope_contains_required_fields():
    env = _make_envelope("agent.started", {"run_id": "123"})
    assert "id" in env
    assert "ts" in env
    assert "source" in env
    assert "correlation_id" in env
    assert env["event"] == "agent.started"
    assert env["payload"] == {"run_id": "123"}


def test_make_envelope_with_explicit_correlation_id():
    env = _make_envelope("agent.completed", {}, correlation_id="trace-abc")
    assert env["correlation_id"] == "trace-abc"


def test_make_envelope_correlation_id_from_trace_var():
    from voodoo.telemetry import trace_id_var

    trace_id_var.set("my-trace-id")
    try:
        env = _make_envelope("test.event", {})
        assert env["correlation_id"] == "my-trace-id"
    finally:
        trace_id_var.set(None)


def test_make_envelope_has_unique_id():
    env1 = _make_envelope("test.event", {})
    env2 = _make_envelope("test.event", {})
    assert env1["id"] != env2["id"]


# ---------------------------------------------------------------------------
# expose
# ---------------------------------------------------------------------------


def test_expose_registers_function():
    @mesh.expose()
    def my_func():
        """Does something."""
        return 42

    assert "my_func" in mesh.exposed_functions
    assert mesh.exposed_functions["my_func"]() == 42


def test_expose_with_custom_name():
    @mesh.expose(name="custom_name")
    def some_func():
        return "ok"

    assert "custom_name" in mesh.exposed_functions


def test_expose_bridges_to_mcp():
    @mesh.expose()
    def exposed_tool():
        """A tool via mesh."""
        return "result"

    from voodoo.mcp import mcp as mcp_instance

    assert "exposed_tool" in mcp_instance.tools


# ---------------------------------------------------------------------------
# Isolated MeshNetwork
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_isolated_mesh_network_emit():
    net = MeshNetwork()
    received = []

    @net.on("isolated.event")
    async def handler(payload):
        received.append(payload)

    await net.emit("isolated.event", {"test": True})
    assert received == [{"test": True}]


@pytest.mark.asyncio
async def test_isolated_mesh_does_not_leak_to_global():
    net = MeshNetwork()
    global_received = []

    @mesh.on("global.only")
    async def global_handler(payload):
        global_received.append(payload)

    @net.on("global.only")
    async def local_handler(payload):
        pass

    await net.emit("global.only", {"from": "local"})
    assert global_received == []  # global handler not called by local mesh


# ---------------------------------------------------------------------------
# Mesh × Runtime integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mesh_handler_produces_execution_record():
    """Every local handler runs through the engine (intent ``mesh:<event>``)."""
    from voodoo.runtime.engine import engine as runtime_engine
    from voodoo.runtime.execution import ExecutionStatus

    received = []

    @mesh.on("runtime.fired")
    async def handler(payload):
        received.append(payload)

    await mesh.emit("runtime.fired", {"n": 1})

    assert received == [{"n": 1}]
    matches = [
        ex
        for ex in runtime_engine.executions.values()
        if ex.intent and ex.intent.name == "mesh:runtime.fired"
    ]
    assert len(matches) == 1
    assert matches[0].status is ExecutionStatus.COMPLETED
    assert matches[0].actor == "mesh"


@pytest.mark.asyncio
async def test_mesh_handler_is_child_of_broadcasting_execution():
    """A handler fired inside another execution links parent_execution_id."""
    from voodoo.primitives.intent import Intent
    from voodoo.runtime import ExecutionContext, ExecutionEngine
    from voodoo.runtime.execution import ExecutionStatus

    engine = ExecutionEngine()
    received = []

    @mesh.on("runtime.child")
    async def handler(payload):
        received.append(payload)

    async def compute(ctx: ExecutionContext):
        # broadcasting from inside an execution → handler becomes a child
        await mesh.emit("runtime.child", {"child": True})
        return None

    parent_ex = await engine.execute(Intent(name="runtime.parent"), compute)

    assert parent_ex.status is ExecutionStatus.COMPLETED
    assert received == [{"child": True}]

    child_matches = [
        ex
        for ex in engine.executions.values()
        if ex.intent and ex.intent.name == "mesh:runtime.child"
    ]
    assert len(child_matches) == 1
    child = child_matches[0]
    assert child.parent_execution_id == parent_ex.id
    assert child.trace_id == parent_ex.trace_id


@pytest.mark.asyncio
async def test_handler_error_does_not_break_others():
    received = []

    @mesh.on("test.resilient")
    async def failing_handler(payload):
        raise Exception("handler failed")

    @mesh.on("test.resilient")
    async def ok_handler(payload):
        received.append(payload)

    # Should not raise even though first handler fails
    await mesh.emit("test.resilient", {"x": 1})
    assert received == [{"x": 1}]


# ---------------------------------------------------------------------------
# Local vs remote boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_to_remote_node_uses_envelope():
    """Remote nodes receive the full envelope; local handlers get raw payload."""
    net = MeshNetwork()
    local_payloads = []

    @net.on("boundary.event")
    async def local_handler(payload):
        local_payloads.append(payload)

    # Mock WebSocket to capture what's sent remotely
    sent_messages = []

    class MockWS:
        async def send_text(self, data):
            sent_messages.append(data)

    mock_ws = MockWS()
    net.active_nodes.append(mock_ws)

    await net.broadcast("boundary.event", {"data": "hello"})

    # Local handler gets raw payload
    assert local_payloads == [{"data": "hello"}]

    # Remote node gets envelope
    assert len(sent_messages) == 1
    remote_msg = json.loads(sent_messages[0])
    assert remote_msg["method"] == "event"
    params = remote_msg["params"]
    assert "id" in params
    assert "ts" in params
    assert "source" in params
    assert "correlation_id" in params
    assert params["event"] == "boundary.event"
    assert params["payload"] == {"data": "hello"}
