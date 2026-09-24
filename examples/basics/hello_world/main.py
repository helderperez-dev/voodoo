"""Hello World — a minimal Voodoo app showing the default design system.

Run: python main.py  or  voodoo dev
"""

from voodoo import App, page
from voodoo.ui import Badge, Button, Card, Grid, Heading, Link, Page, Stack, Text

app = App()


@page("/")
def home():
    return Page(
        Stack(
            Heading("Hello, Voodoo", level=1),
            Text(
                "Zero-config design system: semantic components, theme tokens, "
                "and polished dark mode out of the box.",
                tone="muted",
            ),
            Stack(
                Button("Get started", variant="primary"),
                Button("Learn more", variant="secondary"),
                Link("Visit voodoo.build", href="https://voodoo.build"),
                gap="md",
            ),
            Grid(
                Card(Stack(Badge("Tokens"), Heading("--vd-*", level=3), gap="sm")),
                Card(
                    Stack(Badge("Layout"), Heading("Stack & Grid", level=3), gap="sm")
                ),
                Card(
                    Stack(
                        Badge("Theme"),
                        Heading("dark / light / system", level=3),
                        gap="sm",
                    )
                ),
                cols="3",
                gap="md",
            ),
            gap="lg",
        )
    )


if __name__ == "__main__":
    app.run()
