"""Native Voodoo observability primitives."""

from voodoo.observability.api import get_metrics, get_metrics_prometheus
from voodoo.observability.middleware import TelemetryMiddleware
from voodoo.observability.store import (
    Span,
    TelemetryStore,
    TraceFilter,
    correlation_id_var,
    logger,
    new_trace_id,
    store_operation,
    store_span,
    telemetry_store,
    trace,
    trace_id_var,
)

__all__ = [
    "Span",
    "TelemetryMiddleware",
    "TelemetryStore",
    "TraceFilter",
    "correlation_id_var",
    "get_metrics",
    "get_metrics_prometheus",
    "logger",
    "new_trace_id",
    "store_operation",
    "store_span",
    "telemetry_store",
    "trace",
    "trace_id_var",
]
