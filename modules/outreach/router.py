from fastapi import APIRouter
from pydantic import BaseModel
from core.database import get_supabase
from modules.outreach.service import generate_outreach_campaign

router = APIRouter()


class OutreachRequest(BaseModel):
    product: str
    target_customer: str
    platform: str
    tone: str


@router.post("/generate")
async def outreach_generate(req: OutreachRequest):
    db = get_supabase()
    return await generate_outreach_campaign(req.product, req.target_customer, req.platform, req.tone, db)
