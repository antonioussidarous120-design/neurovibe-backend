from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from core.database import get_supabase
from core.config import settings, TEST_USER_ID
import uuid

router = APIRouter()

@router.post("/video")
async def upload_video(file: UploadFile = File(...), title: str = Form("Untitled")):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    db = get_supabase()
    project_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    path = f"{TEST_USER_ID}/{job_id}/{file.filename}"
    try:
        db.storage.from_(settings.SUPABASE_BUCKET).upload(path, content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage upload failed: {e}")
    try:
        db.table("projects").insert({"id":project_id,"title":title,"user_id":TEST_USER_ID}).execute()
        db.table("jobs").insert({"id":job_id,"project_id":project_id,"user_id":TEST_USER_ID,"status":"pending","content_type":"video","file_path":path,"meta":{}}).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Database insert failed: {e}")
    return {"job_id":job_id,"project_id":project_id,"content_type":"video","status":"pending"}

@router.post("/script")
async def upload_script(script_text: str = Form(...), title: str = Form("Untitled")):
    if not script_text or not script_text.strip():
        raise HTTPException(status_code=400, detail="script_text cannot be empty")
    db = get_supabase()
    project_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    try:
        db.table("projects").insert({"id":project_id,"title":title,"user_id":TEST_USER_ID}).execute()
        db.table("jobs").insert({"id":job_id,"project_id":project_id,"user_id":TEST_USER_ID,"status":"pending","content_type":"script","raw_script":script_text,"meta":{}}).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Database insert failed: {e}")
    return {"job_id":job_id,"project_id":project_id,"content_type":"script","status":"pending"}
