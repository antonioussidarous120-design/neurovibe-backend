from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from core.database import get_supabase
from modules.content.service import convert_to_platforms

router = APIRouter()


class MultiPlatformRequest(BaseModel):
    original_script: str
    platform_list: List[str]


@router.post("/multi-platform")
async def multi_platform(req: MultiPlatformRequest):
    db = get_supabase()
    return await convert_to_platforms(req.original_script, req.platform_list, db)
