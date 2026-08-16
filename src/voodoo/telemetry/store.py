import contextvars
import functools
import inspect
import logging
import time
import traceback
from collections.abc import Callable
from typing import Any

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
            "agent_runs": [],
            "tool_calls": [],
        }
        #: Context variable for tracing (aliased for module-level access).
        self.trace_id_var = trace_id_var

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

    def record_agent_run(self, run_record: Any) -> None:
        """Store an agent run record (AgentRun dataclass or compatible dict).

        Correlated with the current ``trace_id_var`` when available.
        """
        entry: dict[str, Any]
        if hasattr(run_record, "__dict__"):
            # AgentRun dataclass — extract key fields.
            entry = {
                "run_id": run_record.run_id,
                "model": run_record.model,
                "provider": run_record.provider,
                "prompt": run_record.prompt,
                "output": run_record.output,
                "timings": run_record.timings,
                "tokens_in": run_record.tokens_in,
                "tokens_out": run_record.tokens_out,
                "cost": run_record.cost,
                "tool_calls": run_record.tool_calls,
                "status": run_record.status,
                "error": run_record.error,
                "started_at": run_record.started_at,
                "completed_at": run_record.completed_at,
                "trace_id": run_record.trace_id or trace_id_var.get(),
            }
        else:
            entry = dict(run_record)
            entry.setdefault("trace_id", trace_id_var.get())

        self.metrics["agent_runs"].append(entry)
        if len(self.metrics["agent_runs"]) > 500:
            self.metrics["agent_runs"].pop(0)

    def record_tool_call(
        self, tool_name: str, latency_ms: float, error: bool = False
    ) -> None:
        """Record a single tool invocation with latency and error status."""
        self.metrics["tool_calls"].append(
            {
                "tool": tool_name,
                "latency_ms": latency_ms,
                "error": error,
                "trace_id": trace_id_var.get(),
                "timestamp": time.time(),
            }
        )
        if len(self.metrics["tool_calls"]) > 1000:
            self.metrics["tool_calls"].pop(0)

    def get_summary(self) -> dict[str, Any]:
        latencies = self.metrics["latencies_ms"]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        agent_runs = self.metrics["agent_runs"]
        total_tokens_in = sum(r.get("tokens_in", 0) for r in agent_runs)
        total_tokens_out = sum(r.get("tokens_out", 0) for r in agent_runs)
        total_cost = sum(r.get("cost", 0.0) for r in agent_runs)

        tool_calls = self.metrics["tool_calls"]
        tool_errors = sum(1 for tc in tool_calls if tc.get("error"))

        return {
            "requests_total": self.metrics["requests_total"],
            "errors_total": self.metrics["errors_total"],
            "average_latency_ms": round(avg_latency, 2),
            "db_queries": self.metrics["db_queries"],
            "agent_tokens": self.metrics["agent_tokens"],
            "agent_runs": len(agent_runs),
            "agent_tokens_in": total_tokens_in,
            "agent_tokens_out": total_tokens_out,
            "agent_cost": round(total_cost, 6),
            "tool_calls_total": len(tool_calls),
            "tool_errors": tool_errors,
            "recent_traces": self.metrics["custom_traces"][-10:],
            "recent_agent_runs": agent_runs[-10:],
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
