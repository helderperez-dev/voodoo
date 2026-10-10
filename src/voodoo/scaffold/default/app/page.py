"""Home route — app/page.py maps to /."""

from voodoo.seo import SEO
from voodoo.ui import A, Badge, Button, Card, Flex, Grid, Heading, Page, Stack, Text


def page(request: object) -> tuple[SEO, object]:
    seo = SEO(
        title="{{ project_name }}",
        description=(
            "Built with Voodoo: Python UI, semantic components, and themeable tokens."
        ),
    )
    ui = Page(
        Stack(
            Heading("Hello, Voodoo", level=1, size="xl"),
            Text(
                "Build your UI in Python with semantic, themeable components.",
                tone="muted",
            ),
            Flex(
                Button("Get Started", variant="primary"),
                A("View about", href="/about"),
                direction="row",
                gap="sm",
            ),
            Grid(
                Card(
                    Stack(
                        Badge("Routing", variant="secondary"),
                        Heading("Folder-based routing", level=3),
                        Text("app/page.py → /", tone="muted"),
                        gap="sm",
                    )
                ),
                Card(
                    Stack(
                        Badge("Theming", variant="secondary"),
                        Heading("Theme tokens", level=3),
                        Text("Components read --vd-* tokens.", tone="muted"),
                        gap="sm",
                    )
                ),
                Card(
                    Stack(
                        Badge("Layout", variant="secondary"),
                        Heading("Semantic layout", level=3),
                        Text(
                            "Stack, Flex, Grid, and Page express layout.", tone="muted"
                        ),
                        gap="sm",
                    )
                ),
                cols="3",
                gap="md",
            ),
            gap="lg",
        )
    )
    return seo, ui
