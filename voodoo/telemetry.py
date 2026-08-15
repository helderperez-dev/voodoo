import contextvars
import functools
import inspect
import logging
import time
import traceback
import uuid
from collections.abc import Callable
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from voodoo.api import api

# Context variable for tracing
trace_id_var = contextvars.ContextVar("trace_id", default=None)


class TelemetryStore:
    def __init__(self):
        self.metrics: dict[str, Any] = {
            "requests_total": 0,
            "errors_total": 0,
            "latencies_ms": [],
            "custom_traces": [],
            "db_queries": 0,
            "agent_tokens": 0,
        }

    def record_request(self, latency_ms: float, error: bool = False):
        self.metrics["requests_total"] += 1
        if error:
            self.metrics["errors_total"] += 1
        self.metrics["latencies_ms"].append(latency_ms)
        if len(self.metrics["latencies_ms"]) > 1000:
            self.metrics["latencies_ms"].pop(0)

    def record_trace(self, name: str, latency_ms: float, error: bool = False):
        self.metrics["custom_traces"].append(
            {
                "name": name,
                "latency_ms": latency_ms,
                "error": error,
                "timestamp": time.time(),
                "trace_id": trace_id_var.get(),
            }
        )
        if len(self.metrics["custom_traces"]) > 1000:
            self.metrics["custom_traces"].pop(0)

    def record_db_query(self):
        self.metrics["db_queries"] += 1

    def record_agent_tokens(self, count: int):
        self.metrics["agent_tokens"] += count

    def get_summary(self) -> dict[str, Any]:
        latencies = self.metrics["latencies_ms"]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        return {
            "requests_total": self.metrics["requests_total"],
            "errors_total": self.metrics["errors_total"],
            "average_latency_ms": round(avg_latency, 2),
            "db_queries": self.metrics["db_queries"],
            "agent_tokens": self.metrics["agent_tokens"],
            "recent_traces": self.metrics["custom_traces"][-10:],
        }


telemetry_store = TelemetryStore()

logger = logging.getLogger("voodoo.telemetry")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - [%(trace_id)s] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get() or "no-trace"
        return True


logger.addFilter(TraceFilter())


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


def trace(name: str = None):
    """Decorator to trace a specific function block."""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            t_name = name or func.__name__
            start = time.perf_counter()
            error = False
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error = True
                logger.error(
                    f"Error in traced block '{t_name}': {e}\n{traceback.format_exc()}"
                )
                raise
            finally:
                latency = (time.perf_counter() - start) * 1000
                telemetry_store.record_trace(t_name, latency, error)
                logger.info(f"Trace '{t_name}' completed in {latency:.2f}ms")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            t_name = name or func.__name__
            start = time.perf_counter()
            error = False
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error = True
                logger.error(
                    f"Error in traced block '{t_name}': {e}\n{traceback.format_exc()}"
                )
                raise
            finally:
                latency = (time.perf_counter() - start) * 1000
                telemetry_store.record_trace(t_name, latency, error)
                logger.info(f"Trace '{t_name}' completed in {latency:.2f}ms")

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@api.get("/voodoo/metrics")
async def get_metrics():
    return telemetry_store.get_summary()
