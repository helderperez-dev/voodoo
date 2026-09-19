"""Native Voodoo observability primitives."""

from voodoo.observability.api import get_metrics
from voodoo.observability.middleware import TelemetryMiddleware
from voodoo.observability.store import (
    Span,
    TelemetryStore,
    TraceFilter,
    logger,
    new_trace_id,
    telemetry_store,
    trace,
    trace_id_var,
)

__all__ = [
    "Span",
    "TelemetryMiddleware",
    "TelemetryStore",
    "TraceFilter",
    "get_metrics",
    "logger",
    "new_trace_id",
    "telemetry_store",
    "trace",
    "trace_id_var",
]
