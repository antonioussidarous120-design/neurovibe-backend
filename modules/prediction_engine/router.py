from fastapi import APIRouter
from core.database import get_supabase
from modules.prediction_engine.service import predict_job
router = APIRouter()
@router.post("/{job_id}")
async def predict(job_id: str):
    db = get_supabase()
    return await predict_job(job_id, db)
