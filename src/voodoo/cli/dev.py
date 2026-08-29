import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import typer

from voodoo.cli import terminal


def dev(
    app_str: str = typer.Argument(
        None,
        help="App instance to run (e.g., main:app). Defaults to main:app if main.py exists, otherwise voodoo.core:app",
    ),
    port: int = typer.Option(8000, help="Port to run the server on"),
):
    """
    Start the Voodoo development server.
    """
    # Auto-discover app: prefer main:app for backward compat, fall back to voodoo.core:app
    if app_str is None:
        if Path("main.py").exists():
            app_str = "main:app"
        else:
            app_str = "voodoo.core:app"

    module_name = app_str.split(":")[0]

    # Resolve the module either as a local file/dir (e.g. main.py) or as an
    # importable installed package (e.g. voodoo.core). Folder-based routing
    # projects have no main.py and rely on the bundled voodoo.core:app fallback.
    module_path = Path(module_name.replace(".", "/") + ".py")
    module_dir = Path(module_name.replace(".", "/"))
    local_exists = module_path.exists() or (
        module_dir.is_dir() and (module_dir / "__init__.py").exists()
    )
    try:
        importable = importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        # find_spec raises ModuleNotFoundError for dotted names whose parent
        # package is missing (e.g. "myapp.sub" when "myapp" isn't installed)
        # and ValueError for relative names without a package context. Treat
        # both as "not importable" so the caller gets the clean error below.
        importable = False

    if not local_exists and not importable:
        terminal.error(
            f"Could not find module '{module_name}'",
            hint="run from inside a voodoo project, or use 'voodoo new <name>' to create one",
        )
        raise typer.Exit(1)

    import voodoo

    ver = getattr(voodoo, "__version__", "unknown")
    from voodoo.config import config as _cfg

    host = _cfg.host
    display_host = "localhost" if host in ("0.0.0.0", "::", "") else host
    local_url = f"http://{display_host}:{port}"

    terminal.wordmark(ver)
    terminal.blank()
    terminal.status("runtime", "running")
    terminal.label_value("environment", "development")
    terminal.blank()
    terminal.label_value("local", local_url)
    terminal.label_value("docs", f"{local_url}/docs")
    terminal.blank()

    # Sprint 22: runtime banner — show providers and runtime state
    _print_runtime_banner()

    local_venv_python = (
        Path(".venv/bin/python")
        if os.name != "nt"
        else Path(".venv/Scripts/python.exe")
    )

    if local_venv_python.exists():
        python_exe = str(local_venv_python.absolute())
        terminal.muted("using local .venv")
    else:
        python_exe = sys.executable
        terminal.muted("using global environment")

    terminal.blank()

    env = os.environ.copy()
    # NOTE: do NOT inject the CLI's own `sys.path` into PYTHONPATH. When the CLI
    # runs from a bundled install (Homebrew, uv tool) its site-packages contain a
    # DIFFERENT voodoo version than the project's `.venv`; prepending those paths
    # shadows the project's installed voodoo and serves stale code. `python -m
    # uvicorn` already places the cwd on sys.path, so local `main.py`/`app.py`
    # modules resolve without any PYTHONPATH manipulation.
    env["WEBSOCKETS_MAX_LINE_LENGTH"] = "8388608"
    env["WEBSOCKETS_MAX_NUM_HEADERS"] = "256"

    try:
        subprocess.run(
            [
                python_exe,
                "-m",
                "uvicorn",
                app_str,
                "--reload",
                "--port",
                str(port),
                "--http",
                "h11",
                "--ws",
                "auto",
                "--h11-max-incomplete-event-size",
                "5242880",
            ],
            env=env,
        )
    except KeyboardInterrupt:
        terminal.blank()
        terminal.status("runtime", "stopped")


def _print_runtime_banner() -> None:
    """Print runtime providers and state (Sprint 22)."""
    from voodoo.config import get_config

    cfg = get_config()

    # Providers
    terminal.heading("providers")
    db_provider = cfg.database.provider.lower()
    terminal.status("database", db_provider)

    queue_provider = cfg.queue.provider.lower()
    terminal.status("queue", queue_provider)

    # Object store
    terminal.status("objects", cfg.objects.provider.lower())

    # Agent runtime
    try:
        from voodoo.ai.providers import _PROVIDER_CLASSES

        providers = list(_PROVIDER_CLASSES.keys())
        terminal.status("agents", ", ".join(providers) if providers else "none")
    except Exception:
        terminal.status("agents", "mock")

    # MCP endpoint
    terminal.label_value("mcp", "/mcp")

    # Registered workers
    try:
        from voodoo.workers.queue import _workers

        worker_names = list(_workers.keys())
        if worker_names:
            terminal.label_value("workers", ", ".join(worker_names))
        else:
            terminal.label_value("workers", "none")
    except Exception:
        terminal.label_value("workers", "none")

    # Schedules DB
    schedule_path = Path(".voodoo/state/schedules.db")
    if schedule_path.exists():
        terminal.status("scheduler", "ready")
    else:
        terminal.status("scheduler", "will be created")

    terminal.blank()
