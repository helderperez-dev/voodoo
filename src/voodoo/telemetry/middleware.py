import time
import traceback
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from voodoo.telemetry.store import logger, telemetry_store, trace_id_var


class TelemetryMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        trace_id = str(uuid.uuid4())
        token = trace_id_var.set(trace_id)

        start_time = time.perf_counter()
        error = False

        try:
            await self.app(scope, receive, send)
        except Exception as e:
            error = True
            logger.error(
                f"Unhandled exception in {scope['type']}: {e}\n{traceback.format_exc()}"
            )
            raise
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000
            telemetry_store.record_request(latency_ms, error)

            if scope["type"] == "http":
                method = scope.get("method", "")
                path = scope.get("path", "")
                logger.info(f"{method} {path} completed in {latency_ms:.2f}ms")
            elif scope["type"] == "websocket":
                logger.info(f"WebSocket session completed in {latency_ms:.2f}ms")

            trace_id_var.reset(token)
