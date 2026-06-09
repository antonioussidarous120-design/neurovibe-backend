from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from core.database import get_supabase
from core.config import settings, TEST_USER_ID
from modules.video_analysis.service import analyze_video, SUPPORTED_FORMATS
import uuid
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    file_path: str
    job_id: Optional[str] = None


async def _run_analysis(
    video_job_id: str,
    file_path: str,
    filename: str,
    job_id: Optional[str],
):
    """Background task: download file from Supabase storage, run analysis, update job row."""
    db = get_supabase()
    start_time = time.time()
    logger.info(f"[_run_analysis] starting — file_path={file_path} filename={filename} video_job_id={video_job_id}")
    try:
        # Download the video bytes from Supabase storage
        file_bytes = db.storage.from_(settings.SUPABASE_BUCKET).download(file_path)
        logger.info(f"[_run_analysis] downloaded {len(file_bytes)} bytes from storage")

        result = await analyze_video(file_bytes, filename, file_path, job_id, db)
        elapsed = round(time.time() - start_time, 1)
        logger.info(f"[_run_analysis] COMPLETE video_job_id={video_job_id} elapsed={elapsed}s")
        db.table("video_analysis_jobs").update({
            "status": "complete",
            "result": result,
            "updated_at": "now()",
        }).eq("id", video_job_id).execute()
    except Exception as e:
        elapsed = round(time.time() - start_time, 1)
        logger.error(f"[_run_analysis] ERROR video_job_id={video_job_id} elapsed={elapsed}s error={e}")
        db.table("video_analysis_jobs").update({
            "status": "error",
            "error_message": str(e),
            "updated_at": "now()",
        }).eq("id", video_job_id).execute()


@router.get("/upload-url")
async def get_upload_url(filename: str = Query(..., description="Original filename including extension")):
    """
    Returns a presigned Supabase storage upload URL.
    Frontend uploads directly to Supabase (bypassing Railway size limits),
    then calls POST /analyze with the returned file_path.
    Storage bucket now has open RLS policies so anon uploads work.
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    file_id = str(uuid.uuid4())
    file_path = f"{TEST_USER_ID}/video_analysis/{file_id}/{filename}"

    db = get_supabase()
    try:
        result = db.storage.from_(settings.SUPABASE_BUCKET).create_signed_upload_url(file_path)
        if isinstance(result, dict):
            signed_url = result.get("signedURL") or result.get("signed_url") or result.get("url")
        else:
            signed_url = getattr(result, "signed_url", None) or getattr(result, "signedURL", None)
        if not signed_url:
            raise ValueError(f"Unexpected response from Supabase storage: {result}")
    except Exception as e:
        logger.error(f"[get_upload_url] failed to create signed URL: {e}")
        raise HTTPException(status_code=500, detail=f"Could not generate upload URL: {e}")

    logger.info(f"[get_upload_url] created signed URL for {file_path}")
    return {"upload_url": signed_url, "file_path": file_path}


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: Optional[str] = Form(None),
):
    """
    Accept video file directly, upload to Supabase storage using service role key,
    then kick off analysis. Avoids signed URL RLS issues entirely.
    """
    filename = file.filename or "video.mp4"
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    file_id = str(uuid.uuid4())
    file_path = f"{TEST_USER_ID}/video_analysis/{file_id}/{filename}"

    # Read file bytes
    file_bytes = await file.read()
    logger.info(f"[upload_video] received {len(file_bytes)} bytes for {filename}")

    # Upload to Supabase using service role key (bypasses RLS)
    db = get_supabase()
    try:
        db.storage.from_(settings.SUPABASE_BUCKET).upload(
            file_path,
            file_bytes,
            {"content-type": file.content_type or "video/mp4"},
        )
        logger.info(f"[upload_video] uploaded to Supabase: {file_path}")
    except Exception as e:
        logger.error(f"[upload_video] Supabase upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")

    # Create job and start analysis
    video_job_id = str(uuid.uuid4())
    db.table("video_analysis_jobs").insert({
        "id": video_job_id,
        "status": "processing",
        "filename": filename,
    }).execute()

    background_tasks.add_task(_run_analysis, video_job_id, file_path, filename, job_id)
    logger.info(f"[upload_video] analysis queued video_job_id={video_job_id}")

    return {"job_id": video_job_id, "status": "processing", "file_path": file_path}


@router.post("/analyze")
async def video_analyze(
    background_tasks: BackgroundTasks,
    req: AnalyzeRequest,
):
    """
    Start analysis for a video already uploaded to Supabase storage.
    Accepts {file_path, job_id} — no file bytes, so Railway's proxy limit is irrelevant.
    """
    file_path = req.file_path
    filename = file_path.rsplit("/", 1)[-1]
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    db = get_supabase()
    video_job_id = str(uuid.uuid4())

    db.table("video_analysis_jobs").insert({
        "id": video_job_id,
        "status": "processing",
        "filename": filename,
    }).execute()

    logger.info(f"[video_analyze] QUEUED video_job_id={video_job_id} file_path={file_path}")

    background_tasks.add_task(_run_analysis, video_job_id, file_path, filename, req.job_id)

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

    return {"status": "complete", "results": row.get("result", {})}
