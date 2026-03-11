from fastapi import APIRouter
from core.database import get_supabase
from modules.transcription.service import transcribe_job
import asyncio
router = APIRouter()
@router.post("/{job_id}")
async def transcribe(job_id: str):
    db = get_supabase()
    segments = await transcribe_job(job_id, db)
    return {"job_id": job_id, "segment_count": len(segments)}
