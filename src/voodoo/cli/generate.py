import asyncio
import os
import time
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from voodoo.cli import terminal


def generate(
    component: str = typer.Argument(
        ..., help="Component type (e.g., agent, resource, tool)"
    ),
    description: str = typer.Argument(..., help="What should the AI generate?"),
):
    """
    AI-powered generation of Voodoo components using LLMs.
    """
    from voodoo.ai.providers import get_provider

    # Check for API keys (support OpenRouter or OpenAI)
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = (
        "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None
    )

    if not api_key:
        terminal.error(
            "Neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set",
            hint="set an API key in your environment",
        )
        raise typer.Exit(1)

    # Resolve through the provider abstraction (no direct SDK use). For
    # OpenRouter the model id keeps the provider's ``vendor/model`` slug.
    model = os.getenv("VOODOO_MODELS_DEFAULT")
    if not model:
        model = "openai:openai/gpt-4o" if base_url else "openai:gpt-4o"
    provider = get_provider(model, api_key=api_key, base_url=base_url)

    terminal.wordmark()
    terminal.blank()
    terminal.muted(f"generating {component}")
    terminal.muted(description)
    terminal.blank()

    async def _generate():
        with Progress(
            SpinnerColumn(style="white"),
            TextColumn("[dim]{task.description}[/]"),
            transient=True,
        ) as progress:
            progress.add_task(
                description="thinking...",
                total=None,
            )

            prompt = f"""
            You are an expert Voodoo Framework developer. Voodoo is a modern Python framework built on Starlette and Pydantic.
            Generate a Voodoo `{component}` based on this description: "{description}".

            Only output the raw Python code. Do not include markdown code blocks (no ```python).
            Do not include explanations. Just the raw code.
            """

            try:
                response = await provider.complete(
                    [{"role": "user", "content": prompt}], temperature=0.2
                )

                code = (response.content or "").strip()
                if code.startswith("```python"):
                    code = code[9:]
                if code.startswith("```"):
                    code = code[3:]
                if code.endswith("```"):
                    code = code[:-3]

                return code.strip()

            except Exception as e:
                terminal.error(f"Failed to generate code: {e}")
                raise typer.Exit(1) from None

    code = asyncio.run(_generate())

    filename = f"{component}_{int(time.time())}.py"
    Path(filename).write_text(code + "\n")

    terminal.success("ready")
    terminal.muted(f"saved to {filename}")
    terminal.blank()
