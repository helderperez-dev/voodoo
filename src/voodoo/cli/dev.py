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
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
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
