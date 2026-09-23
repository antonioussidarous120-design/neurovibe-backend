from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from core.database import get_supabase
from modules.email.service import notify_admin, waitlist_confirmation_email
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class WaitlistRequest(BaseModel):
    email: EmailStr


@router.post("/")
async def join_waitlist(req: WaitlistRequest):
    """Save email to waitlist table, notify admin, confirm to user."""
    db = get_supabase()

    try:
        db.table("waitlist").insert({"email": req.email}).execute()
    except Exception as exc:
        err = str(exc).lower()
        if "duplicate" in err or "unique" in err or "23505" in err:
            # Already signed up — treat as success so we don't leak enumeration info
            return {"ok": True, "message": "Already on the list"}
        logger.error(f"[waitlist] insert failed for {req.email}: {exc}")
        raise HTTPException(status_code=500, detail="Could not save email. Please try again.")

    logger.info(f"[waitlist] new signup: {req.email}")

    notify_admin(
        subject="🎉 New Waitlist Signup",
        body=f"New waitlist signup: {req.email}",
    )
    waitlist_confirmation_email(req.email)

    return {"ok": True, "message": "You're on the list"}
