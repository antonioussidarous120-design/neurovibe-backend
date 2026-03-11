from fastapi import APIRouter, BackgroundTasks
from core.database import get_supabase
from modules.transcription.service import transcribe_job
from modules.emotion_engine.service import analyze_job
from modules.prediction_engine.service import predict_job
from modules.rewrite_engine.service import generate_rewrites_for_drop_moments
import traceback
router = APIRouter()
@router.post("/run/{job_id}")
async def run_pipeline(job_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run, job_id)
    return {"job_id": job_id, "message": "Pipeline started"}
@router.get("/{job_id}/status")
async def status(job_id: str):
    db = get_supabase()
    res = db.table("jobs").select("*").eq("id", job_id).single().execute()
    return res.data
async def _run(job_id: str):
    db = get_supabase()
    def set_status(s): db.table("jobs").update({"status":s}).eq("id",job_id).execute()
    try:
        set_status("transcribing"); await transcribe_job(job_id, db)
        set_status("analyzing");    await analyze_job(job_id, db)
        set_status("predicting");   await predict_job(job_id, db)
        set_status("rewriting");    await generate_rewrites_for_drop_moments(job_id, db)
        set_status("complete")
    except Exception as e:
        db.table("jobs").update({"status":"failed","meta":{"error":str(e)}}).eq("id",job_id).execute()
