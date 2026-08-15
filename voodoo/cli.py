import os
import sys
import time
import asyncio
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from textwrap import dedent

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.markdown import Markdown

# We initialize the Typer app
app = typer.Typer(
    help="🔮 Voodoo Framework CLI - Fast, Animated, AI-Powered",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

AI_DOCS_BASE_URL = "https://raw.githubusercontent.com/helderperez-dev/voodoo/main/docs/ai"
AI_TRAE_SKILL_URL = "https://raw.githubusercontent.com/helderperez-dev/voodoo/main/.trae/skills/voodoo-builder/SKILL.md"


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fetch_text(url: str, timeout: int = 3) -> str | None:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except Exception:
        return None


def _build_workspace_rules() -> str:
    return dedent(
        """
        # Voodoo AI Workspace

        This project uses the Voodoo Framework.

        Start by reading these local files in order:
        1. `.voodoo/ai/README.md`
        2. `.voodoo/ai/RULES.md`
        3. `.voodoo/ai/ARCHITECTURE.md`
        4. `.voodoo/ai/ROUTING.md`
        5. `.voodoo/ai/COMPONENTS.md`
        6. `.voodoo/ai/STATE.md`
        7. `.voodoo/ai/DATABASE.md`
        8. `.voodoo/ai/SKILLS.md`

        Core rules:
        - Use `voodoo.components` instead of raw HTML templates.
        - Prefer `async def` for handlers, I/O, and database work.
        - Use Voodoo's `A` component plus `voodoo.navigate()` for internal links.
        - Keep app code in `app/` and data in `.data/`.
        - Use `aiosqlite` with `.data/voodoo.db` by default.
        - Preserve the large-cookie websocket settings in `main.py` and `voodoo dev`.

        If Trae skills are available, use `.trae/skills/voodoo-builder/SKILL.md`.
        """
    ).strip() + "\n"


def _build_cursor_rules() -> str:
    return (
        "---\n"
        "description: Voodoo framework guidance for Cursor.\n"
        "globs:\n"
        '  - "**/*.py"\n'
        '  - "**/*.md"\n'
        "alwaysApply: true\n"
        "---\n\n"
        + _build_workspace_rules()
    )


def _fallback_ai_assets() -> dict[str, str]:
    return {
        ".voodoo/ai/README.md": dedent(
            """
            # Voodoo AI Kit

            This folder gives AI IDEs high-context guidance for building serious Voodoo applications.

            Read these files in order:
            1. `RULES.md`
            2. `ARCHITECTURE.md`
            3. `ROUTING.md`
            4. `COMPONENTS.md`
            5. `STATE.md`
            6. `DATABASE.md`
            7. `SKILLS.md`

            Recommended behavior:
            - Treat Voodoo as a Python-first UI framework.
            - Prefer simple, composable route files and reusable components.
            - Respect Voodoo navigation, websocket, and data conventions.
            """
        ).strip() + "\n",
        ".voodoo/ai/RULES.md": dedent(
            """
            # Voodoo Rules

            - Build UI with `voodoo.components`.
            - Prefer `async def` for handlers and I/O.
            - Use Tailwind via `className`.
            - Use `A(..., href=..., onClick="voodoo.navigate('...')")` for internal links.
            - Keep route files inside `app/`.
            - Keep persistent data inside `.data/`.
            - Use `aiosqlite` and `.data/voodoo.db` by default.
            - Preserve `WEBSOCKETS_MAX_LINE_LENGTH="8388608"` and `http="h11"` when working with websocket-heavy apps.
            """
        ).strip() + "\n",
        ".voodoo/ai/ARCHITECTURE.md": dedent(
            """
            # Voodoo Architecture

            Voodoo is a Starlette-based framework with Python-defined UI and file-based routing.

            Main conventions:
            - `app/` contains routes and app-facing code.
            - `main.py` boots the app with `create_app()`.
            - `voodoo.components` is the primary UI surface.
            - Internal framework API routes remain mounted automatically.
            """
        ).strip() + "\n",
        ".voodoo/ai/ROUTING.md": dedent(
            """
            # Voodoo Routing

            - `app/page.py` maps to `/`
            - Nested `page.py` files map to nested routes
            - Dynamic segments use bracket folders such as `app/users/[id]/page.py`

            Internal links must use Voodoo navigation:

            ```python
            from voodoo.components import A

            A("Dashboard", href="/dashboard", onClick="voodoo.navigate('/dashboard')")
            ```
            """
        ).strip() + "\n",
        ".voodoo/ai/COMPONENTS.md": dedent(
            """
            # Voodoo Components

            Import UI primitives from `voodoo.components`.

            Common components:
            - `Div`
            - `Text`
            - `Heading`
            - `Button`
            - `A`
            - `Input`
            - `Form`

            Use `className` for styling and favor small reusable Python functions for custom components.
            """
        ).strip() + "\n",
        ".voodoo/ai/STATE.md": dedent(
            """
            # Voodoo State

            Voodoo does not use React-style client state hooks.

            Preferred patterns:
            - Form posts for mutations
            - Async route handlers for derived UI
            - Database-backed state for persistence
            - WebSockets only when real-time behavior is truly needed
            """
        ).strip() + "\n",
        ".voodoo/ai/DATABASE.md": dedent(
            """
            # Voodoo Database

            Default stack:
            - `aiosqlite`
            - database path: `.data/voodoo.db`

            Example:

            ```python
            import aiosqlite

            async with aiosqlite.connect(".data/voodoo.db") as db:
                await db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)")
                await db.commit()
            ```
            """
        ).strip() + "\n",
        ".voodoo/ai/SKILLS.md": dedent(
            """
            # Voodoo AI Skills

            ## Scaffold a Route
            - Create the correct `app/.../page.py` file
            - Export `page(request, ...)`
            - Return `voodoo.components`

            ## Create a Component
            - Build a reusable Python function
            - Accept meaningful arguments
            - Style through `className`

            ## Add Data
            - Use `aiosqlite`
            - Store the database in `.data/voodoo.db`
            - Keep queries async

            ## Debug Navigation
            - Check file-based route placement
            - Check `A` + `voodoo.navigate()`

            ## Debug Cookies / WebSockets
            - Check `WEBSOCKETS_MAX_LINE_LENGTH`
            - Check `http="h11"`
            """
        ).strip() + "\n",
        ".trae/skills/voodoo-builder/SKILL.md": dedent(
            """
            ---
            name: "voodoo-builder"
            description: "Builds and refactors Voodoo apps. Invoke when creating routes, components, data flows, or debugging Voodoo-specific behavior."
            ---

            # Voodoo Builder

            Use this skill when working on Voodoo Framework applications.

            Read these local files before making major changes:
            1. `.voodoo/ai/README.md`
            2. `.voodoo/ai/RULES.md`
            3. `.voodoo/ai/ARCHITECTURE.md`
            4. `.voodoo/ai/ROUTING.md`
            5. `.voodoo/ai/COMPONENTS.md`
            6. `.voodoo/ai/STATE.md`
            7. `.voodoo/ai/DATABASE.md`
            8. `.voodoo/ai/SKILLS.md`

            Follow these Voodoo rules:
            - Build UI with `voodoo.components`
            - Prefer `async def`
            - Use `A` plus `voodoo.navigate()` for internal links
            - Keep data in `.data/`
            - Use `aiosqlite` by default
            - Preserve websocket large-cookie configuration
            """
        ).lstrip(),
    }


def _sync_ai_assets(project_dir: Path, progress: Progress) -> None:
    task = progress.add_task(description="Setting up Voodoo AI assets...", total=None)
    time.sleep(0.2)

    fallback_assets = _fallback_ai_assets()
    remote_assets = {
        ".voodoo/ai/README.md": f"{AI_DOCS_BASE_URL}/README.md",
        ".voodoo/ai/RULES.md": f"{AI_DOCS_BASE_URL}/RULES.md",
        ".voodoo/ai/ARCHITECTURE.md": f"{AI_DOCS_BASE_URL}/ARCHITECTURE.md",
        ".voodoo/ai/ROUTING.md": f"{AI_DOCS_BASE_URL}/ROUTING.md",
        ".voodoo/ai/COMPONENTS.md": f"{AI_DOCS_BASE_URL}/COMPONENTS.md",
        ".voodoo/ai/STATE.md": f"{AI_DOCS_BASE_URL}/STATE.md",
        ".voodoo/ai/DATABASE.md": f"{AI_DOCS_BASE_URL}/DATABASE.md",
        ".voodoo/ai/SKILLS.md": f"{AI_DOCS_BASE_URL}/SKILLS.md",
        ".trae/skills/voodoo-builder/SKILL.md": AI_TRAE_SKILL_URL,
    }

    for relative_path, url in remote_assets.items():
        target = project_dir / relative_path
        if target.exists():
            continue
        content = _fetch_text(url, timeout=3) or fallback_assets[relative_path]
        _write_text_file(target, content)

    ide_rules = {
        ".trae/rules": _build_workspace_rules(),
        ".windsurfrules": _build_workspace_rules(),
        ".cursor/rules/voodoo.mdc": _build_cursor_rules(),
    }

    for relative_path, content in ide_rules.items():
        target = project_dir / relative_path
        if target.exists():
            continue
        _write_text_file(target, content)

@app.command()
def new(
    project_name: str,
    template: str = typer.Option("helderperez-dev/voodoo-templates", "--template", "-t", help="GitHub repository URL or 'user/repo' to use as a template"),
    variant: str = typer.Option("default", "--variant", "-v", help="Specific template variant inside the repository"),
):
    """
    Scaffold a new Voodoo project or clone a community template.
    """
    console.print(Panel.fit(f"Creating new Voodoo project: [bold cyan]{project_name}[/bold cyan]", border_style="cyan"))
    
    project_dir = Path(project_name)
    if project_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Directory '{project_name}' already exists.")
        raise typer.Exit(1)
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        if template:
            task = progress.add_task(description=f"Cloning [cyan]{variant}[/cyan] template from [cyan]{template}[/cyan]...", total=None)
            
            # Resolve URL
            if template.startswith("http://") or template.startswith("https://") or template.startswith("git@") or template.startswith("/") or template.startswith("file://"):
                repo_url = template
            elif len(template.split("/")) == 2:
                repo_url = f"https://github.com/{template}.git"
            else:
                console.print("\n[bold red]Error:[/bold red] Template must be a valid Git URL, local path, or 'user/repo'.")
                raise typer.Exit(1)
                
            fallback_to_offline = False
            
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", repo_url, tmp_dir],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    
                    variant_path = Path(tmp_dir) / variant
                    
                    if not variant_path.exists() or not variant_path.is_dir():
                        # If variant doesn't exist, check if the repo root itself is the template
                        if variant == "default" and not (Path(tmp_dir) / "default").exists():
                            variant_path = Path(tmp_dir)
                        else:
                            console.print(f"\n[bold red]Error:[/bold red] Variant '{variant}' not found in template repository.")
                            raise typer.Exit(1)
                            
                    # Copy the template files over to the project directory
                    shutil.copytree(variant_path, project_dir, dirs_exist_ok=True)
                    
            except subprocess.CalledProcessError as e:
                console.print(f"\n[bold yellow]Warning:[/bold yellow] Failed to clone template from {repo_url}")
                console.print("[yellow]Falling back to offline default scaffolding...[/yellow]")
                fallback_to_offline = True
            
            if not fallback_to_offline:
                # Remove the .git folder so the user starts with a clean slate
                if (project_dir / ".git").exists():
                    shutil.rmtree(project_dir / ".git", ignore_errors=True)
                
                if not (project_dir / ".data").exists():
                    os.makedirs(project_dir / ".data", exist_ok=True)
                    
        if not template or fallback_to_offline:
            task = progress.add_task(description="Scaffolding offline project structure...", total=None)
            
            # Simulate quick but visible animation
            time.sleep(0.5)
            
            os.makedirs(project_dir)
            os.makedirs(project_dir / "app")
            os.makedirs(project_dir / ".data")
            
            progress.update(task, description="Writing base configuration...")
            time.sleep(0.5)
            
            (project_dir / ".env").write_text("VOODOO_DB_PATH=.data/voodoo.db\n")
            (project_dir / "pyproject.toml").write_text(f"""[project]
name = "{project_name}"
version = "0.1.0"
dependencies = [
    "voodoo-framework"
]
""")
            
            progress.update(task, description="Generating entry point...")
            time.sleep(0.5)
            
            (project_dir / "app" / "page.py").write_text("""from voodoo.components import Div, Heading, Text

def page(request):
    \"\"\"
    A minimal single-page application.
    Voodoo's router will automatically map app/page.py to the root "/" route.
    \"\"\"
    return Div(
        Heading("Hello, Voodoo! 🪄", level=1, className="text-5xl font-bold text-center mt-32 tracking-tight"),
        Div(Text("Welcome to your new Voodoo app."), className="text-center text-[var(--color-text-muted)] mt-6 text-lg"),
        className="min-h-screen bg-[var(--color-background)] text-[var(--color-text)]"
    )
""")

            (project_dir / "main.py").write_text("""import os
import uvicorn
from voodoo.core import create_app
from voodoo.config import config

# Fix for large cookies in WebSockets
os.environ["WEBSOCKETS_MAX_LINE_LENGTH"] = "8388608"

# Voodoo automatically looks for the "app" folder in the current working directory
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=config.host, 
        port=config.port, 
        reload=True, 
        ws_max_size=16777216, 
        ws_max_queue=32,
        http="h11",
        ws="auto",
        h11_max_incomplete_event_size=5242880
    )
""")

        _sync_ai_assets(project_dir, progress)

        # Set up local virtual environment and install dependencies
        if (project_dir / "pyproject.toml").exists():
            task = progress.add_task(description="Setting up local virtual environment (.venv)...", total=None)
            has_uv = shutil.which("uv") is not None
            try:
                if has_uv:
                    subprocess.run(["uv", "venv"], cwd=project_dir, check=True, capture_output=True)
                    progress.update(task, description="Installing dependencies with uv...")
                    subprocess.run(["uv", "pip", "install", "-e", "."], cwd=project_dir, check=True, capture_output=True)
                else:
                    subprocess.run([sys.executable, "-m", "venv", ".venv"], cwd=project_dir, check=True, capture_output=True)
                    progress.update(task, description="Installing dependencies with pip...")
                    pip_exe = ".venv/bin/pip" if os.name != "nt" else ".venv\\Scripts\\pip.exe"
                    subprocess.run([str(project_dir / pip_exe), "install", "-e", "."], cwd=project_dir, check=True, capture_output=True)
                    
                # Clean up build artifacts created by pip/uv install -e .
                for item in project_dir.glob("*.egg-info"):
                    if item.is_dir():
                        shutil.rmtree(item)
            except subprocess.CalledProcessError as e:
                console.print(f"\n[bold yellow]Warning:[/bold yellow] Failed to set up local environment or install dependencies.")
                if e.stderr:
                    console.print(f"[dim]{e.stderr.decode()}[/dim]")
    
    console.print("[bold green]✓ Project scaffolded successfully![/bold green]")
    console.print(f"\nNext steps:\n  [cyan]cd {project_name}[/cyan]\n  [cyan]voodoo dev[/cyan]\n")

@app.command()
def dev(
    app_str: str = typer.Argument("main:app", help="App instance to run (e.g., main:app)"),
    port: int = typer.Option(8000, help="Port to run the server on"),
):
    """
    Start the Voodoo development server.
    """
    module_name = app_str.split(":")[0]
    module_path = Path(module_name.replace(".", "/") + ".py")
    module_dir = Path(module_name.replace(".", "/"))

    if not module_path.exists() and not (module_dir.is_dir() and (module_dir / "__init__.py").exists()):
        console.print(f"\n[bold red]Error:[/bold red] Could not find module [yellow]{module_name}[/yellow].")
        console.print("Are you sure you are inside a Voodoo project directory?")
        console.print("To start a new project, run: [bold cyan]voodoo new <project_name>[/bold cyan]\n")
        raise typer.Exit(1)

    console.print(Panel.fit(f"Starting Voodoo Server on port [bold yellow]{port}[/bold yellow]", border_style="yellow"))
    
    # We use a subprocess to run uvicorn through the current python executable
    # to ensure we don't accidentally pick up a global system uvicorn that lacks the voodoo package
    import subprocess
    import sys
    import os
    
    local_venv_python = Path(".venv/bin/python") if os.name != "nt" else Path(".venv/Scripts/python.exe")
    
    if local_venv_python.exists():
        python_exe = str(local_venv_python.absolute())
        console.print("[dim]Using local virtual environment.[/dim]")
    else:
        python_exe = sys.executable
        console.print("[dim]Using global environment.[/dim]")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["WEBSOCKETS_MAX_LINE_LENGTH"] = "8388608" # 8 MB to match uvicorn's h11 setting
    env["WEBSOCKETS_MAX_NUM_HEADERS"] = "256"
    
    try:
        # We let uvicorn take over the terminal output
        subprocess.run(
            [python_exe, "-m", "uvicorn", app_str, "--reload", "--port", str(port), "--http", "h11", "--ws", "auto", "--h11-max-incomplete-event-size", "5242880"],
            env=env
        )
    except KeyboardInterrupt:
        console.print("\n[bold red]Server stopped.[/bold red]")

@app.command()
def generate(
    component: str = typer.Argument(..., help="Component type (e.g., agent, resource, tool)"),
    description: str = typer.Argument(..., help="What should the AI generate?"),
):
    """
    AI-powered generation of Voodoo components using LLMs.
    """
    from openai import AsyncOpenAI
    
    # Check for API keys (support OpenRouter or OpenAI)
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None
    
    if not api_key:
        console.print("[bold red]Error:[/bold red] Neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set in the environment.")
        raise typer.Exit(1)
        
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    model = "openai/gpt-4o" if base_url else "gpt-4o"
    
    async def _generate():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description=f"AI is thinking about your [bold magenta]{component}[/bold magenta]...", total=None)
            
            prompt = f"""
            You are an expert Voodoo Framework developer. Voodoo is a modern Python framework built on Starlette and Pydantic.
            Generate a Voodoo `{component}` based on this description: "{description}".
            
            Only output the raw Python code. Do not include markdown code blocks (no ```python).
            Do not include explanations. Just the raw code.
            """
            
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )
                
                code = response.choices[0].message.content.strip()
                # Clean up if the model accidentally included markdown blocks
                if code.startswith("```python"):
                    code = code[9:]
                if code.startswith("```"):
                    code = code[3:]
                if code.endswith("```"):
                    code = code[:-3]
                    
                return code.strip()
                
            except Exception as e:
                console.print(f"[bold red]Failed to generate code:[/bold red] {e}")
                raise typer.Exit(1)
                
    # Run async function
    code = asyncio.run(_generate())
    
    # Save the file
    filename = f"{component}_{int(time.time())}.py"
    Path(filename).write_text(code + "\n")
    
    console.print(f"[bold green]✓ Generated {component} successfully![/bold green]")
    console.print(f"Saved to: [bold cyan]{filename}[/bold cyan]")
    
    # Show preview
    console.print(Panel(code, title=f"Preview: {filename}", border_style="green"))

if __name__ == "__main__":
    app()
