from fastapi import APIRouter, UploadFile, File, Form, Depends
from core.database import get_supabase
from core.config import settings
import uuid, os

router = APIRouter()

@router.post("/video")
async def upload_video(file: UploadFile = File(...), title: str = Form("Untitled")):
    db = get_supabase()
    project_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    test_user = "00000000-0000-0000-0000-000000000001"
    content = await file.read()
    path = f"{test_user}/{job_id}/{file.filename}"
    db.storage.from_(settings.SUPABASE_BUCKET).upload(path, content)
    db.table("projects").insert({"id":project_id,"title":title,"user_id":test_user}).execute()
    db.table("jobs").insert({"id":job_id,"project_id":project_id,"user_id":test_user,"status":"pending","content_type":"video","file_path":path,"meta":{}}).execute()
    return {"job_id":job_id,"project_id":project_id,"content_type":"video","status":"pending"}

@router.post("/script")
async def upload_script(script_text: str = Form(...), title: str = Form("Untitled")):
    db = get_supabase()
    project_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    test_user = "00000000-0000-0000-0000-000000000001"
    db.table("projects").insert({"id":project_id,"title":title,"user_id":test_user}).execute()
    db.table("jobs").insert({"id":job_id,"project_id":project_id,"user_id":test_user,"status":"pending","content_type":"script","raw_script":script_text,"meta":{}}).execute()
    return {"job_id":job_id,"project_id":project_id,"content_type":"script","status":"pending"}
