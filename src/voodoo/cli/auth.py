import asyncio

import typer
from rich.console import Console
from rich.panel import Panel

# =========================================================================
# Auth CLI Subcommands
# =========================================================================

auth_app = typer.Typer(
    help="🔒 Authentication & Security tools (users, API keys, password hashing, secrets)",
    no_args_is_help=True,
)

console = Console()


@auth_app.command("secret-key")
def cli_secret_key(
    length: int = typer.Option(
        32, "--length", "-l", help="Length of the secret key in bytes"
    ),
):
    """
    Generate a cryptographically secure secret key for VOODOO_SECRET_KEY.
    """
    from voodoo.auth import generate_secret_key

    key = generate_secret_key(length)
    console.print(
        Panel(
            f"[bold green]{key}[/bold green]\n\n[dim]Add this to your .env file:[/dim]\n[cyan]VOODOO_SECRET_KEY={key}[/cyan]",
            title="🔑 Generated Secret Key",
            border_style="green",
        )
    )


@auth_app.command("hash-password")
def cli_hash_password(
    password: str = typer.Argument(..., help="Plaintext password to hash"),
):
    """
    Generate a PBKDF2-HMAC-SHA256 hash for a given password.
    """
    from voodoo.auth import hash_password

    hashed = hash_password(password)
    console.print(
        Panel(
            f"[bold cyan]{hashed}[/bold cyan]",
            title="🔒 Password Hash (PBKDF2-SHA256)",
            border_style="cyan",
        )
    )


@auth_app.command("generate-key")
def cli_generate_key(
    prefix: str = typer.Option(
        "vd_live", "--prefix", "-p", help="API key prefix (e.g. vd_live, vd_test)"
    ),
):
    """
    Generate a new API key and its SHA-256 hash.
    """
    from voodoo.auth import generate_api_key

    raw_key, key_hash = generate_api_key(prefix)
    console.print(
        Panel(
            f"[bold green]API Key (keep secret):[/bold green]\n[cyan]{raw_key}[/cyan]\n\n"
            f"[bold yellow]SHA-256 Hash (stored in DB):[/bold yellow]\n[dim]{key_hash}[/dim]",
            title="🔑 Generated API Key",
            border_style="green",
        )
    )


@auth_app.command("create-user")
def cli_create_user(
    email: str = typer.Option(
        ..., "--email", "-e", prompt=True, help="User email address"
    ),
    password: str = typer.Option(
        ..., "--password", "-p", prompt=True, hide_input=True, help="User password"
    ),
    username: str = typer.Option(
        None, "--username", "-u", help="Username (defaults to email prefix)"
    ),
    role: str = typer.Option(
        "user", "--role", "-r", help="User role (e.g. user, admin, editor)"
    ),
):
    """
    Create a new user directly in the database.
    """
    from voodoo.auth import User
    from voodoo.security import validate_password_strength

    is_valid, err = validate_password_strength(password)
    if not is_valid:
        console.print(f"[bold red]Error:[/bold red] {err}")
        raise typer.Exit(1)

    async def _create():
        user, raw_key = await User.create_user(
            email=email, password=password, username=username, role=role
        )
        return user, raw_key

    user, raw_key = asyncio.run(_create())
    console.print(
        Panel(
            f"[bold green]User created successfully![/bold green]\n\n"
            f"• [bold]ID:[/bold] {user.id}\n"
            f"• [bold]Email:[/bold] {user.email}\n"
            f"• [bold]Username:[/bold] {user.username}\n"
            f"• [bold]Role:[/bold] {user.role}\n"
            f"• [bold]API Key:[/bold] [cyan]{raw_key}[/cyan]\n",
            title="👤 New User",
            border_style="green",
        )
    )
