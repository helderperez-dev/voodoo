"""Dynamic user route — app/users/[id]/page.py maps to /users/{id}."""

from voodoo.seo import SEO
from voodoo.ui import Card, Heading, Page, Stack, Text


def page(request: object, id: int) -> tuple[SEO, object]:
    seo = SEO(title=f"User {id} — " + "{{ project_name }}")
    ui = Page(
        Card(
            Stack(
                Heading(f"User #{id}", level=2),
                Text(
                    "Bracket folders create dynamic segments: /users/{id}.",
                    tone="muted",
                ),
                Text(
                    "The int annotation coerces the segment to an integer.",
                    tone="muted",
                ),
                gap="md",
            )
        )
    )
    return seo, ui
