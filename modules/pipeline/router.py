from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from core.database import get_supabase
from core.auth import get_user_id
from core.plans import check_feature_access, increment_feature, PLAN_FEATURES, UPGRADE_TO
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

    # Enforce plan limits for script_analyzer feature
    status, plan = check_feature_access(db, user_id, "script_analyzer")
    if status == "blocked":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_blocked",
                "feature": "script_analyzer",
                "plan": plan["plan_name"],
                "upgrade_to": UPGRADE_TO.get("script_analyzer", {}).get(plan["plan_name"], "creator"),
                "message": "Script Analyzer is not available on this plan.",
            },
        )
    if status == "limit_reached":
        raise HTTPException(
            status_code=429,
            detail={
                "error": "limit_reached",
                "feature": "script_analyzer",
                "plan": plan["plan_name"],
                "used": plan.get("script_analyses_used", 0),
                "limit": PLAN_FEATURES.get(plan["plan_name"], {}).get("script_analyzer"),
                "upgrade_to": UPGRADE_TO.get("script_analyzer", {}).get(plan["plan_name"], "pro"),
                "message": f"You've used all {PLAN_FEATURES.get(plan['plan_name'], {}).get('script_analyzer')} Script Analyzer runs this month on the {plan['plan_name'].title()} plan.",
            },
        )

    increment_feature(db, user_id, "script_analyzer", plan)
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
