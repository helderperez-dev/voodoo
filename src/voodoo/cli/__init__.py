import typer

from voodoo.cli import (
    ai,
    dev,
    doctor,
    executions,
    generate,
    new,
    objects,
    recover,
    routes,
    schedules,
    tasks,
    theme,
    version,
)
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
app.add_typer(tasks.tasks_app, name="tasks")
app.add_typer(schedules.schedules_app, name="schedules")
app.add_typer(executions.executions_app, name="executions")
app.add_typer(objects.objects_app, name="objects")
app.add_typer(theme.theme_app, name="theme")
# Top-level aliases per the Sprint 3 CLI surface: `voodoo execution <id>`
# (timeline from the journal) and `voodoo events` (recent journal events).
app.command("execution")(executions.show_execution)
app.command("events")(executions.list_events)
app.command()(version.version)
app.command()(doctor.doctor)
app.command()(routes.routes)
app.command()(recover.recover)
