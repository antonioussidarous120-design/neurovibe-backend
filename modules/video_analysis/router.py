from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from core.database import get_supabase
from core.config import settings
from modules.video_analysis.service import analyze_video, SUPPORTED_FORMATS
import uuid

CONTENT_TYPES = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
}

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

    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
    try:
        db.storage.from_(settings.SUPABASE_BUCKET).upload(
            file_path, file_bytes, file_options={"content-type": content_type}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase storage upload failed: {e}")

    try:
        result = await analyze_video(file_bytes, file.filename, file_path, job_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error during video analysis: {e}")

    return result
