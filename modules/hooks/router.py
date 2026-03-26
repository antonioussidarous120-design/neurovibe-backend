from fastapi import APIRouter
from pydantic import BaseModel
from core.database import get_supabase
from modules.hooks.service import test_hooks

router = APIRouter()


class HookTestRequest(BaseModel):
    hook_a: str
    hook_b: str
    platform: str


@router.post("/test")
async def hook_test(req: HookTestRequest):
    db = get_supabase()
    return await test_hooks(req.hook_a, req.hook_b, req.platform, db)
