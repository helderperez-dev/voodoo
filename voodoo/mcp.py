import inspect
import asyncio
import json
import uuid
from typing import Any, Callable, Dict, Optional
from voodoo.api import api
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse, Response

class MCPServer:
    def __init__(self, name: str = "voodoo-mcp", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        
        # Sessions map: session_id -> asyncio.Queue
        self.sessions: Dict[str, asyncio.Queue] = {}
        
        # Register SSE endpoints
        api.get("/mcp/sse")(self._sse_endpoint)
        api.post("/mcp/messages")(self._messages_endpoint)

    def tool(self, name: Optional[str] = None, description: Optional[str] = None):
        def decorator(func: Callable):
            tool_name = name or func.__name__
            self.tools[tool_name] = {
                "func": func,
                "description": description or func.__doc__ or "No description provided."
            }
            return func
        return decorator

    def resource(self, uri: str, name: Optional[str] = None):
        def decorator(func: Callable):
            res_name = name or func.__name__
            self.resources[uri] = {
                "func": func,
                "name": res_name
            }
            return func
        return decorator

    async def _sse_endpoint(self, request: Request):
        session_id = str(uuid.uuid4())
        queue = asyncio.Queue()
        self.sessions[session_id] = queue
        
        async def event_generator():
            # The client must append the sessionId when POSTing messages
            yield f'event: endpoint\ndata: /mcp/messages?sessionId={session_id}\n\n'
            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                    except asyncio.TimeoutError:
                        yield ':\n\n'
            finally:
                if session_id in self.sessions:
                    del self.sessions[session_id]
                    
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    async def _handle_message(self, body: dict, queue: asyncio.Queue):
        method = body.get("method")
        params = body.get("params", {})
        msg_id = body.get("id")

        if method == "initialize":
            await queue.put({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": self.name, "version": self.version}
                }
            })
            
        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            tools_list = [
                {"name": t_name, "description": t_data["description"], "inputSchema": {"type": "object", "properties": {}}}
                for t_name, t_data in self.tools.items()
            ]
            await queue.put({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tools_list}
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            if tool_name in self.tools:
                func = self.tools[tool_name]["func"]
                try:
                    if inspect.iscoroutinefunction(func):
                        result = await func(**args)
                    else:
                        result = func(**args)
                    await queue.put({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"content": [{"type": "text", "text": str(result)}]}
                    })
                except Exception as e:
                    await queue.put({
                        "jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(e)}
                    })
            else:
                await queue.put({
                    "jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Tool not found"}
                })
                
        elif method == "resources/list":
            res_list = [{"uri": uri, "name": r_data["name"]} for uri, r_data in self.resources.items()]
            await queue.put({"jsonrpc": "2.0", "id": msg_id, "result": {"resources": res_list}})

        elif method == "resources/read":
            uri = params.get("uri")
            if uri in self.resources:
                func = self.resources[uri]["func"]
                try:
                    if inspect.iscoroutinefunction(func):
                        content = await func()
                    else:
                        content = func()
                    await queue.put({
                        "jsonrpc": "2.0", "id": msg_id, "result": {"contents": [{"uri": uri, "text": str(content)}]}
                    })
                except Exception as e:
                    await queue.put({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(e)}})
            else:
                await queue.put({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "Resource not found"}})
                
        else:
            if msg_id is not None:
                await queue.put({
                    "jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}
                })

    async def _messages_endpoint(self, request: Request):
        try:
            session_id = request.query_params.get("sessionId")
            if not session_id or session_id not in self.sessions:
                # Fallback to the first available session if client didn't append sessionId (for some broken clients)
                if self.sessions:
                    session_id = list(self.sessions.keys())[0]
                else:
                    return JSONResponse({"error": "No active SSE session found"}, status_code=400)
            
            queue = self.sessions[session_id]
            body = await request.json()
            asyncio.create_task(self._handle_message(body, queue))
            return Response(status_code=202)
        except Exception as e:
            return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}, status_code=500)

mcp = MCPServer()

class MCPClient:
    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        import httpx
        async with httpx.AsyncClient() as client:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments
                },
                "id": 1
            }
            response = await client.post(self.endpoint_url, json=payload)
            return response.json()