import inspect
import asyncio
from typing import Any, Callable, Dict, Optional
from voodoo.api import api
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

class MCPServer:
    def __init__(self, name: str = "voodoo-mcp", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        
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
        async def event_generator():
            yield 'event: endpoint\ndata: /mcp/messages\n\n'
            while True:
                await asyncio.sleep(15)
                yield ':\n\n'
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    async def _messages_endpoint(self, request: Request):
        try:
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})
            msg_id = body.get("id")

            if method == "tools/list":
                tools_list = [
                    {
                        "name": t_name,
                        "description": t_data["description"],
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                    for t_name, t_data in self.tools.items()
                ]
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": tools_list}
                })

            elif method == "tools/call":
                tool_name = params.get("name")
                args = params.get("arguments", {})
                if tool_name in self.tools:
                    func = self.tools[tool_name]["func"]
                    if inspect.iscoroutinefunction(func):
                        result = await func(**args)
                    else:
                        result = func(**args)
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"content": [{"type": "text", "text": str(result)}]}
                    })
                else:
                    return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Tool not found"}})

            elif method == "resources/list":
                res_list = [
                    {
                        "uri": uri,
                        "name": r_data["name"]
                    }
                    for uri, r_data in self.resources.items()
                ]
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"resources": res_list}
                })

            elif method == "resources/read":
                uri = params.get("uri")
                if uri in self.resources:
                    func = self.resources[uri]["func"]
                    if inspect.iscoroutinefunction(func):
                        content = await func()
                    else:
                        content = func()
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"contents": [{"uri": uri, "text": str(content)}]}
                    })
                return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "Resource not found"}})
            
            return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}})
        except Exception as e:
            return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}, status_code=500)

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

mcp = MCPServer()
