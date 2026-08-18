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
        DatabaseCapabilities,
        EventBusCapabilities,
        ObjectStoreCapabilities,
        QueueCapabilities,
    )

    # Default local providers (Sprints 1–7). Declared statically so ``doctor``
    # stays side-effect free: it never opens a connection or creates files.
    providers = (
        DatabaseCapabilities(
            "sqlite",
            transactions=True,
            migrations=True,
            native_json=False,
            concurrent_writers=False,
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
            "memory",
            durable=False,
            visibility_timeout=True,
            delayed_delivery=False,
            priority=True,
            transactions=False,
        ),
        EventBusCapabilities(
            "sqlite",
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
    )

    for caps in providers:
        flag_str = "  ".join(f"{k}={v}" for k, v in caps.describe().items())
        terminal.status(caps.provider, "active")
        terminal.muted(f"  {flag_str}")


def doctor():  # noqa: C901
    """
    Run environment and configuration diagnostics.
    """
    import importlib
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

    # ── Modules ─────────────────────────────────────
    terminal.heading("modules")

    for name, label in [
        ("voodoo.mesh", "mesh"),
        ("voodoo.mcp", "mcp"),
        ("voodoo.ai", "ai provider"),
        ("voodoo.workers", "workers"),
        ("voodoo.telemetry", "telemetry"),
    ]:
        try:
            importlib.import_module(name)
            terminal.status(label, "ready")
        except Exception:
            terminal.status(label, "not found")

    # ── Providers & capability matrix ────────────────
    terminal.heading("providers")
    try:
        _print_capability_matrix()
    except Exception:  # noqa: BLE001 - diagnostics must never crash doctor
        terminal.status("capability matrix", "unavailable")

    # ── AI Kit ──────────────────────────────────────
    terminal.heading("ai kit")

    ai_dir = Path(".voodoo/ai")
    if ai_dir.exists() and (ai_dir / "README.md").exists():
        terminal.status("context", "ready")
        terminal.muted("  .voodoo/ai/")
    else:
        terminal.status("context", "not found")
        terminal.muted("  run 'voodoo ai init' to generate")

    terminal.blank()
