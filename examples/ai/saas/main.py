"""AI SaaS demo using the current Voodoo happy path.

Actual local chain exercised by this example:

UI → Agent → Tool → Model → Mesh → Worker → Model

Tools decorated with ``@tool`` are also available to the MCP integration, but
MCP is a separate interoperability boundary and is not a fake step in this
local execution path.

Run: python examples/ai_saas/main.py  or  voodoo dev

This demo uses the mock provider (no network/API keys required).
"""

from voodoo import Agent, App, Model, page, state, task, tool
from voodoo.ui import Button, Card, Container, Div, Heading, Text
from voodoo.mesh import mesh

app = App()


class Lead(Model):
    name: str
    email: str
    status: str = "new"
    score: int = 0


@tool
async def create_lead(name: str, email: str) -> str:
    """Create a new lead and publish the resulting application event."""
    lead = await Lead.create(name=name, email=email)
    await mesh.emit("lead.created", {"id": lead.id, "name": name, "email": email})
    return f"Created lead #{lead.id}: {name}"


@tool
async def list_leads() -> str:
    """List all leads."""
    leads = await Lead.all()
    if not leads:
        return "No leads yet."
    return "\n".join(
        f"#{lead.id}: {lead.name} <{lead.email}> [{lead.status}]" for lead in leads
    )


notifications = state([])
status = state("Ready")
leads_display = state("No leads yet.")


@mesh.on("lead.created")
async def on_lead_created(payload):
    notifications.set(notifications.get() + [f"Lead created: {payload['name']}"])


@mesh.on("lead.created")
@task(retries=3, timeout=10)
async def score_lead(payload):
    import random

    score = random.randint(50, 100)
    lead = await Lead.get(payload["id"])
    if lead:
        lead.score = score
        lead.status = "scored"
        await lead.save()


agent = Agent(
    model="mock:test",
    tools=["create_lead", "list_leads"],
    system_prompt="You are a sales assistant. Use tools to create and list leads.",
)


async def ai_create() -> None:
    status.set("Running agent...")
    run = await agent.run("Create a lead for Ada Lovelace, ada@example.com")
    status.set(f"Done: {run.output}")
    leads_list = await Lead.all()
    leads_display.set(f"{len(leads_list)} leads")


async def ai_list() -> None:
    status.set("Listing leads...")
    leads_list = await Lead.all()
    if leads_list:
        leads_display.set(
            "\n".join(
                f"#{lead.id}: {lead.name} score={lead.score}" for lead in leads_list
            )
        )
    else:
        leads_display.set("No leads yet.")
    status.set("Ready")


@page("/")
def dashboard():
    return Container(
        Heading("AI SaaS Dashboard", level=1),
        Card(
            Heading("AI Agent", level=2),
            Text(f"Status: {status.get()}", id="status-text"),
            Button("Create Lead", on_click=ai_create),
            Button("List Leads", on_click=ai_list),
        ),
        Card(
            Heading("Leads", level=2),
            Text(leads_display.get(), id="leads-text"),
        ),
        Card(
            Heading("Notifications", level=2),
            Div(*[Text(n) for n in notifications.get()] or [Text("No notifications")]),
        ),
    )


if __name__ == "__main__":
    app.run()
