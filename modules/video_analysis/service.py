import asyncio, uuid, statistics
import httpx
from core.config import settings

ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"
SUPPORTED_FORMATS = {"mp4", "mov", "webm", "m4a", "mp3", "wav"}


# ── AssemblyAI helpers ─────────────────────────────────────────────────────────

async def _upload_bytes(file_bytes: bytes) -> str:
    """Upload raw bytes to AssemblyAI CDN, returns upload_url."""
    headers = {"authorization": settings.ASSEMBLYAI_API_KEY}
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{ASSEMBLYAI_BASE}/upload", headers=headers, content=file_bytes)
        r.raise_for_status()
        return r.json()["upload_url"]


async def _submit_transcript(upload_url: str) -> str:
    """Submit a transcription job and return the transcript ID."""
    headers = {
        "authorization": settings.ASSEMBLYAI_API_KEY,
        "content-type": "application/json",
    }
    payload = {
        "audio_url": upload_url,
        "sentiment_analysis": True,
        "auto_highlights": True,
        "content_safety": True,
        "iab_categories": True,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{ASSEMBLYAI_BASE}/transcript", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["id"]


async def _poll_transcript(transcript_id: str) -> dict:
    """Poll until the transcript is completed or errored."""
    headers = {"authorization": settings.ASSEMBLYAI_API_KEY}
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(200):  # max ~10 minutes
            r = await client.get(f"{ASSEMBLYAI_BASE}/transcript/{transcript_id}", headers=headers)
            r.raise_for_status()
            data = r.json()
            if data["status"] == "completed":
                return data
            if data["status"] == "error":
                raise ValueError(f"AssemblyAI error: {data.get('error', 'unknown')}")
            await asyncio.sleep(3)
    raise TimeoutError("AssemblyAI transcription timed out after 10 minutes")


# ── Score calculations ─────────────────────────────────────────────────────────

def _sentiment_label_to_int(label: str) -> int:
    return {"POSITIVE": 1, "NEUTRAL": 0, "NEGATIVE": -1}.get(label, 0)


def _calc_tone_variety_score(sentiment_results: list) -> float:
    """
    Measures how much the sentiment changes across the transcript.
    More transitions = higher variety (0-100).
    """
    if len(sentiment_results) < 2:
        return 0.0
    transitions = sum(
        1 for i in range(1, len(sentiment_results))
        if sentiment_results[i]["sentiment"] != sentiment_results[i - 1]["sentiment"]
    )
    max_transitions = len(sentiment_results) - 1
    return round((transitions / max_transitions) * 100, 2)


def _calc_energy_level_score(sentiment_results: list) -> float:
    """
    Energy = weighted average of confidence, boosted for POSITIVE, dampened for NEGATIVE.
    """
    if not sentiment_results:
        return 0.0
    weights = {"POSITIVE": 1.2, "NEUTRAL": 0.8, "NEGATIVE": 0.6}
    scores = [
        s.get("confidence", 0.5) * weights.get(s["sentiment"], 1.0)
        for s in sentiment_results
    ]
    raw = statistics.mean(scores)
    return round(min(raw * 100, 100.0), 2)


def _calc_pacing_score(sentiment_results: list) -> float:
    """
    Measures WPM variance across segments. High variance = dynamic pacing (good).
    Low variance = monotone delivery. Returns 0-100.
    """
    wpms = []
    for s in sentiment_results:
        duration_sec = (s["end"] - s["start"]) / 1000
        if duration_sec > 0:
            word_count = len(s["text"].split())
            wpms.append((word_count / duration_sec) * 60)
    if len(wpms) < 2:
        return 50.0
    stdev = statistics.stdev(wpms)
    # Normalize: stdev of ~30 wpm = score of 50, ~60+ = 100
    return round(min((stdev / 60) * 100, 100.0), 2)


def _calc_flat_tone_moments(sentiment_results: list, min_seconds: float = 10.0) -> list:
    """
    Identifies stretches where sentiment doesn't change for >= min_seconds.
    """
    flat_moments = []
    if not sentiment_results:
        return flat_moments

    run_start = 0
    for i in range(1, len(sentiment_results)):
        same = sentiment_results[i]["sentiment"] == sentiment_results[run_start]["sentiment"]
        if not same or i == len(sentiment_results) - 1:
            end_idx = i if not same else i
            run_duration = (sentiment_results[end_idx - 1]["end"] - sentiment_results[run_start]["start"]) / 1000
            if run_duration >= min_seconds:
                flat_moments.append({
                    "start_ms": sentiment_results[run_start]["start"],
                    "end_ms": sentiment_results[end_idx - 1]["end"],
                    "duration_seconds": round(run_duration, 2),
                    "sentiment": sentiment_results[run_start]["sentiment"],
                    "text_preview": sentiment_results[run_start]["text"][:80],
                })
            run_start = i

    return flat_moments


def _calc_words_per_minute(transcript_data: dict) -> float:
    words = transcript_data.get("words", [])
    if not words:
        text = transcript_data.get("text", "")
        return round(len(text.split()) / max((transcript_data.get("audio_duration", 60) / 60), 0.01), 1)
    audio_duration_sec = transcript_data.get("audio_duration", 0)
    if audio_duration_sec <= 0:
        return 0.0
    return round((len(words) / audio_duration_sec) * 60, 1)


def _sentiment_breakdown(sentiment_results: list) -> dict:
    counts = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    for s in sentiment_results:
        label = s.get("sentiment", "NEUTRAL")
        counts[label] = counts.get(label, 0) + 1
    total = sum(counts.values()) or 1
    return {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in counts.items()}


def _calc_script_vs_delivery_gap(sentiment_results: list, job_segments: list) -> float:
    """
    Compare expected emotion scores from job_segments with actual
    AssemblyAI sentiment delivery. Returns 0-100 (0 = perfect match).
    """
    if not sentiment_results or not job_segments:
        return 0.0

    delivery_avg = statistics.mean(
        [_sentiment_label_to_int(s["sentiment"]) for s in sentiment_results]
    )
    script_avg = statistics.mean(
        [(seg.get("excitement", 0.5) + seg.get("warmth", 0.5)) / 2 - 0.5
         for seg in job_segments]
    )
    gap = abs(delivery_avg - script_avg)
    return round(min(gap * 100, 100.0), 2)


# ── Main analysis function ─────────────────────────────────────────────────────

async def analyze_video(file_bytes: bytes, filename: str, file_path: str, job_id: str | None, db) -> dict:
    if not settings.ASSEMBLYAI_API_KEY or settings.ASSEMBLYAI_API_KEY == "YOUR_ASSEMBLYAI_API_KEY_HERE":
        raise ValueError("ASSEMBLYAI_API_KEY is not configured. Add it to your .env and Railway variables.")

    # 1. Upload to AssemblyAI
    upload_url = await _upload_bytes(file_bytes)

    # 2. Submit transcription with all intelligence features
    transcript_id = await _submit_transcript(upload_url)

    # 3. Poll until complete
    data = await _poll_transcript(transcript_id)

    sentiment_results = data.get("sentiment_analysis_results") or []
    highlights = (data.get("auto_highlights_result") or {}).get("results", [])
    iab_categories = data.get("iab_categories_result") or {}
    content_safety = data.get("content_safety_labels") or {}

    # 4. Calculate scores
    tone_variety_score = _calc_tone_variety_score(sentiment_results)
    energy_level_score = _calc_energy_level_score(sentiment_results)
    pacing_score = _calc_pacing_score(sentiment_results)
    flat_tone_moments = _calc_flat_tone_moments(sentiment_results)
    wpm = _calc_words_per_minute(data)
    breakdown = _sentiment_breakdown(sentiment_results)

    # 5. Script vs delivery gap (requires job_id)
    script_vs_delivery_gap = 0.0
    if job_id:
        segs_res = db.table("job_segments").select("excitement,warmth").eq("job_id", job_id).execute()
        script_vs_delivery_gap = _calc_script_vs_delivery_gap(sentiment_results, segs_res.data or [])

    # 6. Save to Supabase
    analysis_id = str(uuid.uuid4())
    db.table("video_analyses").insert({
        "id": analysis_id,
        "job_id": job_id,
        "filename": filename,
        "file_path": file_path,
        "transcript": data.get("text", ""),
        "words_per_minute": wpm,
        "tone_variety_score": tone_variety_score,
        "energy_level_score": energy_level_score,
        "pacing_score": pacing_score,
        "sentiment_breakdown": breakdown,
        "flat_tone_moments": flat_tone_moments,
        "highlights": highlights[:20],  # top 20 highlights
        "iab_categories": iab_categories,
        "content_safety": content_safety,
        "script_vs_delivery_gap": script_vs_delivery_gap,
        "raw_assemblyai": {
            "transcript_id": transcript_id,
            "audio_duration": data.get("audio_duration"),
            "confidence": data.get("confidence"),
        },
    }).execute()

    return {
        "analysis_id": analysis_id,
        "job_id": job_id,
        "transcript": data.get("text", ""),
        "words_per_minute": wpm,
        "scores": {
            "tone_variety_score": tone_variety_score,
            "energy_level_score": energy_level_score,
            "pacing_score": pacing_score,
            "script_vs_delivery_gap": script_vs_delivery_gap,
        },
        "sentiment_breakdown": breakdown,
        "flat_tone_moments": flat_tone_moments,
        "highlights": highlights[:10],
        "iab_categories": iab_categories,
        "content_safety": content_safety,
        "assemblyai_transcript_id": transcript_id,
    }
