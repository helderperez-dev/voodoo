import logging
from collections.abc import Iterator, Mapping
from math import isfinite
from numbers import Real

from starlette.responses import PlainTextResponse

from voodoo.observability.store import telemetry_store
from voodoo.routing.api import api
from voodoo.security.redaction import redact_string

logger = logging.getLogger("voodoo.observability.api")

_MAX_METRIC_DEPTH = 6
_MAX_METRIC_FIELDS = 256
_SENSITIVE_METRIC_KEYS = {
    "id",
    "key",
    "path",
    "namespace",
    "payload",
    "store_id",
    "session_id",
    "token",
    "secret",
}


def _bounded_metric_details(value: object, *, depth: int = 0) -> object | None:
    """Keep only bounded scalar health data suitable for metrics responses."""
    if depth > _MAX_METRIC_DEPTH:
        return None
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_METRIC_FIELDS:
                break
            safe_key = str(key)
            lowered = safe_key.lower()
            if (
                lowered in _SENSITIVE_METRIC_KEYS
                or lowered.endswith("_id")
                or any(
                    fragment in lowered
                    for fragment in (
                        "key",
                        "path",
                        "namespace",
                        "payload",
                        "secret",
                        "token",
                    )
                )
            ):
                continue
            bounded = _bounded_metric_details(item, depth=depth + 1)
            if bounded is not None:
                result[safe_key] = bounded
        return result or None
    if isinstance(value, bool):
        return value
    if isinstance(value, Real):
        numeric = float(value)
        if isfinite(numeric):
            return value
    return None


def _store_health_projection() -> dict[str, object] | None:
    """Return sanitized active-Store health for metrics consumers."""
    try:
        from voodoo.runtime.store import get_active_runtime_store

        runtime_store = get_active_runtime_store()
        if runtime_store is None:
            return None
        health = runtime_store.health()
        if health is None:
            return None
        return {
            "provider": health.provider,
            "opened": health.opened,
            "verified": health.verified,
            "details": _bounded_metric_details(health.details) or {},
        }
    except Exception as error:
        logger.warning(
            "Store metrics health projection failed error=%s",
            redact_string(str(error)),
        )
        return {"available": False}


def _numeric_metrics(prefix: str, value: object) -> Iterator[tuple[str, Real]]:
    """Yield flattened numeric metric names without exposing string fields."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            safe_key = "".join(
                character if character.isalnum() else "_" for character in str(key)
            ).strip("_")
            if safe_key:
                yield from _numeric_metrics(f"{prefix}_{safe_key}", item)
    elif isinstance(value, Real) and not isinstance(value, bool):
        numeric = float(value)
        if isfinite(numeric):
            yield prefix, value


@api.get("/voodoo/metrics")
async def get_metrics() -> dict[str, object]:
    summary = telemetry_store.get_summary()
    store_health = _store_health_projection()
    if store_health is not None:
        summary["store_health"] = store_health
    return summary


@api.get("/voodoo/metrics/prometheus")
async def get_metrics_prometheus() -> PlainTextResponse:
    """Expose bounded numeric telemetry in Prometheus text format."""
    summary = telemetry_store.get_summary()
    store_health = _store_health_projection()
    if store_health is not None:
        summary["store_health"] = store_health
    lines = [
        "# HELP voodoo_metrics_info Voodoo runtime metrics schema version.",
        "# TYPE voodoo_metrics_info gauge",
        'voodoo_metrics_info{version="1"} 1',
    ]
    for key, value in summary.items():
        flattened = _numeric_metrics("voodoo_" + key.replace("-", "_"), value)
        for metric, numeric_value in flattened:
            metric_type = "counter" if metric.endswith("_total") else "gauge"
            lines.append(f"# TYPE {metric} {metric_type}")
            lines.append(f"{metric} {numeric_value}")
    return PlainTextResponse(
        "\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
