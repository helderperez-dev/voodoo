import asyncio
import json
import uuid
from typing import Any


class MeshClient:
    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url
        self.ws = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._structured_requests: set[str] = set()
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
                msg_id = data.get("id")
                if msg_id not in self._pending_requests:
                    continue

                future = self._pending_requests.pop(msg_id)
                structured = msg_id in self._structured_requests
                self._structured_requests.discard(msg_id)
                if future.done():
                    continue

                if structured:
                    outcome_payload = data.get("outcome")
                    if outcome_payload is None:
                        future.set_exception(
                            RuntimeError("remote response did not include structured outcome")
                        )
                        continue
                    from voodoo.mesh.remote import RemoteExecutionOutcome

                    future.set_result(RemoteExecutionOutcome.model_validate(outcome_payload))
                elif "error" in data:
                    future.set_exception(Exception(data["error"]))
                else:
                    future.set_result(data.get("result"))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"MeshClient receive loop error: {e}")

    async def call(self, name: str, **kwargs) -> Any:
        """Invoke a remote function using the legacy raw-result contract."""
        await self._ensure_connected()
        msg_id = str(uuid.uuid4())

        future = asyncio.get_running_loop().create_future()
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

    async def execute(
        self,
        operation: str,
        *,
        arguments: dict[str, Any] | None = None,
        actor: str = "anonymous",
        request_id: str | None = None,
        correlation_id: str | None = None,
        parent_execution_id: str | None = None,
        target_entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Execute remotely and return the canonical structured Voodoo outcome.

        Unlike :meth:`call`, this method does not collapse WAITING or FAILED
        executions into generic RPC success/error semantics. The caller gets a
        ``RemoteExecutionOutcome`` whose ``status`` mirrors canonical Execution
        truth and can decide what to do next.
        """
        await self._ensure_connected()
        msg_id = str(uuid.uuid4())
        stable_request_id = request_id or msg_id

        future = asyncio.get_running_loop().create_future()
        self._pending_requests[msg_id] = future
        self._structured_requests.add(msg_id)

        params: dict[str, Any] = {
            "operation": operation,
            "arguments": arguments or {},
            "actor": actor,
            "request_id": stable_request_id,
        }
        if correlation_id is not None:
            params["correlation_id"] = correlation_id
        if parent_execution_id is not None:
            params["parent_execution_id"] = parent_execution_id
        if target_entity_id is not None:
            params["target_entity_id"] = target_entity_id
        if metadata:
            params["metadata"] = dict(metadata)

        await self.ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": params,
                    "id": msg_id,
                }
            )
        )
        return await future
