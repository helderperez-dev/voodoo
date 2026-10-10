import asyncio
import json
import logging
import uuid
from typing import Any

from voodoo.security.redaction import redact_string

_logger = logging.getLogger("voodoo.mesh.client")


class MeshClient:
    def __init__(self, endpoint_url: str, *, credential: str | None = None) -> None:
        self.endpoint_url = endpoint_url
        self.credential = credential
        self.ws: Any = None
        self._pending_requests: dict[str, asyncio.Future[Any]] = {}
        self._structured_requests: set[str] = set()
        self._receive_task: asyncio.Task[Any] | None = None

    def _fail_pending(self, error: BaseException) -> None:
        """Resolve every in-flight request when the transport dies.

        A receive-loop failure is a transport failure, not a successful
        response.  Leaving futures pending here leaks callers indefinitely and
        can strand Runtime operations waiting on a remote result.
        """
        pending = tuple(self._pending_requests.items())
        self._pending_requests.clear()
        self._structured_requests.clear()
        for _message_id, future in pending:
            if not future.done():
                future.set_exception(error)

    async def _ensure_connected(self) -> None:
        if self.ws is None or getattr(self.ws, "closed", True):
            import websockets

            self.ws = await websockets.connect(self.endpoint_url, max_size=8388608)
            self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        import websockets
        from websockets.exceptions import ConnectionClosed

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
                            RuntimeError(
                                "remote response did not include structured outcome"
                            )
                        )
                        continue
                    from voodoo.runtime.distributed.remote import RemoteExecutionOutcome

                    future.set_result(
                        RemoteExecutionOutcome.model_validate(outcome_payload)
                    )
                elif "error" in data:
                    future.set_exception(Exception(data["error"]))
                else:
                    future.set_result(data.get("result"))
        except ConnectionClosed as error:
            self._fail_pending(
                ConnectionError(
                    f"mesh connection closed while awaiting response: {error}"
                )
            )
        except Exception as e:
            self._fail_pending(
                ConnectionError("mesh receive loop failed")
            )
            _logger.warning(
                "mesh client receive loop failed endpoint=%s error=%s",
                self.endpoint_url,
                redact_string(str(e)),
            )

    def _credential_params(self) -> dict[str, str]:
        if self.credential is None:
            return {}
        return {"credential": self.credential}

    async def call(self, name: str, **kwargs: Any) -> Any:
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
                    "params": {
                        "name": name,
                        "arguments": kwargs,
                        **self._credential_params(),
                    },
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
    ) -> Any:
        """Execute remotely and return the canonical structured Voodoo outcome.

        ``actor`` remains for compatibility with unauthenticated Mesh nodes.
        When the receiving node configures a participant resolver, credential
        evidence is resolved first and the authenticated identity replaces this
        asserted actor label before authority evaluation.
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
            **self._credential_params(),
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
