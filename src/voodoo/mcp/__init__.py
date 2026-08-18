"""MCP Server — Model Context Protocol integration.

Consumes the :class:`ToolRegistry` so that the same ``@tool`` definition serves
Python calls, agent runs, and MCP consumers. The ``tool()`` decorator
registers tools in both the internal ``self.tools`` dict and the default
:class:`ToolRegistry`, with schemas generated from :class:`ToolSpec` when
available. Existing MCP functionality (SSE endpoint, sessions, resources)
is preserved.
"""

import asyncio
import inspect
import json
import uuid
from collections.abc import Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from voodoo.ai.tools.registry import (
    ToolRegistry,
    ToolSpec,
    build_spec,
    default_registry,
)
from voodoo.mcp.client import MCPClient
from voodoo.routing.api import api

__all__ = ["MCPClient", "MCPServer", "mcp"]


class MCPServer:
    def __init__(
        self,
        name: str = "voodoo-mcp",
        version: str = "1.0.0",
        registry: ToolRegistry | None = None,
        engine: Any | None = None,
    ):
        self.name = name
        self.version = version
        self.tools: dict[str, dict[str, Any]] = {}
        self.resources: dict[str, dict[str, Any]] = {}
        self.registry = registry or default_registry
        # The runtime engine MCP tool calls flow through. When ``None``
        # (e.g. tests constructing the server via ``__new__``) the default
        # runtime engine is used lazily.
        self.engine = engine

        # Sessions map: session_id -> asyncio.Queue
        self.sessions: dict[str, asyncio.Queue] = {}

        # Register SSE endpoints
        api.get("/mcp/sse")(self._sse_endpoint)
        api.post("/mcp/messages")(self._messages_endpoint)

    def tool(self, name: str | None = None, description: str | None = None):
        """Register a function as an MCP tool AND in the ToolRegistry.

        The function is introspected to build a :class:`ToolSpec` (with
        JSON-schema from type hints) and registered in the default
        :class:`ToolRegistry`. It is also stored in ``self.tools`` so
        existing MCP behavior is preserved.
        """

        def decorator(func: Callable):
            tool_name = name or func.__name__

            # Build and register ToolSpec in the registry.
            spec = build_spec(func, name=tool_name, description=description)
            self.registry.register(spec)

            self.tools[tool_name] = {
                "func": func,
                "description": description
                or func.__doc__
                or "No description provided.",
                "spec": spec,
            }
            return func

        return decorator

    def _list_tools(self) -> list[dict[str, Any]]:
        """Build the tools/list response from both self.tools and ToolRegistry."""
        tools_list: list[dict[str, Any]] = []
        seen: set[str] = set()

        # First, tools from self.tools (which have specs)
        for t_name, t_data in self.tools.items():
            spec: ToolSpec | None = t_data.get("spec")
            if spec:
                input_schema = spec.input_schema
                description = spec.description or t_data["description"]
            else:
                input_schema = {"type": "object", "properties": {}}
                description = t_data["description"]

            tools_list.append(
                {
                    "name": t_name,
                    "description": description,
                    "inputSchema": input_schema,
                }
            )
            seen.add(t_name)

        # Then, any tools in the registry not already in self.tools
        for spec in self.registry.all():
            if spec.name not in seen:
                tools_list.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "inputSchema": spec.input_schema,
                    }
                )
                seen.add(spec.name)

        return tools_list

    def resource(self, uri: str, name: str | None = None):
        def decorator(func: Callable):
            res_name = name or func.__name__
            self.resources[uri] = {"func": func, "name": res_name}
            return func

        return decorator

    async def _sse_endpoint(self, request: Request):
        session_id = str(uuid.uuid4())
        queue: asyncio.Queue[str] = asyncio.Queue()
        self.sessions[session_id] = queue

        async def event_generator():
            # The client must append the sessionId when POSTing messages
            yield f"event: endpoint\ndata: /mcp/messages?sessionId={session_id}\n\n"
            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                    except TimeoutError:
                        yield ":\n\n"
            finally:
                if session_id in self.sessions:
                    del self.sessions[session_id]

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    async def _handle_message(self, body: dict, queue: asyncio.Queue):  # noqa: C901
        method = body.get("method")
        params = body.get("params", {})
        msg_id = body.get("id")

        if method == "initialize":
            await queue.put(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}, "resources": {}},
                        "serverInfo": {"name": self.name, "version": self.version},
                    },
                }
            )

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            await queue.put(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": self._list_tools()},
                }
            )

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            # Try self.tools first, then the registry.
            func = None
            spec = None
            if tool_name in self.tools:
                func = self.tools[tool_name]["func"]
                spec = self.tools[tool_name].get("spec")
            else:
                spec = self.registry.get(tool_name)
                if spec:
                    func = spec.func

            if func is not None:
                try:
                    result = await self._run_tool_call(tool_name, func, spec, args)
                    await queue.put(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "result": {
                                "content": [{"type": "text", "text": str(result)}]
                            },
                        }
                    )
                except Exception as e:
                    await queue.put(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "error": {"code": -32603, "message": str(e)},
                        }
                    )
            else:
                await queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": "Tool not found"},
                    }
                )

        elif method == "resources/list":
            res_list = [
                {"uri": uri, "name": r_data["name"]}
                for uri, r_data in self.resources.items()
            ]
            await queue.put(
                {"jsonrpc": "2.0", "id": msg_id, "result": {"resources": res_list}}
            )

        elif method == "resources/read":
            uri = params.get("uri")
            if uri in self.resources:
                func = self.resources[uri]["func"]
                try:
                    if inspect.iscoroutinefunction(func):
                        content = await func()
                    else:
                        content = func()
                    await queue.put(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "result": {
                                "contents": [{"uri": uri, "text": str(content)}]
                            },
                        }
                    )
                except Exception as e:
                    await queue.put(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "error": {"code": -32603, "message": str(e)},
                        }
                    )
            else:
                await queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32602, "message": "Resource not found"},
                    }
                )

        else:
            if msg_id is not None:
                await queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": "Method not found"},
                    }
                )

    async def _messages_endpoint(self, request: Request):
        try:
            session_id = request.query_params.get("sessionId")
            if not session_id or session_id not in self.sessions:
                # Fallback to the first available session if client didn't append sessionId (for some broken clients)
                if self.sessions:
                    session_id = list(self.sessions.keys())[0]
                else:
                    return JSONResponse(
                        {"error": "No active SSE session found"}, status_code=400
                    )

            queue = self.sessions[session_id]
            body = await request.json()
            asyncio.create_task(self._handle_message(body, queue))
            return Response(status_code=202)
        except Exception as e:
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}},
                status_code=500,
            )

    async def _run_tool_call(
        self,
        tool_name: str,
        func: Callable,
        spec: ToolSpec | None,
        args: dict[str, Any],
    ) -> Any:
        """Execute an MCP tool call through the runtime execution engine.

        The call becomes an :class:`~voodoo.runtime.execution.Execution`
        (intent ``mcp:<tool>``) with the tool's declared permissions enforced
        as required capabilities. Unauthorized calls raise ``CapabilityDenied``
        before the tool executes — same authority model as agents.
        """
        from voodoo.primitives.intent import Intent
        from voodoo.runtime.engine import engine as default_engine

        eng = getattr(self, "engine", None) or default_engine
        permissions = list(spec.permissions) if spec else []

        async def compute(ctx: Any) -> Any:
            if inspect.iscoroutinefunction(func):
                return await func(**args)
            return func(**args)

        intent = Intent(name=f"mcp:{tool_name}", params=dict(args))
        for perm in permissions:
            intent.require(perm)

        execution = await eng.execute(intent, compute, actor="mcp")
        return execution.result


mcp = MCPServer()
