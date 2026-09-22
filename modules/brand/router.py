from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from core.database import get_supabase
from core.auth import get_user_id

router = APIRouter()


class BrandProfileRequest(BaseModel):
    niche: str = ""
    audience: str = ""
    tone: str = ""
    platform_pref: str = ""
    voice_notes: str = ""


@router.get("/profile")
async def get_brand_profile(request: Request):
    """Fetch the authenticated user's brand profile."""
    user_id = get_user_id(request)
    try:
        db = get_supabase()
        res = db.table("brand_profiles").select("*").eq("user_id", user_id).maybe_single().execute()
        if res.data:
            return res.data
        return {
            "user_id": user_id,
            "niche": "",
            "audience": "",
            "tone": "",
            "platform_pref": "",
            "voice_notes": "",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile")
async def save_brand_profile(request: Request, req: BrandProfileRequest):
    """Upsert brand profile for the authenticated user."""
    user_id = get_user_id(request)
    try:
        db = get_supabase()
        data = {
            "user_id": user_id,
            "niche": req.niche,
            "audience": req.audience,
            "tone": req.tone,
            "platform_pref": req.platform_pref,
            "voice_notes": req.voice_notes,
            "updated_at": "now()",
        }
        db.table("brand_profiles").upsert(data, on_conflict="user_id").execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
