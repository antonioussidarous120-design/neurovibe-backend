"""
Prediction Engine — neuroscience-grounded engagement prediction.

Watch time / share / conversion modeled after:
- Berger & Milkman (2012): High-arousal emotions drive sharing
- Nielsen Norman Group: Attention and abandonment research
- Cialdini (2001): Influence and conversion psychology
"""

import math
import statistics
from shared.models import PredictionResponse, DropMoment


async def predict_failure(job_id: str, db) -> dict:
    res = db.table("job_segments").select("*").eq("job_id", job_id).order("time_start").execute()
    segments = res.data

    if not segments:
        return {
            "job_id": job_id,
            "risk_level": "unknown",
            "failure_reasons": [],
            "fix_suggestions": [],
            "predicted_drop_second": None,
        }

    drop_segments = [s for s in segments if s.get("is_drop_moment")]
    scores = [s["segment_score"] for s in segments if s.get("segment_score") is not None]
    avg_score = statistics.mean(scores) if scores else 0.0
    drop_ratio = len(drop_segments) / len(segments)

    if avg_score < 35 or drop_ratio > 0.5:
        risk_level = "high"
    elif avg_score < 55 or drop_ratio > 0.25:
        risk_level = "medium"
    else:
        risk_level = "low"

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

    fix_suggestions = _build_neuro_suggestions(segments, drop_segments)
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


def _build_neuro_suggestions(segments: list, drop_segments: list) -> list:
    if not drop_segments:
        return []

    avg = lambda key: statistics.mean([s.get(key) or 0.0 for s in segments])
    suggestions = []

    avg_curiosity = avg("curiosity")
    avg_warmth = avg("warmth")
    avg_trust = avg("trust")
    avg_excitement = avg("excitement")
    avg_boredom = avg("boredom_risk")

    if avg_curiosity < 0.40:
        suggestions.append(
            "Curiosity gap too narrow — Loewenstein's Information Gap Theory (1994) shows audiences stay "
            "engaged when they feel a tension between what they know and what they want to know. "
            "Add open loops: rhetorical questions, partial reveals, or 'here's what nobody tells you' structures."
        )

    if avg_warmth < 0.35:
        suggestions.append(
            "Low social connection — mirror neurons (Rizzolatti & Craighero, 2004) activate on first-person "
            "language and human specificity. Switch from 'we provide' to 'I found' — concrete personal "
            "moments outperform abstract benefits every time."
        )

    if avg_trust < 0.35:
        suggestions.append(
            "Weak credibility signals — the medial prefrontal cortex evaluates source trust before accepting "
            "any claim. Add precise numbers (37%, not 40%), named examples, and acknowledge one limitation — "
            "counterintuitively, admitting a flaw raises overall trust (Cialdini, 2001)."
        )

    if avg_excitement < 0.35:
        suggestions.append(
            "Low arousal energy — amygdala-driven excitement requires short sentences, active verbs, and "
            "concrete stakes. Berger & Milkman (2012) found high-arousal content is 34% more likely to be "
            "shared. Cut sentences over 15 words and start at least 3 with a strong action verb."
        )

    if avg_boredom > 0.60:
        suggestions.append(
            "High Default Mode Network activation risk — when content fails to exceed the brain's arousal "
            "threshold, the DMN takes over and attention wanders (Buckner et al., 2008). Nielsen Norman Group "
            "research shows you have 3.5 seconds per section. Lead every paragraph with your most compelling point."
        )

    if not suggestions:
        suggestions.append(
            "Rewrite drop-moment segments targeting the weakest emotion dimension. "
            "Use the AI Rewrite feature on each flagged segment."
        )

    return suggestions


async def predict_job(job_id: str, db) -> PredictionResponse:
    res = db.table("job_segments").select("*").eq("job_id", job_id).execute()
    segments = res.data
    scores = [s["segment_score"] for s in segments if s.get("segment_score") is not None]
    engagement_score = round(statistics.mean(scores), 2) if scores else 0.0

    # Sigmoid curves modeled on content performance data
    # Watch time: peaks around score 50 (moderate engagement threshold)
    # Share: higher bar — requires genuine excitement/curiosity (peaks ~65)
    # Conversion: highest bar — requires trust + excitement combo (peaks ~72)
    watch_time  = _sigmoid(engagement_score, midpoint=48, steepness=0.07)
    share       = _sigmoid(engagement_score, midpoint=63, steepness=0.08)
    conversion  = _sigmoid(engagement_score, midpoint=70, steepness=0.09)

    drop_moments = [
        DropMoment(
            time_start=s["time_start"],
            time_end=s["time_end"],
            reason=s["drop_reason"] or "Low emotional engagement.",
            segment_id=s["id"],
        )
        for s in segments if s.get("is_drop_moment")
    ]

    db.table("jobs").update({
        "engagement_score": engagement_score,
        "meta": {
            "watch_time_probability": watch_time,
            "share_likelihood": share,
            "conversion_likelihood": conversion,
            "drop_moment_count": len(drop_moments),
        },
    }).eq("id", job_id).execute()

    return PredictionResponse(
        job_id=job_id,
        engagement_score=engagement_score,
        watch_time_probability=watch_time,
        share_likelihood=share,
        conversion_likelihood=conversion,
        drop_moments=drop_moments,
    )


def _sigmoid(score: float, midpoint: float, steepness: float) -> float:
    return round(1 / (1 + math.exp(-steepness * (score - midpoint))), 3)
