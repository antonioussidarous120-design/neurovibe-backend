import re
from core.config import settings
from shared.models import TranscriptSegment

async def transcribe_job(job_id: str, db) -> list:
    res = db.table("jobs").select("*").eq("id", job_id).single().execute()
    job = res.data
    if job["content_type"] == "video":
        raise NotImplementedError("Video transcription requires ffmpeg - use script mode for testing")
    segments = _split_script(job["raw_script"])
    db.table("job_segments").delete().eq("job_id", job_id).execute()
    db.table("job_segments").insert([
        {"job_id": job_id, "time_start": s.time_start, "time_end": s.time_end, "text": s.text}
        for s in segments
    ]).execute()
    return segments

def _split_script(script: str) -> list:
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    segments, current_time, buffer_text, buffer_start = [], 0.0, "", 0.0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        duration = len(sentence.split()) / 2.5
        if not buffer_text:
            buffer_start = current_time
        buffer_text = (buffer_text + " " + sentence).strip()
        current_time += duration
        if current_time - buffer_start >= 15.0:
            segments.append(TranscriptSegment(time_start=round(buffer_start,3), time_end=round(current_time,3), text=buffer_text))
            buffer_text = ""
    if buffer_text:
        segments.append(TranscriptSegment(time_start=round(buffer_start,3), time_end=round(current_time,3), text=buffer_text))
    return segments
