from fastapi import APIRouter, Request
from pydantic import BaseModel
from core.database import get_supabase
from core.auth import get_user_id
from modules.outreach.service import generate_outreach_campaign

router = APIRouter()


class OutreachRequest(BaseModel):
    product: str
    target_customer: str
    platform: str
    tone: str


@router.post("/generate")
async def outreach_generate(request: Request, req: OutreachRequest):
    user_id = get_user_id(request)
    db = get_supabase()
    return await generate_outreach_campaign(req.product, req.target_customer, req.platform, req.tone, db)
