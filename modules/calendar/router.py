from fastapi import APIRouter
from pydantic import BaseModel
from core.database import get_supabase
from modules.calendar.service import generate_content_calendar

router = APIRouter()


class CalendarRequest(BaseModel):
    product: str
    platform: str
    posting_goal: str
    days: int = 30


@router.post("/generate")
async def calendar_generate(req: CalendarRequest):
    db = get_supabase()
    return await generate_content_calendar(req.product, req.platform, req.posting_goal, req.days, db)
