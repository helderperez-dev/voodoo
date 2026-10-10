import re
import time
import traceback
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from voodoo.observability.store import (
    correlation_id_var,
    logger,
    telemetry_store,
    trace_id_var,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            try:
                decoded = value.decode("latin-1")
            except UnicodeDecodeError:
                return None
            return decoded if _SAFE_ID.fullmatch(decoded) else None
    return None


class TelemetryMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        trace_id = _header(scope, b"x-trace-id") or str(uuid.uuid4())
        correlation_id = _header(scope, b"x-correlation-id") or trace_id
        trace_token = trace_id_var.set(trace_id)
        correlation_token = correlation_id_var.set(correlation_id)

        start_time = time.perf_counter()
        error = False
        status_code: int | None = None

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 0))
                headers = list(message.get("headers", []))
                header_names = {key.lower() for key, _ in headers}
                if b"x-trace-id" not in header_names:
                    headers.append((b"x-trace-id", trace_id.encode("ascii")))
                if b"x-correlation-id" not in header_names:
                    headers.append(
                        (b"x-correlation-id", correlation_id.encode("ascii"))
                    )
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception as e:
            error = True
            from voodoo.security.redaction import redact_string

            logger.error(
                "Unhandled exception in %s [%s]: %s\n%s",
                scope["type"],
                trace_id,
                redact_string(str(e)),
                redact_string(traceback.format_exc()),
            )
            raise
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000
            telemetry_store.record_request(
                latency_ms,
                error,
                trace_id=trace_id,
                correlation_id=correlation_id,
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
            )

            if scope["type"] == "http":
                method = scope.get("method", "")
                path = scope.get("path", "")
                logger.info(
                    "%s %s completed in %.2fms [%s]",
                    method,
                    path,
                    latency_ms,
                    trace_id,
                )
            elif scope["type"] == "websocket":
                logger.info("WebSocket session completed in %.2fms [%s]", latency_ms, trace_id)

            trace_id_var.reset(trace_token)
            correlation_id_var.reset(correlation_token)
