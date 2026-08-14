import os
import sys
import time
import asyncio
from pathlib import Path

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

@app.command()
def new(project_name: str):
    """
    Scaffold a new Voodoo project.
    """
    console.print(Panel.fit(f"Creating new Voodoo project: [bold cyan]{project_name}[/bold cyan]", border_style="cyan"))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(description="Scaffolding project structure...", total=None)
        
        # Simulate quick but visible animation
        time.sleep(0.5)
        
        project_dir = Path(project_name)
        if project_dir.exists():
            console.print(f"[bold red]Error:[/bold red] Directory '{project_name}' already exists.")
            raise typer.Exit(1)
            
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
        
        (project_dir / "app" / "main.py").write_text("""from voodoo import VoodooApp

app = VoodooApp()

@app.get("/")
async def index():
    return {"message": "Welcome to Voodoo!"}
""")
    
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
    
    # We use a subprocess to run uvicorn
    import subprocess
    
    try:
        # We let uvicorn take over the terminal output
        subprocess.run(["uvicorn", app_str, "--reload", "--port", str(port)])
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
