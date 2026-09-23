"""Plan limits and usage enforcement for NeuroVibe Studio.

Plans
-----
free     : Script Analyzer 5/mo, Script Generator 2/mo — everything else blocked
creator  : Script Analyzer 50/mo, Script Generator 20/mo, Video 5/mo,
           Content Calendar unlimited, Marketing Plan unlimited — Ads blocked
pro      : Everything unlimited, Ads unlocked

Sentinel values in PLAN_FEATURES:
  None  → feature is blocked on this plan (raise 403)
  -1    → unlimited (no counter increment needed)
  int>0 → monthly limit (tracked via per-feature counter column)
"""

import logging
import threading
from datetime import date
from dateutil.relativedelta import relativedelta
from core.config import TEST_USER_ID

logger = logging.getLogger(__name__)


# ─── Email helpers (fire-and-forget background threads) ───────────────────────

def _fire_welcome_email(db, user_id: str) -> None:
    """Fetch user email from Supabase Auth and send welcome email in a daemon thread."""
    def _send():
        try:
            user_res = db.auth.admin.get_user_by_id(user_id)
            if not (user_res and user_res.user and user_res.user.email):
                return
            email = user_res.user.email
            meta  = user_res.user.user_metadata or {}
            name  = meta.get("full_name") or meta.get("name") or email.split("@")[0]
            from modules.email.service import welcome_email
            welcome_email(email, name)
        except Exception as exc:
            logger.warning(f"[plans] welcome email failed for {user_id}: {exc}")
    threading.Thread(target=_send, daemon=True).start()


def _fire_limit_email(db, user_id: str, feature: str, plan: dict) -> None:
    """Fetch user email from Supabase Auth and send limit-reached email in a daemon thread."""
    plan_snapshot = dict(plan)   # copy so the thread doesn't see later mutations
    def _send():
        try:
            user_res = db.auth.admin.get_user_by_id(user_id)
            if not (user_res and user_res.user and user_res.user.email):
                return
            from modules.email.service import limit_reached_email
            limit_reached_email(
                to_email   = user_res.user.email,
                plan       = plan_snapshot.get("plan_name", "free"),
                feature    = feature,
                reset_date = str(plan_snapshot.get("reset_date", "")),
            )
        except Exception as exc:
            logger.warning(f"[plans] limit email failed for {user_id} feature={feature}: {exc}")
    threading.Thread(target=_send, daemon=True).start()

# ─── Plan feature limits ───────────────────────────────────────────────────────
# None = blocked (403), -1 = unlimited, positive int = monthly cap
PLAN_FEATURES: dict[str, dict[str, int | None]] = {
    "free": {
        "script_analyzer":   5,
        "script_generator":  2,
        "video_analysis":    None,   # blocked
        "content_calendar":  None,   # blocked
        "marketing_plan":    None,   # blocked
        "ads":               None,   # blocked
    },
    "creator": {
        "script_analyzer":   50,
        "script_generator":  20,
        "video_analysis":    5,
        "content_calendar":  -1,     # unlimited
        "marketing_plan":    -1,     # unlimited
        "ads":               None,   # blocked
    },
    "pro": {
        "script_analyzer":   -1,
        "script_generator":  -1,
        "video_analysis":    -1,
        "content_calendar":  -1,
        "marketing_plan":    -1,
        "ads":               -1,
    },
}

# DB column that tracks usage for each feature (None = no counter, e.g. unlimited features)
FEATURE_COUNTER: dict[str, str | None] = {
    "script_analyzer":   "script_analyses_used",
    "script_generator":  "script_generations_used",
    "video_analysis":    "video_analyses_used",
    "content_calendar":  None,
    "marketing_plan":    None,
    "ads":               None,
}

# Which plan to suggest upgrading to when a feature is blocked or exhausted
UPGRADE_TO: dict[str, dict[str, str]] = {
    "script_analyzer":  {"free": "creator", "creator": "pro"},
    "script_generator": {"free": "creator", "creator": "pro"},
    "video_analysis":   {"free": "creator", "creator": "pro"},
    "content_calendar": {"free": "creator", "creator": "pro"},
    "marketing_plan":   {"free": "creator", "creator": "pro"},
    "ads":              {"free": "pro",     "creator": "pro"},
}


def _next_reset_date() -> str:
    today = date.today()
    return (today.replace(day=1) + relativedelta(months=1)).isoformat()


def get_or_create_plan(db, user_id: str) -> dict:
    """Return the user_plans row, creating a free-tier row if absent.
    Resets monthly counters if reset_date has passed."""
    res = db.table("user_plans").select("*").eq("user_id", user_id).execute()
    today = date.today()

    if not res.data:
        row: dict = {
            "user_id":                  user_id,
            "plan_name":                "free",
            "script_analyses_used":     0,
            "script_generations_used":  0,
            "video_analyses_used":      0,
            "reset_date":               _next_reset_date(),
        }
        try:
            db.table("user_plans").insert(row).execute()
            _fire_welcome_email(db, user_id)   # new user — send welcome email
            from modules.email.service import notify_admin
            notify_admin(
                subject="🆕 New NeuroVibe User",
                body=f"A new user just signed up. User ID: {user_id}. Check Supabase for their email.",
            )
        except Exception as exc:
            logger.warning(f"[plans] insert failed for {user_id}: {exc}")
        return row

    plan = dict(res.data[0])

    # Reset counters if the reset date has passed
    reset_date = date.fromisoformat(str(plan["reset_date"])[:10])
    if reset_date <= today:
        new_reset = _next_reset_date()
        try:
            db.table("user_plans").update({
                "script_analyses_used":    0,
                "script_generations_used": 0,
                "video_analyses_used":     0,
                "reset_date":              new_reset,
            }).eq("user_id", user_id).execute()
        except Exception as exc:
            logger.warning(f"[plans] reset failed for {user_id}: {exc}")
        plan["script_analyses_used"]    = 0
        plan["script_generations_used"] = 0
        plan["video_analyses_used"]     = 0
        plan["reset_date"]              = new_reset

    return plan


def check_feature_access(
    db, user_id: str, feature: str
) -> tuple[str, dict]:
    """Check whether the user may use a given feature.

    Returns (status, plan_dict) where status is:
      "ok"            → allowed; caller must call increment_feature() if counter-tracked
      "blocked"       → feature not on this plan (raise 403)
      "limit_reached" → monthly cap hit (raise 429)

    TEST_USER_ID always returns "ok" with a synthetic pro plan.
    """
    if user_id == TEST_USER_ID:
        return "ok", {
            "plan_name": "pro",
            "script_analyses_used":    0,
            "script_generations_used": 0,
            "video_analyses_used":     0,
            "reset_date":              None,
        }

    plan    = get_or_create_plan(db, user_id)
    pname   = plan.get("plan_name", "free")
    limits  = PLAN_FEATURES.get(pname, PLAN_FEATURES["free"])
    limit   = limits.get(feature)

    if limit is None:
        return "blocked", plan

    if limit == -1:
        return "ok", plan

    counter_col = FEATURE_COUNTER.get(feature)
    used = int(plan.get(counter_col, 0)) if counter_col else 0

    if used >= limit:
        return "limit_reached", plan

    return "ok", plan


def increment_feature(db, user_id: str, feature: str, plan: dict) -> None:
    """Atomically increment the usage counter for a feature.
    No-op if the feature has no counter (unlimited or untracked)."""
    if user_id == TEST_USER_ID:
        return

    counter_col = FEATURE_COUNTER.get(feature)
    if not counter_col:
        return

    current   = int(plan.get(counter_col, 0))
    new_value = current + 1
    try:
        db.table("user_plans").update({counter_col: new_value}).eq("user_id", user_id).execute()
        plan[counter_col] = new_value
    except Exception as exc:
        logger.warning(f"[plans] increment {feature} failed for {user_id}: {exc}")
        return

    # Fire limit-reached email the moment the counter first hits the monthly cap.
    # increment_feature is only called when access was "ok" (used < limit), so
    # new_value == limit means this is the last allowed request for the month.
    cap = PLAN_FEATURES.get(plan.get("plan_name", "free"), {}).get(feature)
    if isinstance(cap, int) and cap > 0 and new_value >= cap:
        _fire_limit_email(db, user_id, feature, plan)
        from modules.email.service import notify_admin
        notify_admin(
            subject=f"⚠️ User Hit Plan Limit — {feature}",
            body=f"A {plan.get('plan_name', 'free')} user hit their {feature} limit. User ID: {user_id}.",
        )


# ─── Legacy shim — kept so existing pipeline router still compiles ─────────────
# Will be removed once pipeline router is updated to check_feature_access.
PLAN_LIMITS: dict[str, int | None] = {
    "free":    5,
    "creator": 50,
    "pro":     None,
}


def check_and_increment(db, user_id: str) -> tuple[bool, dict]:
    """Deprecated — use check_feature_access + increment_feature instead."""
    status, plan = check_feature_access(db, user_id, "script_analyzer")
    if status == "ok":
        increment_feature(db, user_id, "script_analyzer", plan)
        return True, plan
    return False, plan
