"""CRM leads management and real-time prospect tracking."""
import random
import string
from voodoo import Div, Heading, Card, Button, Table, register_event, enqueue, _
from app.models import Lead
from app.layout import Layout

async def handle_submit_lead(element_id: str, value: str):
    random_str = ''.join(random.choices(string.ascii_lowercase, k=5))
    name = f"New Lead {random_str}"
    email = f"{random_str}@example.com"
    
    lead = Lead()
    lead.name = name
    lead.email = email
    lead.status = "New"
    await lead.insert()
    
    await enqueue("lead_enrichment", {"lead_id": lead.id})

register_event("submit_lead", handle_submit_lead)

async def page(request):
    leads = await Lead.find_all()
    rows = [[lead.id, lead.name, lead.email, lead.status] for lead in leads]
    
    content = Div(
        Card(
            Div(
                Button(_("leads.generate"), on_click="submit_lead", className="bg-[var(--color-secondary)]/20 hover:bg-[var(--color-secondary)]/40 border border-[var(--color-secondary)]/50 transition-colors text-[var(--color-secondary)] font-semibold py-2 px-4 rounded-lg mb-6"),
                Table(
                    headers=[_("leads.headers.id"), _("leads.headers.name"), _("leads.headers.email"), _("leads.headers.status")],
                    rows=rows,
                    id="leads-table",
                    className="w-full text-left"
                ),
            ),
            className="bg-[var(--color-surface)] border-[var(--color-border)] backdrop-blur-md"
        )
    )
    
    return Layout(content, title=_("leads.title"))
