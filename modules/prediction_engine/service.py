import math, statistics
from shared.models import PredictionResponse, DropMoment

async def predict_job(job_id: str, db) -> PredictionResponse:
    res = db.table("job_segments").select("*").eq("job_id", job_id).execute()
    segments = res.data
    scores = [s["segment_score"] for s in segments if s["segment_score"] is not None]
    engagement_score = round(statistics.mean(scores), 2) if scores else 0.0
    watch_time  = _sigmoid(engagement_score, 50, 0.07)
    share       = _sigmoid(engagement_score, 65, 0.08)
    conversion  = _sigmoid(engagement_score, 72, 0.09)
    drop_moments = [DropMoment(time_start=s["time_start"], time_end=s["time_end"], reason=s["drop_reason"] or "Low emotional engagement.", segment_id=s["id"]) for s in segments if s.get("is_drop_moment")]
    db.table("jobs").update({"engagement_score": engagement_score, "meta": {"watch_time_probability": watch_time, "share_likelihood": share, "conversion_likelihood": conversion, "drop_moment_count": len(drop_moments)}}).eq("id", job_id).execute()
    return PredictionResponse(job_id=job_id, engagement_score=engagement_score, watch_time_probability=watch_time, share_likelihood=share, conversion_likelihood=conversion, drop_moments=drop_moments)

def _sigmoid(score, midpoint, steepness):
    return round(1 / (1 + math.exp(-steepness * (score - midpoint))), 3)
