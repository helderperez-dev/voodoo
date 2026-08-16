import typer

from voodoo.cli import dev, doctor, generate, new, routes, version
from voodoo.cli.auth import auth_app
from voodoo.cli.scaffolding import _detect_ide as _detect_ide
from voodoo.cli.scaffolding import _sync_ai_assets as _sync_ai_assets

# We initialize the Typer app
app = typer.Typer(
    help="🔮 Voodoo Framework CLI - Fast, Animated, AI-Powered",
    no_args_is_help=True,
    add_completion=False,
)

app.command()(new.new)
app.command()(dev.dev)
app.command()(generate.generate)
app.add_typer(auth_app, name="auth")
app.command()(version.version)
app.command()(doctor.doctor)
app.command()(routes.routes)
