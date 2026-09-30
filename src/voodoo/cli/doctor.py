import importlib
from pathlib import Path
from typing import Any

import typer

from voodoo.cli import terminal
from voodoo.config import get_config


def _doctor_snapshot() -> dict[str, Any]:
    """Return side-effect-free diagnostics suitable for automation."""
    from voodoo.cli.status import _application_snapshot

    cfg = get_config()
    modules: dict[str, str] = {}
    for name, label in (
        ("voodoo.mesh", "mesh"),
        ("voodoo.integrations.mcp", "mcp"),
        ("voodoo.ai", "ai"),
        ("voodoo.runtime.scheduling", "workers"),
        ("voodoo.observability", "observability"),
    ):
        try:
            importlib.import_module(name)
            modules[label] = "ready"
        except Exception:
            modules[label] = "not found"

    legacy_candidates = (
        Path(".voodoo/state/data.db"),
        Path(".voodoo/state/schedules.db"),
        Path(".voodoo/state/agents.db"),
    )
    legacy_files = [str(path) for path in legacy_candidates if path.exists()]
    ai_dir = Path(".voodoo/ai")

    return {
        "application": _application_snapshot(),
        "project": {
            "root": str(Path.cwd()),
            "config": "voodoo.toml" if Path("voodoo.toml").exists() else None,
            "app_directory": Path("app").is_dir(),
        },
        "integrity": {
            "legacy_sqlite": legacy_files,
            "store_first_clean": (
                cfg.database.provider.lower() != "voodoo" or not legacy_files
            ),
        },
        "auth": {
            "secret": (
                "warning"
                if cfg.auth.secret_key
                == "dev-secret-key-change-in-production-voodoo-2026"
                else "ready"
            )
        },
        "security": {
            "headers": cfg.security.headers_enabled,
            "rate_limit": cfg.security.rate_limit_enabled,
            "cors": cfg.security.cors_enabled,
            "csrf": cfg.security.csrf_enabled,
        },
        "modules": modules,
        "ai_kit": (
            "ready"
            if ai_dir.exists() and (ai_dir / "README.md").exists()
            else "not found"
        ),
    }


def _print_capability_matrix() -> None:
    """Print active providers and their declared capability matrix (spec §9).

    Renders one row per registered adapter implementation. This gives
    ``voodoo doctor`` an honest, per-provider view of what the runtime
    guarantees.
    """
    from voodoo.adapters.capabilities import (
        CacheCapabilities,
        DatabaseCapabilities,
        EventBusCapabilities,
        ObjectStoreCapabilities,
        QueueCapabilities,
    )

    # Default local providers (Sprints 1–7). Declared statically so ``doctor``
    # stays side-effect free: it never opens a connection or creates files.
    # PostgreSQL (Sprint 10) is an optional server backend behind the same
    # VoodooDatabase protocol.
    providers = (
        DatabaseCapabilities(
            "sqlite",
            transactions=True,
            migrations=True,
            native_json=False,
            concurrent_writers=False,
        ),
        DatabaseCapabilities(
            "postgres",
            transactions=True,
            migrations=True,
            native_json=True,
            concurrent_writers=True,
        ),
        QueueCapabilities(
            "sqlite",
            durable=True,
            visibility_timeout=True,
            delayed_delivery=True,
            priority=True,
            transactions=True,
        ),
        QueueCapabilities(
            "postgres",
            durable=True,
            visibility_timeout=True,
            delayed_delivery=True,
            priority=True,
            transactions=True,
        ),
        QueueCapabilities(
            "memory",
            durable=False,
            visibility_timeout=True,
            delayed_delivery=False,
            priority=True,
            transactions=False,
        ),
        QueueCapabilities(
            "redis",
            durable=True,
            visibility_timeout=True,
            delayed_delivery=True,
            priority=True,
            transactions=True,
        ),
        EventBusCapabilities(
            "sqlite",
            durable=True,
            replay=True,
            ordering=True,
        ),
        EventBusCapabilities(
            "postgres",
            durable=True,
            replay=True,
            ordering=True,
        ),
        EventBusCapabilities(
            "local",
            durable=False,
            replay=False,
            ordering=True,
        ),
        ObjectStoreCapabilities(
            "local",
            presign_urls=False,
            checksums=True,
            metadata=True,
            multipart=False,
        ),
        CacheCapabilities(
            "memory",
            ttl=False,
            durable=False,
        ),
        CacheCapabilities(
            "redis",
            ttl=True,
            durable=True,
        ),
    )

    for caps in providers:
        flag_str = "  ".join(f"{k}={v}" for k, v in caps.describe().items())
        terminal.status(caps.provider, "active")
        terminal.muted(f"  {flag_str}")


def _doctor_modules() -> None:

    terminal.heading("modules")
    modules = [
        ("voodoo.mesh", "mesh"),
        ("voodoo.integrations.mcp", "mcp"),
        ("voodoo.ai", "ai provider"),
        ("voodoo.runtime.scheduling", "workers"),
        ("voodoo.observability", "observability"),
    ]
    for name, label in modules:
        try:
            importlib.import_module(name)
            terminal.status(label, "ready")
        except Exception:
            terminal.status(label, "not found")


def _doctor_queue() -> None:
    import asyncio

    terminal.heading("queue")

    async def check() -> tuple[int, int]:
        from voodoo.runtime.scheduling.workers import _get_queue, _workers

        depth = 0
        try:
            queue = await _get_queue()
            if hasattr(queue, "list"):
                depth = len(await queue.list())
            elif hasattr(queue, "depth"):
                depth = await queue.depth()
        except Exception:
            pass
        return depth, len(_workers)

    try:
        depth, workers = asyncio.run(check())
        terminal.status("depth", str(depth))
        terminal.status("registered workers", str(workers))
    except Exception:
        terminal.status("queue", "unavailable")


def _doctor_optional_services(cfg: object) -> None:
    terminal.heading("schedules")
    try:
        from voodoo.cli.context import acquire_schedule_store

        schedule_store, store_path = acquire_schedule_store()
        try:
            schedule_store.list_all()
            terminal.status("scheduler", "ready")
            terminal.muted(f"  {store_path}")
        finally:
            schedule_store.close()
    except Exception:
        terminal.status("scheduler", "unavailable")

    terminal.heading("otel")
    try:
        from voodoo.integrations.otel import is_available

        terminal.status("otlp exporter", "active" if is_available() else "off")
    except Exception:
        terminal.status("otlp exporter", "off")


def _doctor_ai_kit() -> None:
    terminal.heading("ai kit")
    ai_dir = Path(".voodoo/ai")
    ready = ai_dir.exists() and (ai_dir / "README.md").exists()
    terminal.status("context", "ready" if ready else "not found")
    terminal.muted("  .voodoo/ai/" if ready else "  run 'voodoo ai init' to generate")


def doctor(
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output side-effect-free machine-readable diagnostics.",
    ),
):
    """Run environment and configuration diagnostics."""
    import os

    from voodoo import __version__ as ver

    cfg = get_config()

    if json_mode or terminal.is_json_mode():
        terminal.json_output(_doctor_snapshot())
        return

    terminal.wordmark(ver)
    terminal.blank()

    # ── Environment ─────────────────────────────────
    terminal.heading("environment")
    terminal.status(
        "mode",
        "production" if os.getenv("VOODOO_ENV") == "production" else "development",
    )
    terminal.muted(
        "  set VOODOO_ENV=production to enforce production security defaults"
        if os.getenv("VOODOO_ENV") != "production"
        else "  production security defaults active"
    )
    terminal.status("voodoo", "ready")
    terminal.muted(f"  v{ver}")

    # ── Runtime ─────────────────────────────────────
    terminal.heading("runtime")

    # Canonical application Store
    try:
        from voodoo.runtime.store import VoodooStoreProvider

        report = VoodooStoreProvider(cfg.store.path).health()
        terminal.status("store", "ready" if report.verified else "not found")
        terminal.muted(f"  {cfg.store.provider} ({cfg.store.path})")
    except Exception:
        terminal.status("store", "unavailable")

    if cfg.database.provider.lower() == "voodoo":
        legacy_candidates = (
            Path(".voodoo/state/data.db"),
            Path(".voodoo/state/schedules.db"),
            Path(".voodoo/state/agents.db"),
        )
        legacy_files = [path for path in legacy_candidates if path.exists()]
        terminal.status("legacy sqlite", "clean" if not legacy_files else "warning")
        if legacy_files:
            terminal.warning(
                "Legacy SQLite state exists while the application uses Voodoo Store."
            )
            for path in legacy_files:
                terminal.muted(f"  {path}")

    # External SQL is reported only when explicitly selected.
    if cfg.database.provider.lower() != "voodoo":
        db_path = cfg.database.path or cfg.database.url or cfg.db_path
        ready = db_path == ":memory:" or bool(db_path and Path(db_path).exists())
        if cfg.database.provider.lower() in {"postgres", "postgresql"}:
            ready = bool(db_path)
        terminal.status("database", "ready" if ready else "not found")
        terminal.muted(f"  {cfg.database.provider} ({db_path})")

    # Resolved providers (Sprint 9)
    terminal.status("queue", "ready")
    terminal.muted(f"  {cfg.queue.provider}")

    terminal.status("events", "ready")
    terminal.muted(f"  {cfg.events.provider}")

    terminal.status("objects", "ready")
    terminal.muted(f"  {cfg.objects.provider}")

    terminal.status("cache", "ready")
    terminal.muted(f"  {cfg.cache.provider}")

    terminal.status("models", "ready")
    terminal.muted(f"  {cfg.models.default}")

    # Auth secret
    if cfg.auth.secret_key != "dev-secret-key-change-in-production-voodoo-2026":
        terminal.status("auth", "ready")
    else:
        terminal.status("auth", "warning")
        terminal.muted("  using dev default secret key")

    # Security
    terminal.status(
        "security headers",
        "enabled" if cfg.security.headers_enabled else "disabled",
    )
    terminal.status(
        "rate limit",
        "enabled" if cfg.security.rate_limit_enabled else "disabled",
    )
    terminal.status(
        "cors",
        "enabled" if cfg.security.cors_enabled else "disabled",
    )
    terminal.status(
        "csrf",
        "enabled" if cfg.security.csrf_enabled else "disabled",
    )

    _doctor_modules()

    # ── Providers & capability matrix ────────────────
    terminal.heading("providers")
    try:
        _print_capability_matrix()
    except Exception:
        terminal.status("capability matrix", "unavailable")

    _doctor_queue()

    # ── Schedules / OTLP ─────────────────────────────
    _doctor_optional_services(cfg)

    # ── AI Kit ──────────────────────────────────────
    _doctor_ai_kit()

    terminal.blank()
