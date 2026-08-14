"""Background asynchronous workers and task queues."""
import asyncio
from voodoo import queue, Agent
from app.models import Lead

@queue("lead_enrichment")
async def process_lead_enrichment(payload: dict):
    lead_id = payload.get("lead_id")
    print(f"Worker: Starting enrichment for lead {lead_id}")
    
    # Simulate heavy processing
    await asyncio.sleep(3)
    
    # Use Agent for enrichment (simulated)
    agent = Agent(system_prompt="You are a lead enrichment AI. Extract company and role.")
    response = await agent.run("Enrich lead ID " + str(lead_id))
    print(f"Worker AI Response: {response}")
    
    # Fetch lead and update status
    leads = await Lead.find_all()
    target_lead = next((l for l in leads if l.id == lead_id), None)
    
    if target_lead:
        target_lead.status = "Enriched"
        await target_lead.update()
        print(f"Worker: Finished enrichment for lead {lead_id}")
