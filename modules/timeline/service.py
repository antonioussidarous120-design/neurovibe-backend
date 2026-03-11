import statistics
from shared.models import TimelineResponse, TimelinePoint

async def build_timeline(job_id: str, db) -> TimelineResponse:
    res = db.table("job_segments").select("*").eq("job_id", job_id).order("time_start").execute()
    points = []
    for seg in res.data:
        emotion_map = {"curiosity": seg.get("curiosity") or 0, "warmth": seg.get("warmth") or 0, "trust": seg.get("trust") or 0, "excitement": seg.get("excitement") or 0}
        dominant = max(emotion_map, key=emotion_map.get)
        points.append(TimelinePoint(time_start=seg["time_start"], time_end=seg["time_end"], score=seg.get("segment_score") or 0, dominant_emotion=dominant, is_drop_moment=seg.get("is_drop_moment", False)))
    scores = [p.score for p in points]
    return TimelineResponse(job_id=job_id, points=points, overall_score=round(statistics.mean(scores), 2) if scores else 0.0)
