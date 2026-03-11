from fastapi import APIRouter
from core.database import get_supabase
from modules.emotion_engine.service import analyze_job
router = APIRouter()
@router.post("/{job_id}")
async def analyze(job_id: str):
    db = get_supabase()
    scored = await analyze_job(job_id, db)
    return {"job_id": job_id, "scored_segments": len(scored)}
