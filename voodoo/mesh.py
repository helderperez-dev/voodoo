import asyncio
import inspect
import json
import uuid
from collections.abc import Callable
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from voodoo.mcp import mcp


class MeshNetwork:
    def __init__(self):
        self.exposed_functions: dict[str, Callable] = {}
        self.event_handlers: dict[str, list[Callable]] = {}
        self.active_nodes: list[WebSocket] = []

    def expose(self, name: str | None = None):
        """Decorator to expose a function to the Mesh Network and MCP."""

        def decorator(func: Callable):
            func_name = name or func.__name__
            self.exposed_functions[func_name] = func

            # Auto-bridge to MCP for AI IDEs
            mcp.tool(name=func_name, description=func.__doc__)(func)

            return func

        return decorator

    def on(self, event: str):
        """Decorator to register a handler for a Mesh event."""

        def decorator(func: Callable):
            if event not in self.event_handlers:
                self.event_handlers[event] = []
            self.event_handlers[event].append(func)
            return func

        return decorator

    async def broadcast(self, event: str, payload: Any):
        """Broadcast an event to all connected Mesh nodes."""
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "event",
                "params": {"event": event, "payload": payload},
            }
        )

        # Send to all connected nodes
        for node in self.active_nodes:
            try:
                await node.send_text(message)
            except Exception:
                pass

        # Also trigger locally
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    if inspect.iscoroutinefunction(handler):
                        await handler(payload)
                    else:
                        handler(payload)
                except Exception as e:
                    print(f"Local mesh event handler error: {e}")

    async def connect(self, endpoint_url: str):
        """Connect to another Mesh Node."""
        return MeshClient(endpoint_url)

    async def _handle_websocket(self, websocket: WebSocket):  # noqa: C901
        """The Starlette WebSocket endpoint for the Mesh Node."""
        await websocket.accept()
        self.active_nodes.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)

                method = msg.get("method")
                params = msg.get("params", {})
                msg_id = msg.get("id")

                if method == "call":
                    func_name = params.get("name")
                    args = params.get("arguments", {})

                    if func_name in self.exposed_functions:
                        func = self.exposed_functions[func_name]
                        try:
                            if inspect.iscoroutinefunction(func):
                                result = await func(**args)
                            else:
                                result = func(**args)

                            if msg_id:
                                await websocket.send_text(
                                    json.dumps(
                                        {
                                            "jsonrpc": "2.0",
                                            "id": msg_id,
                                            "result": result,
                                        }
                                    )
                                )
                        except Exception as e:
                            if msg_id:
                                await websocket.send_text(
                                    json.dumps(
                                        {
                                            "jsonrpc": "2.0",
                                            "id": msg_id,
                                            "error": str(e),
                                        }
                                    )
                                )
                    else:
                        if msg_id:
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "jsonrpc": "2.0",
                                        "id": msg_id,
                                        "error": "Function not found in Mesh",
                                    }
                                )
                            )

                elif method == "event":
                    event_name = params.get("event")
                    payload = params.get("payload")

                    if event_name in self.event_handlers:
                        for handler in self.event_handlers[event_name]:
                            try:
                                if inspect.iscoroutinefunction(handler):
                                    await handler(payload)
                                else:
                                    handler(payload)
                            except Exception as e:
                                print(f"Mesh event handler error: {e}")

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"Mesh WS Error: {e}")
        finally:
            if websocket in self.active_nodes:
                self.active_nodes.remove(websocket)


class MeshClient:
    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url
        self.ws = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._receive_task = None

    async def _ensure_connected(self):
        if self.ws is None or getattr(self.ws, "closed", True):
            import websockets

            # Use large max_size to handle huge payloads
            self.ws = await websockets.connect(self.endpoint_url, max_size=8388608)
            self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self):
        import websockets

        try:
            async for message in self.ws:
                data = json.loads(message)
                if "id" in data and data["id"] in self._pending_requests:
                    future = self._pending_requests.pop(data["id"])
                    if not future.done():
                        if "error" in data:
                            future.set_exception(Exception(data["error"]))
                        else:
                            future.set_result(data.get("result"))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"MeshClient receive loop error: {e}")

    async def call(self, name: str, **kwargs) -> Any:
        """Invoke a remote function on the connected Mesh Node."""
        await self._ensure_connected()
        msg_id = str(uuid.uuid4())

        future = asyncio.Future()
        self._pending_requests[msg_id] = future

        await self.ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {"name": name, "arguments": kwargs},
                    "id": msg_id,
                }
            )
        )

        return await future


mesh = MeshNetwork()
