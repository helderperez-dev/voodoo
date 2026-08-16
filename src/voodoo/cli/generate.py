import asyncio
import os
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def generate(
    component: str = typer.Argument(
        ..., help="Component type (e.g., agent, resource, tool)"
    ),
    description: str = typer.Argument(..., help="What should the AI generate?"),
):
    """
    AI-powered generation of Voodoo components using LLMs.
    """
    from openai import AsyncOpenAI

    # Check for API keys (support OpenRouter or OpenAI)
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = (
        "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None
    )

    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] Neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set in the environment."
        )
        raise typer.Exit(1)

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    model = "openai/gpt-4o" if base_url else "gpt-4o"

    async def _generate():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(
                description=f"AI is thinking about your [bold magenta]{component}[/bold magenta]...",
                total=None,
            )

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
                    temperature=0.2,
                )

                raw_content = response.choices[0].message.content
                code = (raw_content or "").strip()
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
                raise typer.Exit(1) from None

    # Run async function
    code = asyncio.run(_generate())

    # Save the file
    filename = f"{component}_{int(time.time())}.py"
    Path(filename).write_text(code + "\n")

    console.print(f"[bold green]✓ Generated {component} successfully![/bold green]")
    console.print(f"Saved to: [bold cyan]{filename}[/bold cyan]")

    # Show preview
    console.print(Panel(code, title=f"Preview: {filename}", border_style="green"))
