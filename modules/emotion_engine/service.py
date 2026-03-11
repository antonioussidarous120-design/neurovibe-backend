import json, asyncio
from openai import AsyncOpenAI
from core.config import settings
from shared.models import EmotionScores, ScoredSegment

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def analyze_job(job_id: str, db) -> list:
    res = db.table("job_segments").select("*").eq("job_id", job_id).order("time_start").execute()
    raw_segments = res.data
    if not raw_segments:
        raise ValueError(f"No segments for job {job_id}")
    scored = await asyncio.gather(*[_score_segment(seg) for seg in raw_segments])
    for seg_data, scored_seg in zip(raw_segments, scored):
        db.table("job_segments").update({
            "curiosity": scored_seg.scores.curiosity,
            "warmth": scored_seg.scores.warmth,
            "trust": scored_seg.scores.trust,
            "excitement": scored_seg.scores.excitement,
            "boredom_risk": scored_seg.scores.boredom_risk,
            "segment_score": scored_seg.segment_score,
            "is_drop_moment": scored_seg.is_drop_moment,
            "drop_reason": scored_seg.drop_reason,
        }).eq("id", seg_data["id"]).execute()
    return scored

async def _score_segment(seg: dict) -> ScoredSegment:
    scores = await _gpt_score(seg["text"])
    score = _compute_score(scores)
    is_drop = scores.boredom_risk > settings.DROP_MOMENT_THRESHOLD
    return ScoredSegment(
        segment_id=seg["id"], time_start=seg["time_start"], time_end=seg["time_end"],
        text=seg["text"], scores=scores, segment_score=score, is_drop_moment=is_drop,
        drop_reason=_explain_drop(scores) if is_drop else None,
    )

async def _gpt_score(text: str) -> EmotionScores:
    prompt = f"""Score this marketing script segment (0.0-1.0 each):
- curiosity: provokes interest/intrigue?
- warmth: empathy, human connection?
- trust: credible, honest, specific?
- excitement: energizing, motivating?
- boredom_risk: likely to lose audience? (1.0 = certain dropout)

Text: "{text}"

JSON only: {{"curiosity":0.0,"warmth":0.0,"trust":0.0,"excitement":0.0,"boredom_risk":0.0}}"""
    try:
        r = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role":"user","content":prompt}],
            response_format={"type":"json_object"},
            temperature=0.2, max_tokens=100,
        )
        d = json.loads(r.choices[0].message.content)
        return EmotionScores(**{k: max(0.0, min(1.0, float(d.get(k, 0.3)))) for k in ["curiosity","warmth","trust","excitement","boredom_risk"]})
    except Exception:
        return EmotionScores(curiosity=0.3, warmth=0.3, trust=0.3, excitement=0.3, boredom_risk=0.5)

def _compute_score(s: EmotionScores) -> float:
    return round(max(0.0, min(100.0, (s.curiosity*0.25 + s.warmth*0.20 + s.trust*0.20 + s.excitement*0.15 + (1-s.boredom_risk)*0.20) * 100)), 2)

def _explain_drop(s: EmotionScores) -> str:
    r = []
    if s.boredom_risk > 0.75: r.append("very high disengagement risk")
    elif s.boredom_risk > 0.65: r.append("elevated disengagement risk")
    if s.warmth < 0.25: r.append("lacks human connection")
    if s.curiosity < 0.2: r.append("nothing to hold attention")
    return f"Drop risk: {', '.join(r) or 'low emotional engagement'}."
