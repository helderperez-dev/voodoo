import platform

from rich.console import Console

from voodoo import __version__

console = Console()


def version():
    """
    Show Voodoo Framework version and environment info.
    """
    console.print(f"[bold magenta]🔮 Voodoo Framework[/bold magenta] v{__version__}")
    console.print(
        f"  • Python: [cyan]{platform.python_version()}[/cyan] ({platform.python_implementation()})"
    )
    console.print(f"  • Platform: [dim]{platform.platform()}[/dim]")
