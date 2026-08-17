import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from voodoo.cli import terminal


def new(  # noqa: C901
    project_name: str,
    template: str = typer.Option(
        "helderperez-dev/voodoo-templates",
        "--template",
        "-t",
        help="GitHub repository URL or 'user/repo' to use as a template",
    ),
    variant: str = typer.Option(
        "default",
        "--variant",
        "-v",
        help="Specific template variant inside the repository",
    ),
):
    """
    Scaffold a new Voodoo project or clone a community template.
    """
    project_dir = Path(project_name)
    if project_dir.exists():
        terminal.error(f"Directory '{project_name}' already exists")
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
        if template:
            task = progress.add_task(
                description=f"cloning {variant} from {template}...",
                total=None,
            )

            if (
                template.startswith("http://")
                or template.startswith("https://")
                or template.startswith("git@")
                or template.startswith("/")
                or template.startswith("file://")
            ):
                repo_url = template
            elif len(template.split("/")) == 2:
                repo_url = f"https://github.com/{template}.git"
            else:
                terminal.error(
                    "Template must be a valid Git URL, local path, or 'user/repo'"
                )
                raise typer.Exit(1)

            fallback_to_offline = False

            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", repo_url, tmp_dir],
                        check=True,
                        capture_output=True,
                    )

                    variant_path = Path(tmp_dir) / variant

                    if not variant_path.exists() or not variant_path.is_dir():
                        if (
                            variant == "default"
                            and not (Path(tmp_dir) / "default").exists()
                        ):
                            variant_path = Path(tmp_dir)
                        else:
                            terminal.error(
                                f"Variant '{variant}' not found in template repository"
                            )
                            raise typer.Exit(1)

                    shutil.copytree(variant_path, project_dir, dirs_exist_ok=True)

            except subprocess.CalledProcessError:
                progress.update(
                    task, description="template unavailable, using minimal scaffold..."
                )
                fallback_to_offline = True

            if not fallback_to_offline:
                if (project_dir / ".git").exists():
                    shutil.rmtree(project_dir / ".git", ignore_errors=True)

        if not template or fallback_to_offline:
            progress.add_task(
                description="scaffolding project...",
                total=None,
            )

            # Minimal application: app/page.py only
            (project_dir / "app").mkdir(parents=True, exist_ok=True)

            (project_dir / "app" / "page.py").write_text(
                "from voodoo import page, Div, Heading, Text\n\n\n"
                '@page("/")\n'
                "def home():\n"
                "    return Div(\n"
                '        Heading("Hello, Voodoo", level=1),\n'
                '        Text("Build differently."),\n'
                "    )\n"
            )

            (project_dir / "voodoo.toml").write_text(
                f'[app]\nname = "{project_dir.name}"\n'
            )

            (project_dir / "pyproject.toml").write_text(
                f"[project]\n"
                f'name = "{project_dir.name}"\n'
                f'version = "0.1.0"\n'
                f"dependencies = [\n"
                f'    "voodoo-framework"\n'
                f"]\n"
            )

        # Set up local virtual environment and install dependencies
        if (project_dir / "pyproject.toml").exists():
            task = progress.add_task(
                description="setting up .venv...",
                total=None,
            )

            has_uv = shutil.which("uv") is not None
            try:
                if has_uv:
                    subprocess.run(
                        ["uv", "venv"], cwd=project_dir, check=True, capture_output=True
                    )
                    progress.update(task, description="installing dependencies...")
                    subprocess.run(
                        ["uv", "pip", "install", "-e", "."],
                        cwd=project_dir,
                        check=True,
                        capture_output=True,
                    )
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
                    subprocess.run(
                        [str(project_dir / pip_exe), "install", "-e", "."],
                        cwd=project_dir,
                        check=True,
                        capture_output=True,
                    )

                for item in project_dir.glob("*.egg-info"):
                    if item.is_dir():
                        shutil.rmtree(item)
            except subprocess.CalledProcessError as e:
                terminal.warning("Failed to set up environment or install dependencies")
                if e.stderr:
                    terminal.muted(e.stderr.decode().strip())

    terminal.blank()
    terminal.success("ready")
    terminal.next_steps([f"cd {project_name}", "voodoo dev"])
