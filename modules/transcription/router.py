from fastapi import APIRouter, HTTPException
from core.database import get_supabase
from modules.transcription.service import transcribe_job

router = APIRouter()


@router.post("/{job_id}")
async def transcribe(job_id: str):
    db = get_supabase()
    # Confirm the job exists
    res = db.table("jobs").select("id", "content_type").eq("id", job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    try:
        segments = await transcribe_job(job_id, db)
    except NotImplementedError as nie:
        raise HTTPException(status_code=501, detail=str(nie))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Transcription failed: {e}")
    return {"job_id": job_id, "segment_count": len(segments)}
