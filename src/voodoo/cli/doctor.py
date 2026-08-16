import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()


def doctor():  # noqa: C901
    """
    Run environment and configuration diagnostics.
    """
    import importlib
    import platform

    console.print(Panel.fit("🔍 Voodoo Doctor - Diagnostics", border_style="cyan"))

    checks = []

    # -- Runtime --
    py_ver = sys.version_info
    if py_ver >= (3, 10):
        checks.append(
            (
                "✓",
                "green",
                f"Python version {platform.python_version()} (>= 3.10 required)",
            )
        )
    else:
        checks.append(
            (
                "✗",
                "red",
                f"Python version {platform.python_version()} (< 3.10 unsupported)",
            )
        )

    import voodoo

    ver = getattr(voodoo, "__version__", "unknown")
    checks.append(("✓", "green", f"Voodoo Framework v{ver}"))

    # -- Database --
    from voodoo.config import config

    db_path = Path(config.db_path)
    if db_path.exists():
        checks.append(("✓", "green", f"Database found at {db_path}"))
    else:
        checks.append(("ℹ", "yellow", f"Database ({db_path}) not initialized yet"))

    # -- Auth --
    from voodoo.config import config as _cfg

    if _cfg.auth.secret_key and _cfg.auth.secret_key != (
        "dev-secret-key-change-in-production-voodoo-2026"
    ):
        checks.append(("✓", "green", "Auth secret key configured"))
    else:
        checks.append(
            (
                "⚠",
                "yellow",
                "Auth secret key is using dev default — set VOODOO_SECRET_KEY in production",
            )
        )

    cookie_secure = _cfg.auth.cookie_secure
    if _cfg.env == "production" and not cookie_secure:
        checks.append(("⚠", "yellow", "Cookie Secure flag is OFF in production mode"))
    else:
        checks.append(("✓", "green", f"Cookie Secure flag: {cookie_secure}"))

    # -- Security --
    checks.append(
        (
            "✓" if _cfg.security.headers_enabled else "⚠",
            "green" if _cfg.security.headers_enabled else "yellow",
            f"Security headers {'enabled' if _cfg.security.headers_enabled else 'disabled'}",
        )
    )
    checks.append(
        (
            "✓" if _cfg.security.rate_limit_enabled else "⚠",
            "green" if _cfg.security.rate_limit_enabled else "yellow",
            f"Rate limiting {'enabled' if _cfg.security.rate_limit_enabled else 'disabled'}",
        )
    )
    checks.append(
        (
            "✓" if _cfg.security.cors_enabled else "⚠",
            "green" if _cfg.security.cors_enabled else "yellow",
            f"CORS {'enabled' if _cfg.security.cors_enabled else 'disabled'}",
        )
    )
    checks.append(
        (
            "✓" if _cfg.security.csrf_enabled else "ℹ",
            "green" if _cfg.security.csrf_enabled else "yellow",
            f"CSRF {'enabled' if _cfg.security.csrf_enabled else 'disabled'}",
        )
    )

    # -- Mesh --
    try:
        importlib.import_module("voodoo.mesh")

        checks.append(("✓", "green", "Mesh module available"))
    except Exception:
        checks.append(("✗", "red", "Mesh module failed to import"))

    # -- MCP --
    try:
        importlib.import_module("voodoo.mcp")

        checks.append(("✓", "green", "MCP module available"))
    except Exception:
        checks.append(("ℹ", "yellow", "MCP module not available"))

    # -- AI Provider --
    try:
        importlib.import_module("voodoo.ai")

        checks.append(("✓", "green", "AI provider module available"))
    except Exception:
        checks.append(("ℹ", "yellow", "AI provider module not available"))

    # -- Workers --
    try:
        importlib.import_module("voodoo.workers")

        checks.append(("✓", "green", "Workers module available"))
    except Exception:
        checks.append(("✗", "red", "Workers module failed to import"))

    # -- Telemetry --
    try:
        importlib.import_module("voodoo.telemetry")

        checks.append(("✓", "green", "Telemetry module available"))
    except Exception:
        checks.append(("✗", "red", "Telemetry module failed to import"))

    # -- AI Kit --
    ai_dir = Path(".voodoo/ai")
    if ai_dir.exists() and (ai_dir / "README.md").exists():
        checks.append(("✓", "green", "AI Kit context available (.voodoo/ai)"))
    else:
        checks.append(
            ("ℹ", "yellow", "AI Kit context not present (run 'voodoo new' to scaffold)")
        )

    for symbol, color, msg in checks:
        console.print(f" [{color}]{symbol}[/{color}] {msg}")
