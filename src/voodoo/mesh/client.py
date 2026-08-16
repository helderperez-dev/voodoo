import asyncio
import json
import uuid
from typing import Any


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
