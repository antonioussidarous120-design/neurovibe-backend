from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from core.database import get_supabase
from core.auth import get_user_id
from core.plans import check_feature_access, UPGRADE_TO
from modules.calendar.service import generate_content_calendar

router = APIRouter()


class CalendarRequest(BaseModel):
    product: str
    platform: str
    posting_goal: str
    days: int = 30


@router.post("/generate")
async def calendar_generate(request: Request, req: CalendarRequest):
    user_id = get_user_id(request)
    db = get_supabase()

    status, plan = check_feature_access(db, user_id, "content_calendar")
    if status == "blocked":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_blocked",
                "feature": "content_calendar",
                "plan": plan["plan_name"],
                "upgrade_to": UPGRADE_TO.get("content_calendar", {}).get(plan["plan_name"], "creator"),
                "message": "Content Calendar requires the Creator or Pro plan.",
            },
        )

    return await generate_content_calendar(req.product, req.platform, req.posting_goal, req.days, db)
