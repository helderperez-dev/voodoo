"""Tests for MCP × Runtime integration (Phase 6).

MCP ``tools/call`` dispatches are routed through the runtime execution
engine, creating an ``Execution`` (intent ``mcp:<tool>``) with the tool's
permissions enforced as required capabilities.
"""

from __future__ import annotations

import pytest

from voodoo.mcp import MCPServer
from voodoo.primitives.capability import Capability
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.errors import CapabilityDenied
from voodoo.runtime.execution import ExecutionStatus
from voodoo.tools.registry import ToolRegistry


@pytest.fixture
def fresh_registry():
    return ToolRegistry()


@pytest.fixture
def fresh_mcp(fresh_registry):
    """MCPServer with an isolated registry + explicit engine."""
    server = MCPServer.__new__(MCPServer)
    server.name = "test-mcp"
    server.version = "1.0.0"
    server.tools = {}
    server.resources = {}
    server.registry = fresh_registry
    server.sessions = {}
    server.engine = ExecutionEngine()
    return server


class TestMCPRuntime:
    async def test_tool_allowed_with_registered_capability(self, fresh_mcp):
        @fresh_mcp.tool(name="send_email")
        def send_email(to: str) -> str:
            return f"sent to {to}"

        spec = fresh_mcp.registry.get("send_email")
        # simulate a ToolSpec with a permission requirement
        spec.permissions = ["email.send"]
        fresh_mcp.engine.capabilities.register(Capability(name="email.send"))

        result = await fresh_mcp._run_tool_call("send_email", send_email, spec, {"to": "a@b.c"})
        assert result == "sent to a@b.c"

        matches = [
            ex
            for ex in fresh_mcp.engine.executions.values()
            if ex.intent and ex.intent.name == "mcp:send_email"
        ]
        assert len(matches) == 1
        assert matches[0].status is ExecutionStatus.COMPLETED
        assert matches[0].actor == "mcp"
        assert matches[0].intent.params == {"to": "a@b.c"}

    async def test_tool_denied_without_capability(self, fresh_mcp):
        from voodoo.tools.registry import ToolSpec

        called = []

        def secret(data: str) -> str:
            called.append(data)
            return "secret result"

        spec = ToolSpec(
            name="secret_tool",
            description="hidden",
            input_schema={},
            output_schema={},
            permissions=["secrets.read"],
            func=secret,
        )

        with pytest.raises(CapabilityDenied):
            await fresh_mcp._run_tool_call("secret_tool", secret, spec, {"data": "x"})
        # side effect must not happen
        assert called == []

        matches = [
            ex
            for ex in fresh_mcp.engine.executions.values()
            if ex.intent and ex.intent.name == "mcp:secret_tool"
        ]
        assert len(matches) == 1
        assert matches[0].status is ExecutionStatus.FAILED

    async def test_tool_without_permissions_runs(self, fresh_mcp):
        @fresh_mcp.tool(name="plain_tool")
        def plain(x: int) -> int:
            return x * 2

        result = await fresh_mcp._run_tool_call("plain_tool", plain, None, {"x": 21})
        assert result == 42
