from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from core.database import get_supabase
from core.config import settings
from modules.video_analysis.service import analyze_video, SUPPORTED_FORMATS
import uuid

router = APIRouter()


@router.post("/analyze")
async def video_analyze(
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

    db = get_supabase()
    test_user = "00000000-0000-0000-0000-000000000001"
    file_id = str(uuid.uuid4())
    file_path = f"{test_user}/video_analysis/{file_id}/{file.filename}"

    try:
        db.storage.from_(settings.SUPABASE_BUCKET).upload(file_path, file_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase storage upload failed: {e}")

    try:
        result = await analyze_video(file_bytes, file.filename, file_path, job_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video analysis failed: {e}")

    return result
