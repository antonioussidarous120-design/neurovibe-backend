from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.database import get_supabase
from modules.prediction_engine.service import predict_job, predict_failure

router = APIRouter()


class FailureRequest(BaseModel):
    job_id: str


# Literal route must be registered before the parameterized one
@router.post("/failure")
async def failure(req: FailureRequest):
    db = get_supabase()
    res = db.table("jobs").select("id").eq("id", req.job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job '{req.job_id}' not found")
    try:
        return await predict_failure(req.job_id, db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failure prediction failed: {e}")


@router.post("/{job_id}")
async def predict(job_id: str):
    db = get_supabase()
    res = db.table("jobs").select("id").eq("id", job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    try:
        return await predict_job(job_id, db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Prediction failed: {e}")
