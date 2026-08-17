import sys
from pathlib import Path

from voodoo.cli import terminal


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
