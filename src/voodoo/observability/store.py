import contextvars
import functools
import inspect
import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from voodoo.security.redaction import redact_string

# Context variable for tracing
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

# Context variable for current span (enables parent-span tracking)
_span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "voodoo_span_id", default=None
)


def _report_observability_failure(operation: str, error: Exception) -> None:
    """Make best-effort observability failures visible without leaking secrets."""
    logging.getLogger("voodoo.observability").warning(
        "observability operation failed operation=%s error=%s",
        operation,
        redact_string(str(error)),
    )


def _percentile(values: list[float], percentile: float) -> float:
    """Return a deterministic nearest-rank percentile for bounded samples."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int((percentile / 100) * len(ordered) + 0.999999)))
    return float(ordered[rank - 1])


@contextmanager
def store_span(name: str, *, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
    """Create a best-effort span for a Store boundary operation.

    Store durability must not depend on telemetry being configured correctly.
    Span construction failures therefore degrade to an uninstrumented operation;
    exceptions raised by the Store operation itself are never intercepted here.
    """
    try:
        manager = telemetry_store.start_span(name, attributes=attributes)
    except Exception as error:
        _report_observability_failure("store_span", error)
        yield None
        return
    with manager as span:
        yield span


@contextmanager
def store_operation(
    operation: str,
    *,
    provider: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[dict[str, int]]:
    """Instrument one Store/object operation with bounded telemetry.

    The yielded mapping lets adapters report a byte count after a successful
    read/write. Keys, payloads, and exception text are never recorded.
    """
    details: dict[str, int] = {}
    started = time.perf_counter()
    failed = False
    span_attributes = {"provider": provider, "operation": operation}
    if attributes:
        span_attributes.update(attributes)
    try:
        with store_span(f"store.{operation}", attributes=span_attributes):
            yield details
    except Exception:
        failed = True
        raise
    finally:
        telemetry_store.record_store_operation(
            operation,
            (time.perf_counter() - started) * 1000,
            error=failed,
            bytes_count=max(0, int(details.get("bytes", 0))),
        )


def new_trace_id() -> str:
    """Generate a new trace/trace id."""
    return str(uuid4())


@dataclass(frozen=True)
class Span:
    """OpenTelemetry-compatible span.

    Carries trace/span identity, timing, status, and arbitrary attributes.
    Frozen so spans are safe to store and pass across boundaries.
    """

    trace_id: str
    span_id: str = field(default_factory=lambda: uuid4().hex[:16])
    parent_span_id: str | None = None
    name: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    status: str = "ok"  # "ok" | "error" | "unset"
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["start_time"] = self.start_time.isoformat()
        d["end_time"] = self.end_time.isoformat() if self.end_time else None
        d["duration_ms"] = self.duration_ms
        return d


class TelemetryStore:
    _SUMMARY_PATH = Path(".voodoo/telemetry_summary.json")

    def __init__(self) -> None:
        self.metrics: dict[str, Any] = {
            "requests_total": 0,
            "errors_total": 0,
            "latencies_ms": [],
            "requests": [],
            "custom_traces": [],
            "db_queries": 0,
            "agent_tokens": 0,
            "agent_runs": [],
            "tool_calls": [],
            "store_operations": [],
            "spans": [],
        }
        #: Context variable for tracing (aliased for module-level access).
        self.trace_id_var = trace_id_var
        # Restore persisted rolling summary if available.
        self._load_summary()

    def record_request(
        self,
        latency_ms: float,
        error: bool = False,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.metrics["requests_total"] += 1
        if error:
            self.metrics["errors_total"] += 1
        self.metrics["latencies_ms"].append(latency_ms)
        if len(self.metrics["latencies_ms"]) > 1000:
            self.metrics["latencies_ms"].pop(0)
        requests = self.metrics.setdefault("requests", [])
        requests.append(
            {
                "latency_ms": latency_ms,
                "error": error,
                "trace_id": trace_id if trace_id is not None else trace_id_var.get(),
                "correlation_id": (
                    correlation_id
                    if correlation_id is not None
                    else correlation_id_var.get()
                ),
                "method": method,
                "path": path,
                "status_code": status_code,
                "timestamp": time.time(),
            }
        )
        if len(requests) > 1000:
            requests.pop(0)
        # Persist rolling summary every 50 requests.
        if self.metrics["requests_total"] % 50 == 0:
            self._persist_summary()

    def record_trace(
        self, name: str, latency_ms: float, error: bool = False
    ) -> None:
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

    def record_db_query(self) -> None:
        self.metrics["db_queries"] += 1

    def record_agent_tokens(self, count: int) -> None:
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

    def record_store_operation(
        self,
        operation: str,
        latency_ms: float,
        *,
        error: bool = False,
        bytes_count: int = 0,
        queue_lag_ms: float | None = None,
    ) -> None:
        """Record a bounded, structured Store operation metric.

        ``operation`` is semantic (for example ``commit``, ``recovery``,
        ``object.read``, ``compaction``, or ``lock.wait``), so adapters can
        report one contract without sharing implementation. Payloads and keys
        are never recorded here.
        """
        self.metrics.setdefault("store_operations", []).append(
            {
                "operation": operation,
                "latency_ms": latency_ms,
                "error": error,
                "bytes": max(0, bytes_count),
                "queue_lag_ms": queue_lag_ms,
                "trace_id": trace_id_var.get(),
                "timestamp": time.time(),
            }
        )
        if len(self.metrics["store_operations"]) > 1000:
            self.metrics["store_operations"].pop(0)

    # -- span model (OTel-compatible) ----------------------------------

    def record_span(self, span: Span) -> None:
        """Store a completed span in the ring buffer and forward to OTLP if active."""
        self.metrics["spans"].append(span.to_dict())
        if len(self.metrics["spans"]) > 1000:
            self.metrics["spans"].pop(0)
        # Forward to OTLP exporter if available (lazy import to avoid circular deps).
        try:
            from voodoo.integrations.otel import export_span

            export_span(span)
        except Exception as error:
            _report_observability_failure("export_span", error)

    @contextmanager
    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """Context manager that creates a child span for the current trace.

        Sets ``_span_id_var`` so nested ``start_span`` calls pick up the
        correct ``parent_span_id``.
        """
        parent_id = _span_id_var.get()
        resolved_trace = trace_id_var.get() or new_trace_id()
        span = Span(
            trace_id=resolved_trace,
            parent_span_id=parent_id,
            name=name,
            attributes=attributes or {},
        )
        token = _span_id_var.set(span.span_id)
        try:
            yield span
        except Exception:
            completed = Span(
                trace_id=span.trace_id,
                span_id=span.span_id,
                parent_span_id=span.parent_span_id,
                name=span.name,
                start_time=span.start_time,
                end_time=datetime.now(UTC),
                status="error",
                attributes=span.attributes,
            )
            self.record_span(completed)
            raise
        else:
            completed = Span(
                trace_id=span.trace_id,
                span_id=span.span_id,
                parent_span_id=span.parent_span_id,
                name=span.name,
                start_time=span.start_time,
                end_time=datetime.now(UTC),
                status="ok",
                attributes=span.attributes,
            )
            self.record_span(completed)
        finally:
            _span_id_var.reset(token)

    # -- persistence ---------------------------------------------------

    def _persist_summary(self) -> None:
        """Persist a rolling summary to disk so ``voodoo status`` survives restarts."""
        try:
            self._SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
            summary = self.get_summary()
            # Convert non-serialisable fields
            for key in ("recent_traces", "recent_agent_runs"):
                summary.pop(key, None)
            self._SUMMARY_PATH.write_text(json.dumps(summary, default=str))
        except (OSError, TypeError, ValueError) as error:
            _report_observability_failure("persist_summary", error)

    def _load_summary(self) -> None:
        """Restore persisted counters so ``voodoo status`` works after restart."""
        try:
            if self._SUMMARY_PATH.exists():
                data = json.loads(self._SUMMARY_PATH.read_text())
                self.metrics["requests_total"] = data.get("requests_total", 0)
                self.metrics["errors_total"] = data.get("errors_total", 0)
                self.metrics["db_queries"] = data.get("db_queries", 0)
                self.metrics["agent_tokens"] = data.get("agent_tokens", 0)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            _report_observability_failure("load_summary", error)

    def get_summary(self) -> dict[str, Any]:
        latencies = self.metrics["latencies_ms"]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        agent_runs = self.metrics["agent_runs"]
        total_tokens_in = sum(r.get("tokens_in", 0) for r in agent_runs)
        total_tokens_out = sum(r.get("tokens_out", 0) for r in agent_runs)
        total_cost = sum(r.get("cost", 0.0) for r in agent_runs)

        tool_calls = self.metrics["tool_calls"]
        tool_errors = sum(1 for tc in tool_calls if tc.get("error"))
        store_operations = self.metrics.get("store_operations", [])
        store_errors = sum(1 for op in store_operations if op.get("error"))
        store_latencies = [
            float(op["latency_ms"])
            for op in store_operations
            if isinstance(op.get("latency_ms"), (int, float))
            and not isinstance(op.get("latency_ms"), bool)
        ]

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
            "store_operations_total": len(store_operations),
            "store_operation_errors": store_errors,
            "store_operation_latency_p50_ms": round(
                _percentile(store_latencies, 50), 3
            ),
            "store_operation_latency_p95_ms": round(
                _percentile(store_latencies, 95), 3
            ),
            "store_bytes_total": sum(op.get("bytes", 0) for op in store_operations),
            "store_queue_lag_ms": round(
                sum(op.get("queue_lag_ms") or 0.0 for op in store_operations), 2
            ),
            "spans_total": len(self.metrics["spans"]),
            "recent_traces": self.metrics["custom_traces"][-10:],
            "recent_agent_runs": agent_runs[-10:],
            "recent_store_operations": store_operations[-10:],
        }


telemetry_store = TelemetryStore()

logger = logging.getLogger("voodoo.observability")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - [%(trace_id)s] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get() or "no-trace"
        return True


logger.addFilter(TraceFilter())


def trace(
    name: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to trace a specific function block.

    Records both a lightweight trace record and a full OTel-compatible span.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            t_name = name or func.__name__
            start = time.perf_counter()
            error = False
            with telemetry_store.start_span(t_name):
                try:
                    return await func(*args, **kwargs)
                except Exception as caught_error:
                    error = True
                    logger.error(
                        "Traced block failed: name=%s error_type=%s",
                        t_name,
                        type(caught_error).__name__,
                    )
                    raise
                finally:
                    latency = (time.perf_counter() - start) * 1000
                    telemetry_store.record_trace(t_name, latency, error)
                    logger.info(f"Trace '{t_name}' completed in {latency:.2f}ms")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            t_name = name or func.__name__
            start = time.perf_counter()
            error = False
            with telemetry_store.start_span(t_name):
                try:
                    return func(*args, **kwargs)
                except Exception as caught_error:
                    error = True
                    logger.error(
                        "Traced block failed: name=%s error_type=%s",
                        t_name,
                        type(caught_error).__name__,
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
