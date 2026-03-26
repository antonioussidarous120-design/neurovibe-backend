from fastapi import APIRouter
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
    return await predict_failure(req.job_id, db)


@router.post("/{job_id}")
async def predict(job_id: str):
    db = get_supabase()
    return await predict_job(job_id, db)
