"""Optional OpenTelemetry OTLP exporter.

Activated only when the ``[otel]`` extra is installed **and**
``VOODOO_OTEL_EXPORTER`` is set (any non-empty value).  When
active, completed :class:`Span` objects are forwarded to the
configured OTLP endpoint (default ``http://localhost:4317``).

Usage::

    pip install voodoo-framework[otel]
    export VOODOO_OTEL_EXPORTER=1
    # optional: export OTEL_EXPORTER_OTLP_ENDPOINT=http://my-collector:4317
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("voodoo.telemetry.otlp")

__all__ = ["OTLPExporter", "is_available", "export_span"]

#: Cached exporter instance (lazy-initialised).
_exporter: OTLPExporter | None = None
_checked: bool = False


def is_available() -> bool:
    """Return ``True`` if OTel SDK is importable and the env var is set."""
    try:
        import opentelemetry  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("VOODOO_OTEL_EXPORTER"))


class OTLPExporter:
    """Thin wrapper around the OTel SDK's OTLP gRPC exporter.

    Each call to :meth:`export_span` builds an OTel ``Span`` from our
    :class:`voodoo.telemetry.store.Span` and forwards it via the
    configured ``TracerProvider``.
    """

    def __init__(self) -> None:
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        provider = TracerProvider()
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        provider.add_span_processor(processor)
        otel_trace.set_tracer_provider(provider)
        self._tracer = otel_trace.get_tracer("voodoo")
        logger.info("OTLP exporter initialised → %s", endpoint)

    def export_span(self, span: Any) -> None:
        """Convert a voodoo :class:`Span` to an OTel span and export it."""
        from opentelemetry import trace as otel_trace
        from opentelemetry.trace import StatusCode

        with self._tracer.start_as_current_span(
            span.name,
            kind=otel_trace.SpanKind.INTERNAL,
            attributes=dict(span.attributes) if span.attributes else {},
        ) as otel_span:
            if span.status == "error":
                otel_span.set_status(StatusCode.ERROR)
            else:
                otel_span.set_status(StatusCode.OK)
            if span.end_time and span.start_time:
                otel_span.set_attribute(
                    "duration_ms",
                    (span.end_time - span.start_time).total_seconds() * 1000,
                )


def _get_exporter() -> OTLPExporter | None:
    """Return the singleton exporter, or ``None`` if unavailable."""
    global _exporter, _checked
    if _checked:
        return _exporter
    _checked = True
    if is_available():
        try:
            _exporter = OTLPExporter()
        except Exception:  # noqa: BLE001 — graceful degradation
            logger.warning("Failed to initialise OTLP exporter", exc_info=True)
            _exporter = None
    return _exporter


def export_span(span: Any) -> None:
    """Forward *span* to the OTLP endpoint if the exporter is active."""
    exporter = _get_exporter()
    if exporter is not None:
        try:
            exporter.export_span(span)
        except Exception:  # noqa: BLE001 — never break the runtime
            logger.debug("OTLP export failed for span %s", span.span_id, exc_info=True)
