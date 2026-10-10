"""About route — app/about/page.py maps to /about."""

from voodoo.seo import SEO
from voodoo.ui import Container, Heading, Page, Stack, Text


def page(request: object) -> tuple[SEO, object]:
    seo = SEO(title="About — {{ project_name }}", description="About this project.")
    ui = Page(
        Container(
            Stack(
                Heading("About", level=1, size="xl"),
                Text("This route is defined by app/about/page.py.", tone="muted"),
                Text(
                    "Folder structure drives routing: app/about/page.py → /about.",
                    tone="muted",
                ),
                gap="md",
            )
        )
    )
    return seo, ui
