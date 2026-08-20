import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from voodoo.cli import terminal

# ---------------------------------------------------------------------------
# Offline scaffold — used when no template repository is available.
# Showcases Voodoo CSS (the default adapter), folder-based routing, and the
# file-based `page(request)` convention. Keeps the surface minimal: routes
# only, no main.py / .env / infrastructure directories.
# ---------------------------------------------------------------------------

_HOME_PAGE = '''"""Home route — app/page.py maps to / via folder-based routing.

Voodoo CSS is the default style adapter: components emit semantic `vd-*`
classes (e.g. `vd-button vd-button--primary`) resolved by theme tokens, so
prefer semantic props (`variant`, `size`, `tone`) over utility classes.
"""
from voodoo import A, Badge, Button, Card, Flex, Grid, Heading, Page, Stack, Text
from voodoo.seo import SEO


def page(request):
    seo = SEO(
        title="My Voodoo App",
        description="Built with Voodoo: Python UI, semantic components, themeable tokens.",
    )
    ui = Page(
        Stack(
            Heading("Hello, Voodoo", level=1, size="xl"),
            Text(
                "Build your UI in Python. Voodoo CSS ships themed, semantic "
                "components out of the box.",
                tone="muted",
            ),
            Flex(
                Button("Get Started", variant="primary"),
                A(
                    "View about",
                    href="/about",
                    onClick="voodoo.navigate('/about')",
                ),
                direction="row",
                gap="sm",
            ),
            Grid(
                Card(
                    Stack(
                        Badge("Routing", variant="secondary"),
                        Heading("Folder-based routing", level=3),
                        Text("app/page.py → /", tone="muted"),
                        Text(
                            "Add app/about/page.py to create /about — no wiring.",
                            tone="muted",
                        ),
                        gap="sm",
                    ),
                ),
                Card(
                    Stack(
                        Badge("Theming", variant="secondary"),
                        Heading("Theme tokens", level=3),
                        Text(
                            "Components read --vd-* tokens; swap them to restyle everything.",
                            tone="muted",
                        ),
                        gap="sm",
                    ),
                ),
                Card(
                    Stack(
                        Badge("Layout", variant="secondary"),
                        Heading("Semantic layout", level=3),
                        Text(
                            "Stack, Flex, Grid and Page express layout — no utility classes.",
                            tone="muted",
                        ),
                        gap="sm",
                    ),
                ),
                cols="3",
                gap="md",
            ),
            gap="lg",
        )
    )
    return seo, ui
'''

_ABOUT_PAGE = '''"""About route — app/about/page.py maps to /about."""
from voodoo import Container, Heading, Page, Stack, Text
from voodoo.seo import SEO


def page(request):
    seo = SEO(title="About — My Voodoo App", description="About this project.")
    ui = Page(
        Container(
            Stack(
                Heading("About", level=1, size="xl"),
                Text("This route is defined by app/about/page.py.", tone="muted"),
                Text(
                    "Folder structure drives routing: app/about/page.py → /about.",
                    tone="muted",
                ),
                gap="md",
            )
        )
    )
    return seo, ui
'''

_USER_PAGE = '''"""User route — app/users/[id]/page.py maps to /users/{id}.

Bracket folders create dynamic segments; the `id: int` annotation coerces
the path segment to the declared type.
"""
from voodoo import Card, Heading, Page, Stack, Text
from voodoo.seo import SEO


def page(request, id: int):
    seo = SEO(title=f"User {id} — My Voodoo App")
    ui = Page(
        Card(
            Stack(
                Heading(f"User #{id}", level=2),
                Text(
                    "Dynamic segments use bracket folders: "
                    "app/users/[id]/page.py → /users/{id}.",
                    tone="muted",
                ),
                Text(
                    "The int annotation coerces the segment: '42' → 42.",
                    tone="muted",
                ),
                gap="md",
            )
        )
    )
    return seo, ui
'''


def _scaffold_offline(project_dir: Path, name: str) -> None:
    """Write the minimal default Voodoo project (Voodoo CSS + folder routing)."""
    (project_dir / "app").mkdir(parents=True, exist_ok=True)
    (project_dir / "app" / "page.py").write_text(_HOME_PAGE)

    about_dir = project_dir / "app" / "about"
    about_dir.mkdir(parents=True, exist_ok=True)
    (about_dir / "page.py").write_text(_ABOUT_PAGE)

    user_dir = project_dir / "app" / "users" / "[id]"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "page.py").write_text(_USER_PAGE)

    (project_dir / "voodoo.toml").write_text(
        f'[app]\nname = "{name}"\n'
        "# Voodoo CSS is the default style adapter.\n"
        "# To opt into Tailwind instead:\n"
        "#   from voodoo import TailwindAdapter, set_style_adapter\n"
        "#   set_style_adapter(TailwindAdapter())\n"
    )

    (project_dir / "pyproject.toml").write_text(
        f"[project]\n"
        f'name = "{name}"\n'
        f'version = "0.1.0"\n'
        f"dependencies = [\n"
        f'    "voodoo-framework"\n'
        f"]\n"
    )


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

            _scaffold_offline(project_dir, project_dir.name)

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
