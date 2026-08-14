"""Database models and real-time UI synchronization hooks."""
import asyncio
from voodoo import BaseModel, on_insert, on_update, rls_policy, ws_manager, Table

class Lead(BaseModel):
    name: str
    email: str
    status: str

# RLS Policy to only show leads matching a specific context if needed
@rls_policy(Lead)
def lead_policy(user_context: dict) -> str:
    # Example: return "status != 'deleted'"
    return ""

async def broadcast_table_update():
    leads = await Lead.find_all()
    rows = [[lead.id, lead.name, lead.email, lead.status] for lead in leads]
    table = Table(
        headers=["ID", "Name", "Email", "Status"],
        rows=rows,
        id="leads-table",
        className="w-full text-left"
    )
    await ws_manager.broadcast_patch("leads-table", table.render())

@on_insert(Lead)
async def handle_new_lead(lead: Lead):
    print(f"Trigger: New lead inserted - {lead.name}")
    await broadcast_table_update()

@on_update(Lead)
async def handle_lead_update(lead: Lead):
    print(f"Trigger: Lead updated - {lead.name}")
    await broadcast_table_update()
