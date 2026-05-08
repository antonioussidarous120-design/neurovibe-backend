from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.database import get_supabase
from modules.rewrite_engine.service import generate_rewrite
import uuid

router = APIRouter()


VALID_EMOTIONS = {"warmth", "curiosity", "trust", "excitement"}


class RewriteRequest(BaseModel):
    job_id: str
    segment_id: str
    original_text: str
    target_emotion: str
    emotion_targets: Optional[dict] = None


@router.post("/")
async def rewrite(req: RewriteRequest):
    if not req.original_text or not req.original_text.strip():
        raise HTTPException(status_code=400, detail="original_text cannot be empty")
    if req.target_emotion not in VALID_EMOTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"target_emotion must be one of: {', '.join(sorted(VALID_EMOTIONS))}",
        )

    db = get_supabase()

    # Verify job exists
    job_res = db.table("jobs").select("id").eq("id", req.job_id).execute()
    if not job_res.data:
        raise HTTPException(status_code=404, detail=f"Job '{req.job_id}' not found")

    # Verify segment exists
    seg_res = db.table("job_segments").select("id").eq("id", req.segment_id).execute()
    if not seg_res.data:
        raise HTTPException(status_code=404, detail=f"Segment '{req.segment_id}' not found")

    try:
        result = await generate_rewrite(req.original_text, req.target_emotion, {}, req.emotion_targets)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Rewrite generation failed: {e}")

    rewrite_id = str(uuid.uuid4())
    try:
        db.table("rewrites").insert({
            "id": rewrite_id,
            "segment_id": req.segment_id,
            "job_id": req.job_id,
            "original_text": req.original_text,
            "improved_text": result["improved_text"],
            "target_emotion": req.target_emotion,
            "emotion_delta": result["emotion_delta"],
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to save rewrite: {e}")

    return {
        "rewrite_id": rewrite_id,
        "segment_id": req.segment_id,
        "original_text": req.original_text,
        "improved_text": result["improved_text"],
        "target_emotion": req.target_emotion,
        "emotion_delta": result["emotion_delta"],
    }
