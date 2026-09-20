"""Data Dashboard — a minimal dashboard with a data table.

Run: python main.py  or  voodoo dev
"""

from voodoo import App, Card, Container, Grid, Heading, Model, Text, page, state

app = App()

stats = state({"visitors": 1247, "revenue": 45890, "conversion": 3.2})


class Sale(Model):
    product: str
    amount: float
    status: str = "completed"


@page("/")
async def dashboard():
    sales = await Sale.all()
    return Container(
        Heading("Dashboard", level=1),
        Grid(
            Card(
                Heading("Visitors", level=3),
                Heading(str(stats.get()["visitors"]), level=2),
            ),
            Card(
                Heading("Revenue", level=3),
                Heading(f"${stats.get()['revenue']:,}", level=2),
            ),
            Card(
                Heading("Conversion", level=3),
                Heading(f"{stats.get()['conversion']}%", level=2),
            ),
        ),
        Heading("Recent Sales", level=2),
        Card(
            *[f"{s.product}: ${s.amount} ({s.status})" for s in sales]
            or [Text("No sales yet")],
        ),
    )


if __name__ == "__main__":
    app.run()
