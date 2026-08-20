"""Hello World — a minimal Voodoo app showing the default design system.

Run: python main.py  or  voodoo dev
"""

from voodoo import App, Badge, Button, Card, Grid, Heading, Page, Stack, Text, page

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
            Button("Get started", variant="primary"),
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
