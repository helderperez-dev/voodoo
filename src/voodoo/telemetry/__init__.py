"""Compatibility facade for :mod:`voodoo.observability`."""

from voodoo.observability import (
    Span,
    TelemetryMiddleware,
    TelemetryStore,
    TraceFilter,
    get_metrics,
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
