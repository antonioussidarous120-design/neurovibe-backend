from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from typing import Optional
from core.database import get_supabase
from modules.video_analysis.service import analyze_video, SUPPORTED_FORMATS
import uuid
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_analysis(
    video_job_id: str,
    file_bytes: bytes,
    filename: str,
    file_path: str,
    job_id: Optional[str],
):
    """Background task: run analysis and update video_analysis_jobs with result or error."""
    db = get_supabase()
    start_time = time.time()
    logger.info(f"[_run_analysis] starting — bytes={len(file_bytes)} filename={filename} video_job_id={video_job_id}")
    try:
        result = await analyze_video(file_bytes, filename, file_path, job_id, db)
        elapsed = round(time.time() - start_time, 1)
        logger.info(f"[video_analyze] BG COMPLETE video_job_id={video_job_id} elapsed={elapsed}s")
        db.table("video_analysis_jobs").update({
            "status": "complete",
            "result": result,
            "updated_at": "now()",
        }).eq("id", video_job_id).execute()
    except Exception as e:
        elapsed = round(time.time() - start_time, 1)
        logger.error(f"[video_analyze] BG ERROR video_job_id={video_job_id} elapsed={elapsed}s error={e}")
        db.table("video_analysis_jobs").update({
            "status": "error",
            "error_message": str(e),
            "updated_at": "now()",
        }).eq("id", video_job_id).execute()


@router.post("/analyze")
async def video_analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: Optional[str] = Form(None),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Video file too large. Maximum size is 500MB.")

    db = get_supabase()

    # Create a tracking row immediately so the client can poll
    video_job_id = str(uuid.uuid4())
    # file_path is a logical reference stored in video_analyses — no actual upload
    file_path = f"assemblyai/{video_job_id}/{file.filename}"

    db.table("video_analysis_jobs").insert({
        "id": video_job_id,
        "status": "processing",
        "filename": file.filename,
    }).execute()

    logger.info(f"[video_analyze] QUEUED video_job_id={video_job_id} file={file.filename} size={len(file_bytes)}")

    background_tasks.add_task(
        _run_analysis, video_job_id, file_bytes, file.filename, file_path, job_id
    )

    return {"job_id": video_job_id, "status": "processing"}


@router.get("/status/{video_job_id}")
async def video_status(video_job_id: str):
    db = get_supabase()
    res = db.table("video_analysis_jobs").select("status,result,error_message").eq("id", video_job_id).execute()

    if not res.data:
        raise HTTPException(status_code=404, detail=f"No analysis job found for id '{video_job_id}'")

    row = res.data[0]
    status = row["status"]

    if status == "processing":
        return {"status": "processing"}

    if status == "error":
        return {"status": "error", "message": row.get("error_message", "Unknown error")}

    # complete
    return {"status": "complete", "results": row.get("result", {})}
