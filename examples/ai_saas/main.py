"""AI SaaS Demo — the killer example exercising the full chain.

UI → mesh → agent → tool → MCP → worker → db → telemetry

Run: python main.py  or  voodoo dev

This demo uses the mock provider (no network/API keys required).
"""

from voodoo import (
    Agent,
    App,
    Button,
    Card,
    Container,
    Div,
    Heading,
    Model,
    Text,
    event,
    page,
    state,
    tool,
)
from voodoo.mesh import mesh
from voodoo.workers import task

app = App()

# ---------------------------------------------------------------------------
# 1. Data model (db layer)
# ---------------------------------------------------------------------------


class Lead(Model):
    name: str
    email: str
    status: str = "new"
    score: int = 0


# ---------------------------------------------------------------------------
# 2. Tool — one definition, four consumers: Python, agent, MCP, mesh
# ---------------------------------------------------------------------------


@tool
async def create_lead(name: str, email: str) -> str:
    """Create a new lead in the database."""
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


# ---------------------------------------------------------------------------
# 3. Mesh events — realtime layer
# ---------------------------------------------------------------------------

notifications = state([])


@mesh.on("lead.created")
async def on_lead_created(payload):
    notifications.set(notifications.get() + [f"Lead created: {payload['name']}"])


# ---------------------------------------------------------------------------
# 4. Workers — background processing with telemetry
# ---------------------------------------------------------------------------


@mesh.on("lead.created")
@task(retries=3, timeout=10)
async def score_lead(payload):
    # Simulate lead scoring
    import random

    score = random.randint(50, 100)
    lead = await Lead.get(payload["id"])
    if lead:
        lead.score = score
        lead.status = "scored"
        await lead.save()


# ---------------------------------------------------------------------------
# 5. Agent — AI layer with tool calling (mock provider, no network)
# ---------------------------------------------------------------------------

agent = Agent(
    model="mock:test",
    tools=["create_lead", "list_leads"],
    system_prompt="You are a sales assistant. Use tools to create and list leads.",
)

# ---------------------------------------------------------------------------
# 6. MCP — tools are auto-exposed via the MCP server
#    (happens automatically when @tool is used)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 7. UI — reactive state + events + telemetry
# ---------------------------------------------------------------------------

status = state("Ready")
leads_display = state("No leads yet.")


@page("/")
def dashboard():
    return Container(
        Heading("AI SaaS Dashboard", level=1),
        Card(
            Heading("AI Agent", level=2),
            Text(f"Status: {status.get()}", id="status-text"),
            Button("Create Lead", onclick="vd.event('ai_create', 'status-text')"),
            Button("List Leads", onclick="vd.event('ai_list', 'status-text')"),
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


@event
async def ai_create(element_id, value):
    status.set("Running agent...")
    run = await agent.run("Create a lead for Ada Lovelace, ada@example.com")
    status.set(f"Done: {run.output}")
    leads_list = await Lead.all()
    leads_display.set(f"{len(leads_list)} leads")


@event
async def ai_list(element_id, value):
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


if __name__ == "__main__":
    app.run()
