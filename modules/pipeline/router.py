from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from core.database import get_supabase
from core.auth import get_user_id
from core.plans import check_and_increment, PLAN_LIMITS
from modules.transcription.service import transcribe_job
from modules.emotion_engine.service import analyze_job
from modules.prediction_engine.service import predict_job
from modules.rewrite_engine.service import generate_rewrites_for_drop_moments
import traceback
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run/{job_id}")
async def run_pipeline(job_id: str, background_tasks: BackgroundTasks, request: Request):
    db = get_supabase()
    user_id = get_user_id(request)

    # Validate the job exists before queueing the background task
    res = db.table("jobs").select("id", "status").eq("id", job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Enforce plan limits — increments counter on success
    allowed, plan = check_and_increment(db, user_id)
    if not allowed:
        limit = PLAN_LIMITS.get(plan["plan_name"])
        raise HTTPException(
            status_code=429,
            detail={
                "error": "usage_limit_reached",
                "message": (
                    f"You've used all {limit} analyses this month "
                    f"on the {plan['plan_name'].title()} plan."
                ),
                "plan": plan["plan_name"],
                "used": plan["analyses_used_this_month"],
                "limit": limit,
                "upgrade_message": (
                    "Upgrade to Creator (100/mo) or Pro (unlimited) to keep going."
                ),
            },
        )

    background_tasks.add_task(_run, job_id)
    return {"job_id": job_id, "message": "Pipeline started"}


@router.get("/{job_id}/status")
async def status(job_id: str):
    db = get_supabase()
    res = db.table("jobs").select("*").eq("id", job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return res.data[0]


async def _run(job_id: str):
    db = get_supabase()

    def set_status(s, meta=None):
        update = {"status": s}
        if meta is not None:
            update["meta"] = meta
        db.table("jobs").update(update).eq("id", job_id).execute()

    try:
        # Step 1: Transcription — video jobs are not yet supported; skip gracefully.
        set_status("transcribing")
        try:
            await transcribe_job(job_id, db)
        except NotImplementedError as nie:
            # Video transcription is not implemented yet. The pipeline continues
            # without segments; downstream steps will produce empty/zero results.
            logger.warning(f"[pipeline] job={job_id} transcription skipped: {nie}")
            set_status("analyzing", meta={"transcription_skipped": str(nie)})
        else:
            set_status("analyzing")

        # Step 2: Emotion analysis
        try:
            await analyze_job(job_id, db)
        except ValueError as ve:
            # No segments (e.g. video job with skipped transcription) — skip
            # analysis and prediction rather than failing the whole job.
            logger.warning(f"[pipeline] job={job_id} analysis skipped (no segments): {ve}")
            set_status("complete", meta={"warning": str(ve)})
            return

        # Step 3: Prediction
        set_status("predicting")
        await predict_job(job_id, db)

        # Step 4: Rewrite drop moments
        set_status("rewriting")
        await generate_rewrites_for_drop_moments(job_id, db)

        set_status("complete")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[pipeline] job={job_id} FAILED: {e}\n{tb}")
        db.table("jobs").update({
            "status": "failed",
            "meta": {"error": str(e)},
        }).eq("id", job_id).execute()
