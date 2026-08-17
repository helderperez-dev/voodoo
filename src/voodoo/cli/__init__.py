import typer

from voodoo.cli import ai, dev, doctor, generate, new, recover, routes, version
from voodoo.cli.auth import auth_app
from voodoo.cli.inspect import inspect_app

app = typer.Typer(
    name="voodoo",
    help="build systems, not glue.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

app.command()(new.new)
app.command()(dev.dev)
app.command()(generate.generate)
app.add_typer(auth_app, name="auth")
app.add_typer(ai.ai_app, name="ai")
app.add_typer(inspect_app, name="inspect")
app.command()(version.version)
app.command()(doctor.doctor)
app.command()(routes.routes)
app.command()(recover.recover)
