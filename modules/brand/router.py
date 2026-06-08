from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client
from core.config import settings

router = APIRouter()


def get_supabase():
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY or settings.SUPABASE_ANON_KEY
    return create_client(settings.SUPABASE_URL, key)


class BrandProfileRequest(BaseModel):
    user_id: str
    niche: str = ""
    audience: str = ""
    tone: str = ""
    platform_pref: str = ""
    voice_notes: str = ""


@router.get("/profile")
async def get_brand_profile(user_id: str):
    """Fetch brand profile for a user. Returns empty profile if none exists."""
    try:
        db = get_supabase()
        res = db.table("brand_profiles").select("*").eq("user_id", user_id).maybe_single().execute()
        if res.data:
            return res.data
        # Return empty profile shape so frontend can pre-fill blank form
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
async def save_brand_profile(req: BrandProfileRequest):
    """Upsert brand profile for a user."""
    try:
        db = get_supabase()
        data = {
            "user_id": req.user_id,
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
