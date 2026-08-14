"""Main dashboard and service status overview."""
from voodoo import Div, Heading, Card, ServiceStatus, _
from app.layout import Layout

async def page(request):
    content = Div(
        Div(
            ServiceStatus(className="mb-8"),
            Card(
                Heading(_("home.title"), level=2, className="text-xl font-semibold mb-4 text-[var(--color-text)]"),
                Div(
                    _("home.description"),
                    className="text-[var(--color-text-muted)]"
                ),
                className="bg-[var(--color-surface)] border-[var(--color-border)] backdrop-blur-md"
            ),
            className="space-y-6"
        )
    )
    return Layout(content, title=_("sidebar.dashboard"))
