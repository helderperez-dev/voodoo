"""REST API routing and endpoints."""
from voodoo import api, storage
from pydantic import BaseModel
from typing import List, Optional
from app.models import Lead
from starlette.requests import Request

# Pydantic schemas for the API request/response
class LeadCreate(BaseModel):
    name: str
    email: str
    
class LeadResponse(BaseModel):
    id: int
    name: str
    email: str
    status: str

class SuccessResponse(BaseModel):
    success: bool
    message: str

@api.get("/api/leads")
async def get_leads() -> List[LeadResponse]:
    """Fetch all leads from the Voodoo database."""
    leads = await Lead.find_all()
    # Map Voodoo ORM models to Pydantic responses
    return [
        LeadResponse(
            id=lead.id, 
            name=lead.name, 
            email=lead.email, 
            status=lead.status
        ) 
        for lead in leads
    ]

@api.post("/api/leads")
async def create_lead(payload: LeadCreate) -> LeadResponse:
    """Create a new lead via API and trigger UI updates automatically."""
    lead = Lead()
    lead.name = payload.name
    lead.email = payload.email
    lead.status = "New (API)"
    
    await lead.insert() # This triggers @on_insert hook automatically
    
    return LeadResponse(
        id=lead.id,
        name=lead.name,
        email=lead.email,
        status=lead.status
    )

@api.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: int) -> SuccessResponse:
    """Delete a lead by ID. Note: Voodoo's base ORM currently does not have an explicit .delete(), 
    but we can run raw SQL or implement delete in the model."""
    from voodoo import get_db
    db = await get_db()
    await db.execute("DELETE FROM lead WHERE id = ?", (lead_id,))
    await db.commit()
    
    # Broadcast table update after deletion manually or let the caller refresh
    from app.models import broadcast_table_update
    await broadcast_table_update()
    
    return SuccessResponse(success=True, message=f"Lead {lead_id} deleted successfully.")

@api.post("/api/upload")
async def upload_file(request: Request):
    """Upload a file using Voodoo Storage."""
    form = await request.form()
    file = form.get("file")
    if not file:
        return {"error": "No file provided"}
    
    # file is a starlette.datastructures.UploadFile
    content = await file.read()
    filename = file.filename
    
    # Upload to storage (defaults to the 'public' bucket)
    url = await storage.upload(content, filename, bucket="public")
    
    return {"url": url, "filename": filename}

