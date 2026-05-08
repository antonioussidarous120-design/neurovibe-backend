from fastapi import APIRouter, HTTPException
from core.database import get_supabase
from modules.emotion_engine.service import analyze_job

router = APIRouter()


@router.post("/{job_id}")
async def analyze(job_id: str):
    db = get_supabase()
    res = db.table("jobs").select("id").eq("id", job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    try:
        scored = await analyze_job(job_id, db)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Emotion analysis failed: {e}")
    return {"job_id": job_id, "scored_segments": len(scored)}
