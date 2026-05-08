import math, statistics
from shared.models import PredictionResponse, DropMoment


async def predict_failure(job_id: str, db) -> dict:
    res = db.table("job_segments").select("*").eq("job_id", job_id).order("time_start").execute()
    segments = res.data

    if not segments:
        return {"job_id": job_id, "risk_level": "unknown", "failure_reasons": [], "fix_suggestions": [], "predicted_drop_second": None}

    drop_segments = [s for s in segments if s.get("is_drop_moment")]
    scores = [s["segment_score"] for s in segments if s.get("segment_score") is not None]
    avg_score = statistics.mean(scores) if scores else 0.0

    # Derive risk level
    drop_ratio = len(drop_segments) / len(segments)
    if avg_score < 35 or drop_ratio > 0.5:
        risk_level = "high"
    elif avg_score < 55 or drop_ratio > 0.25:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Build failure reasons
    failure_reasons = []
    for seg in drop_segments:
        reason = seg.get("drop_reason") or "Low emotional engagement"
        failure_reasons.append({
            "segment_id": seg["id"],
            "time_start": seg["time_start"],
            "time_end": seg["time_end"],
            "text_preview": (seg.get("text") or "")[:80],
            "reason": reason,
            "boredom_risk": seg.get("boredom_risk"),
        })

    # Fix suggestions based on weakest emotion dimensions
    fix_suggestions = _build_fix_suggestions(segments, drop_segments)

    # Predicted drop second: earliest drop moment's start time
    predicted_drop_second = min((s["time_start"] for s in drop_segments), default=None)

    return {
        "job_id": job_id,
        "risk_level": risk_level,
        "average_segment_score": round(avg_score, 2),
        "drop_moment_count": len(drop_segments),
        "failure_reasons": failure_reasons,
        "fix_suggestions": fix_suggestions,
        "predicted_drop_second": predicted_drop_second,
    }


def _build_fix_suggestions(segments: list, drop_segments: list) -> list:
    suggestions = []
    if not drop_segments:
        return suggestions

    avg = lambda key: statistics.mean([s.get(key) or 0.0 for s in segments])

    if avg("curiosity") < 0.4:
        suggestions.append("Add open loops or provocative questions to raise curiosity — audience isn't intrigued enough to keep watching.")
    if avg("warmth") < 0.35:
        suggestions.append("Include personal stories or empathy-driven language to increase warmth and human connection.")
    if avg("trust") < 0.35:
        suggestions.append("Add specific numbers, case studies, or honest caveats to build credibility.")
    if avg("excitement") < 0.35:
        suggestions.append("Use stronger action verbs and future-pacing language to raise excitement levels.")
    if avg("boredom_risk") > 0.6:
        suggestions.append("Shorten or restructure segments with high boredom risk — consider cutting filler and leading with the key point.")

    if not suggestions:
        suggestions.append("Rewrite drop-moment segments to target the weakest emotion dimension in each.")

    return suggestions

async def predict_job(job_id: str, db) -> PredictionResponse:
    res = db.table("job_segments").select("*").eq("job_id", job_id).execute()
    segments = res.data
    scores = [s["segment_score"] for s in segments if s.get("segment_score") is not None]
    engagement_score = round(statistics.mean(scores), 2) if scores else 0.0
    watch_time  = _sigmoid(engagement_score, 50, 0.07)
    share       = _sigmoid(engagement_score, 65, 0.08)
    conversion  = _sigmoid(engagement_score, 72, 0.09)
    drop_moments = [DropMoment(time_start=s["time_start"], time_end=s["time_end"], reason=s["drop_reason"] or "Low emotional engagement.", segment_id=s["id"]) for s in segments if s.get("is_drop_moment")]
    db.table("jobs").update({"engagement_score": engagement_score, "meta": {"watch_time_probability": watch_time, "share_likelihood": share, "conversion_likelihood": conversion, "drop_moment_count": len(drop_moments)}}).eq("id", job_id).execute()
    return PredictionResponse(job_id=job_id, engagement_score=engagement_score, watch_time_probability=watch_time, share_likelihood=share, conversion_likelihood=conversion, drop_moments=drop_moments)

def _sigmoid(score, midpoint, steepness):
    return round(1 / (1 + math.exp(-steepness * (score - midpoint))), 3)
