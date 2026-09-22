from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List
from core.database import get_supabase
from core.auth import get_user_id
from core.plans import check_feature_access, UPGRADE_TO
from modules.content.service import convert_to_platforms

router = APIRouter()


class MultiPlatformRequest(BaseModel):
    original_script: str
    platform_list: List[str]


@router.post("/multi-platform")
async def multi_platform(request: Request, req: MultiPlatformRequest):
    user_id = get_user_id(request)
    db = get_supabase()

    status, plan = check_feature_access(db, user_id, "marketing_plan")
    if status == "blocked":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_blocked",
                "feature": "marketing_plan",
                "plan": plan["plan_name"],
                "upgrade_to": UPGRADE_TO.get("marketing_plan", {}).get(plan["plan_name"], "creator"),
                "message": "Marketing Plan requires the Creator or Pro plan.",
            },
        )

    return await convert_to_platforms(req.original_script, req.platform_list, db)
