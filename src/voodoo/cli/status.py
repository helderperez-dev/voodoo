"""voodoo status — coherent application and Runtime overview."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from voodoo.cli import terminal

__all__ = ["status"]


def _application_snapshot() -> dict[str, Any]:
    """Return the stable machine-readable application/Runtime status contract."""
    from voodoo import __version__
    from voodoo.config import get_config
    from voodoo.integrations.otel import is_available as otlp_available
    from voodoo.observability import telemetry_store

    cfg = get_config()
    summary = telemetry_store.get_summary()

    total = int(summary.get("requests_total", 0) or 0)
    errors = int(summary.get("errors_total", 0) or 0)
    store_path = Path(cfg.store.path)
    store_exists = store_path.exists() if cfg.store.path else False

    return {
        "version": __version__,
        "environment": cfg.env,
        "runtime": {
            "mode": cfg.runtime.mode,
            "requests_total": total,
            "errors_total": errors,
            "error_rate": (errors / total) if total else 0.0,
            "average_latency_ms": float(summary.get("average_latency_ms", 0.0) or 0.0),
            "agent_runs": int(summary.get("agent_runs", 0) or 0),
            "tool_calls_total": int(summary.get("tool_calls_total", 0) or 0),
        },
        "store": {
            "provider": cfg.store.provider,
            "path": cfg.store.path,
            "exists": store_exists,
            "enabled": cfg.store.enabled,
            "durability": cfg.store.durability,
        },
        "providers": {
            "database": cfg.database.provider,
            "queue": cfg.queue.provider,
            "events": cfg.events.provider,
            "objects": cfg.objects.provider,
            "cache": cfg.cache.provider,
            "model": cfg.models.default,
        },
        "telemetry": {
            "otlp_export": "active" if otlp_available() else "off",
        },
    }


def status(
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output the stable machine-readable application status.",
    ),
) -> None:
    """Show application persistence, providers and Runtime health."""
    snapshot = _application_snapshot()
    if json_mode or terminal.is_json_mode():
        terminal.json_output(snapshot)
        return

    terminal.wordmark(snapshot["version"])
    terminal.blank()

    terminal.heading("application")
    terminal.status("environment", snapshot["environment"])
    terminal.status("runtime", snapshot["runtime"]["mode"])

    store = snapshot["store"]
    store_state = "ready" if store["exists"] else "not created"
    if not store["enabled"]:
        store_state = "disabled"
    terminal.status("store", store_state)
    terminal.muted(
        f"  {store['provider']} · {store['path']} · durability={store['durability']}"
    )

    terminal.heading("providers")
    for label, provider in snapshot["providers"].items():
        terminal.label_value(label, str(provider))

    runtime = snapshot["runtime"]
    terminal.heading("runtime health")
    terminal.label_value("requests", str(runtime["requests_total"]))
    terminal.label_value("errors", str(runtime["errors_total"]))
    terminal.label_value("error rate", f"{runtime['error_rate'] * 100:.1f}%")
    terminal.label_value("avg latency", f"{runtime['average_latency_ms']:.1f} ms")
    terminal.label_value("agent runs", str(runtime["agent_runs"]))
    terminal.label_value("tool calls", str(runtime["tool_calls_total"]))

    terminal.heading("telemetry")
    terminal.status("otlp export", snapshot["telemetry"]["otlp_export"])
    terminal.blank()
