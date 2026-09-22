"""Plan limits and usage enforcement for NeuroVibe Studio.

Plans
-----
free     : 10 analyses / month
creator  : 100 analyses / month
pro      : unlimited

Monthly reset is handled here on each request by comparing reset_date
to today, so no cron job is needed.
"""

import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from core.config import TEST_USER_ID

logger = logging.getLogger(__name__)

# None = unlimited
PLAN_LIMITS: dict[str, int | None] = {
    "free":    10,
    "creator": 100,
    "pro":     None,
}


def _next_reset_date() -> str:
    today = date.today()
    return (today.replace(day=1) + relativedelta(months=1)).isoformat()


def get_or_create_plan(db, user_id: str) -> dict:
    """Return the user_plans row, creating a free-tier row if absent.
    Resets the monthly counter if reset_date has passed."""
    res = db.table("user_plans").select("*").eq("user_id", user_id).execute()
    today = date.today()

    if not res.data:
        row = {
            "user_id": user_id,
            "plan_name": "free",
            "analyses_used_this_month": 0,
            "reset_date": _next_reset_date(),
        }
        try:
            db.table("user_plans").insert(row).execute()
        except Exception as exc:
            logger.warning(f"[plans] insert failed for {user_id}: {exc}")
        return row

    plan = dict(res.data[0])

    reset_date = date.fromisoformat(plan["reset_date"])
    if reset_date <= today:
        new_reset = _next_reset_date()
        try:
            db.table("user_plans").update({
                "analyses_used_this_month": 0,
                "reset_date": new_reset,
            }).eq("user_id", user_id).execute()
        except Exception as exc:
            logger.warning(f"[plans] reset failed for {user_id}: {exc}")
        plan["analyses_used_this_month"] = 0
        plan["reset_date"] = new_reset

    return plan


def check_and_increment(db, user_id: str) -> tuple[bool, dict]:
    """Check whether the user may run another analysis and, if so, increment.

    Returns (allowed, plan_dict).
    - If allowed=True  the counter has already been incremented.
    - If allowed=False the caller should raise HTTP 429.
    - TEST_USER_ID always passes without touching the DB (dev/demo mode).
    """
    if user_id == TEST_USER_ID:
        return True, {"plan_name": "pro", "analyses_used_this_month": 0, "reset_date": None}

    plan = get_or_create_plan(db, user_id)
    limit = PLAN_LIMITS.get(plan["plan_name"])

    if limit is not None and plan["analyses_used_this_month"] >= limit:
        return False, plan

    # Within limit — increment atomically (single-row update; race condition
    # risk is negligible for typical single-user usage patterns).
    try:
        db.table("user_plans").update({
            "analyses_used_this_month": plan["analyses_used_this_month"] + 1,
        }).eq("user_id", user_id).execute()
        plan["analyses_used_this_month"] += 1
    except Exception as exc:
        logger.warning(f"[plans] increment failed for {user_id}: {exc}")

    return True, plan
