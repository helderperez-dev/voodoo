import sys
from pathlib import Path

from voodoo.cli import terminal


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
    import platform

    import voodoo

    ver = getattr(voodoo, "__version__", "unknown")

    terminal.wordmark(ver)
    terminal.blank()

    # ── Environment ─────────────────────────────────
    terminal.heading("environment")

    py_ver = sys.version_info
    py_ok = py_ver >= (3, 10)
    terminal.status(
        "python",
        "ready" if py_ok else "failed",
    )
    terminal.muted(
        f"  {platform.python_version()} ({platform.python_implementation()})"
    )

    terminal.status("voodoo", "ready")
    terminal.muted(f"  v{ver}")

    # ── Runtime ─────────────────────────────────────
    terminal.heading("runtime")

    from voodoo.config import config

    # Database
    db_path = Path(config.db_path)
    if db_path.exists():
        terminal.status("database", "ready")
        terminal.muted(f"  {db_path}")
    else:
        terminal.status("database", "not found")
        terminal.muted(f"  {db_path}")

    # Auth
    from voodoo.config import config as _cfg

    if _cfg.auth.secret_key and _cfg.auth.secret_key != (
        "dev-secret-key-change-in-production-voodoo-2026"
    ):
        terminal.status("auth", "ready")
    else:
        terminal.status("auth", "warning")
        terminal.muted("  using dev default secret key")

    # Security
    terminal.status(
        "security headers",
        "enabled" if _cfg.security.headers_enabled else "disabled",
    )
    terminal.status(
        "rate limiting",
        "enabled" if _cfg.security.rate_limit_enabled else "disabled",
    )
    terminal.status(
        "cors",
        "enabled" if _cfg.security.cors_enabled else "disabled",
    )
    terminal.status(
        "csrf",
        "enabled" if _cfg.security.csrf_enabled else "disabled",
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
