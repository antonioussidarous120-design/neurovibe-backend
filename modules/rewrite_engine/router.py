from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.database import get_supabase
from modules.rewrite_engine.service import generate_rewrite
import uuid
router = APIRouter()
class RewriteRequest(BaseModel):
    job_id: str
    segment_id: str
    original_text: str
    target_emotion: str
    emotion_targets: Optional[dict] = None
@router.post("/")
async def rewrite(req: RewriteRequest):
    db = get_supabase()
    result = await generate_rewrite(req.original_text, req.target_emotion, {}, req.emotion_targets)
    rewrite_id = str(uuid.uuid4())
    db.table("rewrites").insert({"id":rewrite_id,"segment_id":req.segment_id,"job_id":req.job_id,"original_text":req.original_text,"improved_text":result["improved_text"],"target_emotion":req.target_emotion,"emotion_delta":result["emotion_delta"]}).execute()
    return {"rewrite_id":rewrite_id,"segment_id":req.segment_id,"original_text":req.original_text,"improved_text":result["improved_text"],"target_emotion":req.target_emotion,"emotion_delta":result["emotion_delta"]}
