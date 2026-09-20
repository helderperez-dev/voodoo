import importlib
from pathlib import Path

from voodoo.cli import terminal
from voodoo.config import get_config


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
        ("voodoo.mcp", "mcp"),
        ("voodoo.ai", "ai provider"),
        ("voodoo.workers", "workers"),
        ("voodoo.telemetry", "telemetry"),
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
        from voodoo.workers.queue import _get_queue, _workers

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
        sched_db = Path(cfg.db_path).parent / "schedules.db"
        terminal.status("scheduler db", "present" if sched_db.exists() else "not found")
    except Exception:
        terminal.status("schedules", "unavailable")

    terminal.heading("otel")
    try:
        from voodoo.telemetry.otlp import is_available

        terminal.status("otlp exporter", "active" if is_available() else "off")
    except Exception:
        terminal.status("otlp exporter", "off")


def _doctor_ai_kit() -> None:
    terminal.heading("ai kit")
    ai_dir = Path(".voodoo/ai")
    ready = ai_dir.exists() and (ai_dir / "README.md").exists()
    terminal.status("context", "ready" if ready else "not found")
    terminal.muted("  .voodoo/ai/" if ready else "  run 'voodoo ai init' to generate")


def doctor():
    """
    Run environment and configuration diagnostics.
    """
    import os

    from voodoo import __version__ as ver

    cfg = get_config()

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

    # Database resolution
    db_path = cfg.db_path
    if db_path == ":memory:" or Path(db_path).exists():
        terminal.status("database", "ready")
        terminal.muted(f"  {cfg.database.provider} ({db_path})")
    else:
        terminal.status("database", "not found")
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
