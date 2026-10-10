import logging
import sqlite3
from collections.abc import Mapping
from math import isfinite
from typing import Any

from starlette.responses import JSONResponse

from voodoo.components import Card, Div, Heading
from voodoo.core.errors import ConfigurationError
from voodoo.data import get_db
from voodoo.i18n import _
from voodoo.routing.api import api
from voodoo.runtime.scheduling.workers import _queue, _worker_tasks
from voodoo.runtime.store import get_active_runtime_store
from voodoo.security.redaction import redact_string
from voodoo.storage import storage

logger = logging.getLogger(__name__)

_REMEDIATION: dict[str, str] = {
    "database": "verify database connectivity and credentials, then retry the health check",
    "queue": "start or reconnect workers and inspect queue backlog before accepting load",
    "storage": "verify the Store path or object provider and available capacity",
    "agent": "verify the configured agent provider and credentials",
    "store": "inspect Store recovery, migration, and capacity details before restarting",
}
_STATUS_POLICY = {
    "Operational": {"http_status": 200, "traffic": "serve"},
    "Degraded": {"http_status": 200, "traffic": "serve_with_attention"},
    "Down": {"http_status": 503, "traffic": "fail_closed"},
}
_MAX_STATUS_DEPTH = 6
_MAX_STATUS_FIELDS = 128
_SENSITIVE_STATUS_KEYS = {
    "id",
    "key",
    "path",
    "namespace",
    "payload",
    "store_id",
}
# Health probes intentionally translate expected provider/configuration failures
# into a bounded Down result, but must not turn framework bugs into healthy-looking
# diagnostics.  Keep this list explicit so new failure modes require review.
_STATUS_CHECK_ERRORS = (
    AttributeError,
    ConnectionError,
    ConfigurationError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    sqlite3.Error,
    TypeError,
    ValueError,
)


def _health_failure(check: str, error: Exception) -> dict[str, str]:
    """Return a redacted health failure and retain structured diagnostics."""
    message = redact_string(str(error))
    logger.warning(
        "health check failed",
        extra={"health_check": check, "error": message},
    )
    return {"status": "Down", "error": message}


async def check_database() -> dict[str, Any]:
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        return {"status": "Operational", "latency": "ok"}
    except _STATUS_CHECK_ERRORS as error:
        return _health_failure("database", error)


async def check_queue() -> dict[str, Any]:
    try:
        total_workers = len(_worker_tasks)
        active_queues = 1 if _queue is not None else 0
        return {
            "status": "Operational" if total_workers > 0 else "Degraded",
            "workers": total_workers,
            "queues": active_queues,
        }
    except _STATUS_CHECK_ERRORS as error:
        return _health_failure("queue", error)


async def check_storage() -> dict[str, Any]:
    try:
        if storage.use_s3 and storage.s3_client:
            return {"status": "Operational", "type": "S3"}
        else:
            import os

            if os.path.exists(storage.base_dir):
                return {"status": "Operational", "type": "Local"}
            return {"status": "Degraded", "type": "Local", "error": "Dir missing"}
    except _STATUS_CHECK_ERRORS as error:
        return _health_failure("storage", error)


async def check_agent() -> dict[str, Any]:
    """Validate the configured model route without making a provider call.

    Health checks must be bounded and side-effect free.  Resolving the model
    route catches malformed aliases/providers while avoiding a network request
    (and therefore avoids turning a probe into an expensive or unavailable LLM
    invocation).  ``verified`` makes that distinction explicit to operators.
    """
    try:
        from voodoo.ai.providers import default_model, resolve_model

        model_ref = default_model()
        provider, model = resolve_model(model_ref)
        return {
            "status": "Operational",
            "provider": provider,
            "model": model,
            "verified": False,
            "probe": "configuration",
        }
    except (
        AttributeError,
        ConfigurationError,
        ImportError,
        TypeError,
        ValueError,
    ) as error:
        return _health_failure("agent", error)


def _status_scalar(value: Any) -> Any:
    """Keep only JSON-safe scalar status values."""
    if isinstance(value, str):
        return redact_string(value)[:512]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if not isinstance(value, float) or isfinite(value) else None
    # Provider-specific objects (bytes, paths, handles, exceptions) are not
    # part of the public status contract and must never cross the JSON boundary.
    return None


def _redact_store_details(value: Any, *, depth: int = 0) -> Any:
    """Return bounded JSON-safe details without exposing provider identifiers."""
    if depth > _MAX_STATUS_DEPTH:
        return None
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_STATUS_FIELDS:
                break
            safe_key = str(key)
            if safe_key.lower() in _SENSITIVE_STATUS_KEYS or safe_key.lower().endswith(
                "_id"
            ):
                continue
            bounded = _redact_store_details(item, depth=depth + 1)
            if bounded is not None:
                result[safe_key] = bounded
        return result
    if isinstance(value, (list, tuple)):
        return [
            bounded
            for item in value[:_MAX_STATUS_FIELDS]
            if (bounded := _redact_store_details(item, depth=depth + 1)) is not None
        ]
    return _status_scalar(value)


async def check_store() -> dict[str, Any]:
    """Project the active Runtime Store into the operational status contract."""
    try:
        runtime_store = get_active_runtime_store()
        if runtime_store is None:
            # Status can be queried before an application lifespan binds its
            # Runtime Store; that is not itself a failure.
            return {"status": "Operational", "bound": False}
        health = runtime_store.health()
        if health is None:
            return {"status": "Degraded", "bound": True, "opened": False}
        details = _redact_store_details(health.details)
        if not isinstance(details, dict):
            details = {}
        if not health.opened:
            status = "Degraded"
        elif not health.verified:
            status = "Down"
        elif details.get("within_limit", True) is False:
            status = "Degraded"
        else:
            status = "Operational"
        return {
            "status": status,
            "provider": health.provider,
            "opened": health.opened,
            "verified": health.verified,
            "details": details,
        }
    except _STATUS_CHECK_ERRORS as error:
        return _health_failure("store", error)


@api.get("/status")
async def get_status() -> JSONResponse:
    db_health = await check_database()
    queue_health = await check_queue()
    storage_health = await check_storage()
    agent_health = await check_agent()
    store_health = await check_store()

    services = [db_health, queue_health, storage_health, agent_health, store_health]
    has_down = any(service["status"] == "Down" for service in services)
    has_degraded = any(service["status"] == "Degraded" for service in services)
    overall = "Down" if has_down else "Degraded" if has_degraded else "Operational"
    degraded = [
        name
        for name, service in (
            ("database", db_health),
            ("queue", queue_health),
            ("storage", storage_health),
            ("agent", agent_health),
            ("store", store_health),
        )
        if service["status"] == "Degraded"
    ]
    attention = {
        name: _REMEDIATION[name]
        for name, service in (
            ("database", db_health),
            ("queue", queue_health),
            ("storage", storage_health),
            ("agent", agent_health),
            ("store", store_health),
        )
        if service["status"] in {"Degraded", "Down"}
    }
    return JSONResponse(
        {
            "services": {
                "database": db_health,
                "queue": queue_health,
                "storage": storage_health,
                "agent": agent_health,
                "store": store_health,
            },
            "overall": overall,
            "degraded": degraded,
            "attention": attention,
            "policy": _STATUS_POLICY[overall],
        },
        status_code=503 if has_down else 200,
    )


@api.get("/status/locales")
async def get_status_locales() -> dict[str, str]:
    return {
        "database": _("status.database"),
        "queue": _("status.queue"),
        "storage": _("status.storage"),
        "agent": _("status.agent"),
        "Operational": _("status.operational"),
        "Degraded": _("status.degraded"),
        "Down": _("status.down"),
    }


class ServiceStatus(Div):
    def __init__(self, **kwargs: Any) -> None:
        # Provide default glass aesthetics for the card
        classes = kwargs.pop("className", "")
        card_classes = f"bg-[var(--color-surface)] border-[var(--color-border)] backdrop-blur-xl {classes}".strip()
        super().__init__(
            Card(
                Heading(
                    _("status.title"),
                    level=2,
                    className="text-xl font-semibold mb-6 text-[var(--color-text)] tracking-tight",
                ),
                Div(id="service-status-container", className="space-y-3"),
                Div(
                    """
                    <script>
                        async function fetchStatus() {
                            try {
                                const [resStatus, resLocales] = await Promise.all([
                                    fetch('/status'),
                                    fetch('/status/locales')
                                ]);
                                const data = await resStatus.json();
                                const locales = await resLocales.json();

                                const container = document.getElementById('service-status-container');
                                let html = '';
                                for (const [service, info] of Object.entries(data.services)) {
                                    let color = info.status === 'Operational' ? 'text-green-400' : (info.status === 'Degraded' ? 'text-yellow-400' : 'text-red-400');
                                    let dot = info.status === 'Operational' ? 'bg-green-400' : (info.status === 'Degraded' ? 'bg-yellow-400' : 'bg-red-400');
                                    let serviceName = locales[service] || service;
                                    let statusName = locales[info.status] || info.status;
                                    html += `
                                        <div class="flex items-center justify-between p-3 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] backdrop-blur-sm">
                                            <div class="flex items-center space-x-3">
                                                <div class="w-2.5 h-2.5 rounded-full ${dot} shadow-[0_0_8px_rgba(0,0,0,0.5)] shadow-${dot.replace('bg-', '')}"></div>
                                                <span class="capitalize text-[var(--color-text)] font-medium tracking-wide">${serviceName}</span>
                                            </div>
                                            <span class="${color} font-semibold text-sm tracking-wide">${statusName}</span>
                                        </div>
                                    `;
                                }
                                container.innerHTML = html;
                            } catch (e) {
                                console.error('Failed to fetch status', e);
                            }
                        }
                        fetchStatus();
                        setInterval(fetchStatus, 10000);
                    </script>
                    """
                ),
                className=card_classes,
                **kwargs,
            )
        )
