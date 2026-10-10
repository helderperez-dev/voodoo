import shutil
import subprocess
import sys
import tempfile
from importlib.resources import as_file, files
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from voodoo.cli import terminal


def _scaffold_offline(project_dir: Path, name: str) -> None:
    """Write the package-owned default scaffold (Voodoo CSS + folder routing)."""
    resource = files("voodoo").joinpath("scaffold", "default")
    with as_file(resource) as scaffold_dir:
        shutil.copytree(scaffold_dir, project_dir, dirs_exist_ok=True)
    for path in project_dir.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".toml", ".md", ".txt"}:
            path.write_text(path.read_text().replace("{{ project_name }}", name))


def _template_url(template: str) -> str:
    if template.startswith(("http://", "https://", "git@", "/", "file://")):
        return template
    if len(template.split("/")) == 2:
        return f"https://github.com/{template}.git"
    terminal.error(
        "Template must be a valid Git URL, local path, or 'user/repo'",
        hint="pass --template with a Git URL, local path, or owner/repository",
    )
    raise typer.Exit(1)


def _clone_template(project_dir: Path, template: str, variant: str) -> bool:
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            subprocess.run(
                ["git", "clone", "--depth", "1", _template_url(template), tmp_dir],
                check=True,
                capture_output=True,
            )
            variant_path = Path(tmp_dir) / variant
            if not variant_path.exists() or not variant_path.is_dir():
                if variant == "default" and not (Path(tmp_dir) / "default").exists():
                    variant_path = Path(tmp_dir)
                else:
                    terminal.error(
                        f"Variant '${variant}' not found in template repository",
                        hint="choose an existing variant or omit --variant for the default scaffold",
                    )
                    raise typer.Exit(1)
            shutil.copytree(variant_path, project_dir, dirs_exist_ok=True)
    except subprocess.CalledProcessError:
        return False
    if (project_dir / ".git").exists():
        shutil.rmtree(project_dir / ".git", ignore_errors=True)
    return True


def _install_project(project_dir: Path, progress: Progress) -> None:
    if not (project_dir / "pyproject.toml").exists():
        return
    task = progress.add_task(description="setting up .venv...", total=None)
    try:
        if shutil.which("uv") is not None:
            subprocess.run(
                ["uv", "venv"], cwd=project_dir, check=True, capture_output=True
            )
            progress.update(task, description="installing dependencies...")
            command = ["uv", "pip", "install", "-e", "."]
        else:
            subprocess.run(
                [sys.executable, "-m", "venv", ".venv"],
                cwd=project_dir,
                check=True,
                capture_output=True,
            )
            progress.update(task, description="installing dependencies...")
            pip_exe = (
                ".venv/bin/pip"
                if sys.platform != "win32"
                else ".venv\\Scripts\\pip.exe"
            )
            command = [str(project_dir / pip_exe), "install", "-e", "."]
        subprocess.run(command, cwd=project_dir, check=True, capture_output=True)
        for item in project_dir.glob("*.egg-info"):
            if item.is_dir():
                shutil.rmtree(item)
    except subprocess.CalledProcessError as exc:
        terminal.warning("Failed to set up environment or install dependencies")
        if exc.stderr:
            terminal.muted(exc.stderr.decode().strip())


def new(
    project_name: str,
    template: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Optional Git URL or 'user/repo'. The default scaffold is built in.",
    ),
    variant: str = typer.Option(
        "default",
        "--variant",
        "-v",
        help="Specific template variant inside the repository",
    ),
    install: bool = typer.Option(
        True,
        "--install/--no-install",
        help="Create a local environment and install project dependencies.",
    ),
) -> None:
    """Scaffold a new Voodoo project or clone a community template."""
    project_dir = Path(project_name)
    if project_dir.exists():
        terminal.error(
            f"Directory '{project_name}' already exists",
            hint="choose a new project name or remove the existing directory",
        )
        raise typer.Exit(1)

    terminal.wordmark()
    terminal.blank()
    terminal.muted(f"creating {project_name}")
    terminal.blank()

    with Progress(
        SpinnerColumn(style="white"),
        TextColumn("[dim]{task.description}[/]"),
        transient=True,
    ) as progress:
        cloned = False
        if template:
            task = progress.add_task(
                description=f"cloning {variant} from {template}...", total=None
            )
            cloned = _clone_template(project_dir, template, variant)
            if not cloned:
                progress.update(
                    task,
                    description="template unavailable, using canonical scaffold...",
                )
        if not cloned:
            progress.add_task(description="scaffolding Voodoo app...", total=None)
            _scaffold_offline(project_dir, project_dir.name)
        if install:
            _install_project(project_dir, progress)

    terminal.blank()
    terminal.success("ready")
    terminal.next_steps([f"cd {project_name}", "voodoo dev"])
