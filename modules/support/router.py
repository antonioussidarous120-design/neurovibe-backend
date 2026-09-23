from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from modules.email.service import notify_admin, support_confirmation_email
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class SupportRequest(BaseModel):
    name: str
    email: EmailStr
    message: str


@router.post("/")
async def submit_support(req: SupportRequest):
    """Forward support message to admin, send confirmation to user."""
    logger.info(f"[support] message from {req.email}")

    notify_admin(
        subject=f"🆘 Support Request from {req.name}",
        body=f"{req.name} ({req.email}) says:\n\n{req.message}",
    )
    support_confirmation_email(req.email, req.name)

    return {"ok": True, "message": "Message received. We'll reply within 24 hours."}
