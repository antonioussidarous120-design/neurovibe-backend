from fastapi import APIRouter
from core.database import get_supabase
from modules.timeline.service import build_timeline
router = APIRouter()
@router.get("/{job_id}")
async def timeline(job_id: str):
    db = get_supabase()
    return await build_timeline(job_id, db)
