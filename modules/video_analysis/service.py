import asyncio, uuid, statistics, json, os
from typing import Optional, Tuple
import httpx
from openai import AsyncOpenAI
from core.config import settings

ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"
SUPPORTED_FORMATS = {"mp4", "mov", "webm", "m4a", "mp3", "wav"}
VISUAL_FORMATS = {"mp4", "mov", "webm"}

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "You are a straight-talking content coach — like a friend who works in marketing and gives real honest feedback. "
    "Never use corporate language, AI buzzwords, or formal tone. Write like you're texting a friend who asked for advice. "
    "Be specific, direct, and real. Say things like 'your hook is weak here because...' not 'the engagement metrics indicate suboptimal performance'. "
    "Use casual language, be encouraging but honest. Short sentences. Get to the point fast."
)


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


# ── Audio score calculations ───────────────────────────────────────────────────

def _sentiment_label_to_int(label: str) -> int:
    return {"POSITIVE": 1, "NEUTRAL": 0, "NEGATIVE": -1}.get(label, 0)


def _calc_tone_variety_score(sentiment_results: list) -> float:
    if len(sentiment_results) < 2:
        return 0.0
    transitions = sum(
        1 for i in range(1, len(sentiment_results))
        if sentiment_results[i]["sentiment"] != sentiment_results[i - 1]["sentiment"]
    )
    return round((transitions / (len(sentiment_results) - 1)) * 100, 2)


def _calc_energy_level_score(sentiment_results: list) -> float:
    if not sentiment_results:
        return 0.0
    weights = {"POSITIVE": 1.2, "NEUTRAL": 0.8, "NEGATIVE": 0.6}
    scores = [
        s.get("confidence", 0.5) * weights.get(s["sentiment"], 1.0)
        for s in sentiment_results
    ]
    return round(min(statistics.mean(scores) * 100, 100.0), 2)


def _calc_pacing_score(sentiment_results: list) -> float:
    wpms = []
    for s in sentiment_results:
        duration_sec = (s["end"] - s["start"]) / 1000
        if duration_sec > 0:
            wpms.append((len(s["text"].split()) / duration_sec) * 60)
    if len(wpms) < 2:
        return 50.0
    return round(min((statistics.stdev(wpms) / 60) * 100, 100.0), 2)


def _calc_flat_tone_moments(sentiment_results: list, min_seconds: float = 10.0) -> list:
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
        counts[s.get("sentiment", "NEUTRAL")] = counts.get(s.get("sentiment", "NEUTRAL"), 0) + 1
    total = sum(counts.values()) or 1
    return {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in counts.items()}


def _calc_script_vs_delivery_gap(sentiment_results: list, job_segments: list) -> float:
    if not sentiment_results or not job_segments:
        return 0.0
    delivery_avg = statistics.mean([_sentiment_label_to_int(s["sentiment"]) for s in sentiment_results])
    script_avg = statistics.mean(
        [(seg.get("excitement", 0.5) + seg.get("warmth", 0.5)) / 2 - 0.5 for seg in job_segments]
    )
    return round(min(abs(delivery_avg - script_avg) * 100, 100.0), 2)


# ── Google credentials helper ──────────────────────────────────────────────────

def _get_google_credentials():
    """
    Reads GOOGLE_APPLICATION_CREDENTIALS from the environment, parses it as a
    JSON string with json.loads(), and returns a service account Credentials object.
    Returns None if the variable is unset or not valid JSON (falls back to ADC).
    """
    creds_val = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not creds_val:
        return None
    try:
        info = json.loads(creds_val)
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    except json.JSONDecodeError:
        # Value is a file path, not JSON — let the Google client library use it via ADC
        return None


def _google_is_configured() -> bool:
    return bool(settings.GOOGLE_CLOUD_PROJECT and settings.GOOGLE_CLOUD_BUCKET)


# ── Google Cloud Storage helpers ───────────────────────────────────────────────

async def _gcs_upload(file_bytes: bytes, filename: str, credentials) -> Tuple[str, str]:
    """Upload bytes to GCS, returns (gs_uri, blob_name)."""
    def _sync():
        from google.cloud import storage as gcs
        client = gcs.Client(project=settings.GOOGLE_CLOUD_PROJECT, credentials=credentials)
        blob_name = f"neurovibe-temp/{uuid.uuid4()}/{filename}"
        bucket = client.bucket(settings.GOOGLE_CLOUD_BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(file_bytes, content_type="video/mp4")
        return f"gs://{settings.GOOGLE_CLOUD_BUCKET}/{blob_name}", blob_name

    return await asyncio.to_thread(_sync)


async def _gcs_delete(blob_name: str, credentials):
    """Best-effort GCS cleanup."""
    def _sync():
        from google.cloud import storage as gcs
        client = gcs.Client(project=settings.GOOGLE_CLOUD_PROJECT, credentials=credentials)
        client.bucket(settings.GOOGLE_CLOUD_BUCKET).blob(blob_name).delete()
    try:
        await asyncio.to_thread(_sync)
    except Exception:
        pass


# ── Google Video Intelligence ──────────────────────────────────────────────────

async def _run_video_intelligence(gcs_uri: str, credentials) -> object:
    """Submit and poll Video Intelligence API. Runs in thread pool."""
    def _sync():
        from google.cloud import videointelligence
        client = videointelligence.VideoIntelligenceServiceClient(credentials=credentials)
        features = [
            videointelligence.Feature.SHOT_CHANGE_DETECTION,
            videointelligence.Feature.FACE_DETECTION,
            videointelligence.Feature.TEXT_DETECTION,
            videointelligence.Feature.OBJECT_TRACKING,
        ]
        operation = client.annotate_video(request={"features": features, "input_uri": gcs_uri})
        return operation.result(timeout=600)

    return await asyncio.to_thread(_sync)


# ── Visual score calculations ──────────────────────────────────────────────────

def _parse_shot_changes(ar) -> list:
    return [
        {
            "start_sec": round(s.start_time_offset.total_seconds(), 2),
            "end_sec": round(s.end_time_offset.total_seconds(), 2),
        }
        for s in ar.shot_annotations
    ]


def _calc_cut_frequency_score(shot_changes: list, duration_sec: float) -> float:
    """More cuts per minute → higher score. Caps at 1 cut/sec = 100."""
    if not shot_changes or duration_sec <= 0:
        return 0.0
    cuts_per_min = (len(shot_changes) / duration_sec) * 60
    return round(min((cuts_per_min / 60) * 100, 100.0), 2)


def _calc_face_visibility_score(ar, duration_sec: float) -> float:
    """% of video duration where at least one face is visible."""
    if duration_sec <= 0:
        return 0.0
    face_sec = sum(
        track.segment.end_time_offset.total_seconds() - track.segment.start_time_offset.total_seconds()
        for face in ar.face_detection_annotations
        for track in face.tracks
    )
    return round(min((face_sec / duration_sec) * 100, 100.0), 2)


def _calc_text_overlay_score(ar, duration_sec: float) -> float:
    """% of video duration where text overlays are detected."""
    if duration_sec <= 0:
        return 0.0
    text_sec = sum(
        seg.segment.end_time_offset.total_seconds() - seg.segment.start_time_offset.total_seconds()
        for text in ar.text_annotations
        for seg in text.segments
    )
    return round(min((text_sec / duration_sec) * 100, 100.0), 2)


def _calc_visual_hook_score(ar, shot_changes: list) -> float:
    """
    Score the first 3 seconds: face present (+33.3), text present (+33.3),
    shot change present (+33.4). Maximum 100.
    """
    hook_window = 3.0
    score = 0.0

    for face in ar.face_detection_annotations:
        if any(t.segment.start_time_offset.total_seconds() < hook_window for t in face.tracks):
            score += 33.3
            break

    for text in ar.text_annotations:
        if any(seg.segment.start_time_offset.total_seconds() < hook_window for seg in text.segments):
            score += 33.3
            break

    if any(s["start_sec"] < hook_window for s in shot_changes):
        score += 33.4

    return round(min(score, 100.0), 2)


def _calc_has_movement(ar, shot_changes: list) -> bool:
    """True if the video has dynamic content: multiple shots or tracked moving objects."""
    if len(shot_changes) > 2:
        return True
    for obj in ar.object_annotations:
        if len(obj.frames) > 5:
            xs = [f.normalized_bounding_box.left for f in obj.frames]
            if xs and (max(xs) - min(xs)) > 0.05:
                return True
    return False


# ── GPT-4o visual + audio feedback ────────────────────────────────────────────

async def _generate_visual_feedback(audio_scores: dict, visual_scores: dict) -> str:
    """Generate specific, blunt, actionable feedback combining visual and audio data."""
    face_score = visual_scores.get("face_visibility_score")
    text_score = visual_scores.get("text_overlay_score")
    hook_score = visual_scores.get("visual_hook_score")
    cut_score = visual_scores.get("cut_frequency_score")
    has_movement = visual_scores.get("has_movement")

    visual_section = f"""VISUAL ANALYSIS:
- Visual hook score (first 3 seconds): {hook_score}/100
- Face visible: {face_score}% of video
- Text overlays: {text_score}% of video
- Cut frequency score: {cut_score}/100 (higher = more dynamic editing)
- Has movement/dynamic content: {has_movement}""" if face_score is not None else "VISUAL ANALYSIS: Not available"

    prompt = f"""You are analyzing a marketing video. Here are the measured metrics:

{visual_section}

AUDIO/DELIVERY ANALYSIS:
- Tone variety score: {audio_scores.get('tone_variety_score', 'N/A')}/100
- Energy level score: {audio_scores.get('energy_level_score', 'N/A')}/100
- Pacing score: {audio_scores.get('pacing_score', 'N/A')}/100
- Flat tone moments (sections with no sentiment shift): {len(audio_scores.get('flat_tone_moments', []))}

Give 3-5 specific, blunt, actionable feedback points. Each should be 1-2 sentences.
Lead with the biggest weaknesses. Be concrete — reference the actual numbers. Examples of the tone:
"Your first 3 seconds have no face visible and no text overlay — you lose 40% of viewers before you say a word. Start with your face in frame and add a bold text hook immediately."
"Your tone never changes across {len(audio_scores.get('flat_tone_moments', []))} flat segments — the audience has no reason to keep watching. Add a pattern interrupt every 8-10 seconds."
Do NOT be generic. Every sentence must reference a real score or timestamp."""

    r = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    return r.choices[0].message.content.strip()


# ── analyze_video_visuals (public) ─────────────────────────────────────────────

async def analyze_video_visuals(
    file_bytes: bytes,
    filename: str,
    audio_duration_sec: float,
    audio_data: dict,
) -> dict:
    """
    Runs Google Video Intelligence on file_bytes and returns visual scores
    plus GPT-4o feedback. Returns empty defaults if Google is not configured.
    """
    if not _google_is_configured():
        return _empty_visual_result()

    credentials = _get_google_credentials()
    blob_name = None
    try:
        gcs_uri, blob_name = await _gcs_upload(file_bytes, filename, credentials)
        result = await _run_video_intelligence(gcs_uri, credentials)
        ar = result.annotation_results[0]

        shot_changes = _parse_shot_changes(ar)
        visual_scores = {
            "shot_changes": shot_changes,
            "cut_frequency_score": _calc_cut_frequency_score(shot_changes, audio_duration_sec),
            "face_visibility_score": _calc_face_visibility_score(ar, audio_duration_sec),
            "text_overlay_score": _calc_text_overlay_score(ar, audio_duration_sec),
            "visual_hook_score": _calc_visual_hook_score(ar, shot_changes),
            "has_movement": _calc_has_movement(ar, shot_changes),
        }
        visual_scores["visual_feedback"] = await _generate_visual_feedback(audio_data, visual_scores)
        return visual_scores

    except Exception as e:
        return {**_empty_visual_result(), "visual_feedback": f"Visual analysis error: {e}"}
    finally:
        if blob_name:
            await _gcs_delete(blob_name, credentials)


def _empty_visual_result() -> dict:
    return {
        "shot_changes": [],
        "cut_frequency_score": None,
        "face_visibility_score": None,
        "text_overlay_score": None,
        "visual_hook_score": None,
        "has_movement": None,
        "visual_feedback": None,
    }


# ── Main analysis function ─────────────────────────────────────────────────────

async def analyze_video(file_bytes: bytes, filename: str, file_path: str, job_id: Optional[str], db) -> dict:
    if not settings.ASSEMBLYAI_API_KEY or settings.ASSEMBLYAI_API_KEY == "YOUR_ASSEMBLYAI_API_KEY_HERE":
        raise ValueError("ASSEMBLYAI_API_KEY is not configured. Add it to your .env and Railway variables.")

    ext = filename.rsplit(".", 1)[-1].lower()
    is_visual = ext in VISUAL_FORMATS and _google_is_configured()

    # ── Step 1: Upload to AssemblyAI (and GCS if visual) in parallel ──────────
    if is_visual:
        credentials = _get_google_credentials()
        aai_upload_url, (gcs_uri, blob_name) = await asyncio.gather(
            _upload_bytes(file_bytes),
            _gcs_upload(file_bytes, filename, credentials),
        )
    else:
        aai_upload_url = await _upload_bytes(file_bytes)
        gcs_uri = blob_name = credentials = None

    # ── Step 2: Submit AssemblyAI transcript + kick off Google VIA in parallel ─
    # Google VIA (submit + poll) runs in a thread; AssemblyAI transcript is
    # submitted here and polled in step 3 — both run truly concurrently.
    blob_name_ref = [blob_name]  # mutable ref for finally cleanup
    try:
        if is_visual:
            google_task = asyncio.create_task(_run_video_intelligence(gcs_uri, credentials))
            transcript_id = await _submit_transcript(aai_upload_url)
            # Poll AssemblyAI while Google VIA runs in its thread
            aai_data, vi_result = await asyncio.gather(
                _poll_transcript(transcript_id),
                google_task,
            )
        else:
            transcript_id = await _submit_transcript(aai_upload_url)
            aai_data = await _poll_transcript(transcript_id)
            vi_result = None
    finally:
        if blob_name_ref[0]:
            await _gcs_delete(blob_name_ref[0], credentials)

    # ── Step 3: Calculate audio scores ────────────────────────────────────────
    sentiment_results = aai_data.get("sentiment_analysis_results") or []
    highlights = (aai_data.get("auto_highlights_result") or {}).get("results", [])
    iab_categories = aai_data.get("iab_categories_result") or {}
    content_safety = aai_data.get("content_safety_labels") or {}
    audio_duration_sec = aai_data.get("audio_duration") or 0

    tone_variety_score = _calc_tone_variety_score(sentiment_results)
    energy_level_score = _calc_energy_level_score(sentiment_results)
    pacing_score = _calc_pacing_score(sentiment_results)
    flat_tone_moments = _calc_flat_tone_moments(sentiment_results)
    wpm = _calc_words_per_minute(aai_data)
    breakdown = _sentiment_breakdown(sentiment_results)

    script_vs_delivery_gap = 0.0
    if job_id:
        segs_res = db.table("job_segments").select("excitement,warmth").eq("job_id", job_id).execute()
        script_vs_delivery_gap = _calc_script_vs_delivery_gap(sentiment_results, segs_res.data or [])

    audio_scores = {
        "tone_variety_score": tone_variety_score,
        "energy_level_score": energy_level_score,
        "pacing_score": pacing_score,
        "flat_tone_moments": flat_tone_moments,
    }

    # ── Step 4: Calculate visual scores ───────────────────────────────────────
    if vi_result:
        ar = vi_result.annotation_results[0]
        shot_changes = _parse_shot_changes(ar)
        visual_scores = {
            "shot_changes": shot_changes,
            "cut_frequency_score": _calc_cut_frequency_score(shot_changes, audio_duration_sec),
            "face_visibility_score": _calc_face_visibility_score(ar, audio_duration_sec),
            "text_overlay_score": _calc_text_overlay_score(ar, audio_duration_sec),
            "visual_hook_score": _calc_visual_hook_score(ar, shot_changes),
            "has_movement": _calc_has_movement(ar, shot_changes),
        }
    else:
        visual_scores = _empty_visual_result()

    # ── Step 5: Always generate GPT-4o feedback (audio + visual combined) ─────
    ai_feedback = await _generate_visual_feedback(audio_scores, visual_scores)

    # ── Step 6: Save to Supabase ───────────────────────────────────────────────
    analysis_id = str(uuid.uuid4())
    db.table("video_analyses").insert({
        "id": analysis_id,
        "job_id": job_id,
        "filename": filename,
        "file_path": file_path,
        "transcript": aai_data.get("text", ""),
        "words_per_minute": wpm,
        "tone_variety_score": tone_variety_score,
        "energy_level_score": energy_level_score,
        "pacing_score": pacing_score,
        "sentiment_breakdown": breakdown,
        "flat_tone_moments": flat_tone_moments,
        "highlights": highlights[:20],
        "iab_categories": iab_categories,
        "content_safety": content_safety,
        "script_vs_delivery_gap": script_vs_delivery_gap,
        "raw_assemblyai": {
            "transcript_id": transcript_id,
            "audio_duration": audio_duration_sec,
            "confidence": aai_data.get("confidence"),
        },
        "shot_changes": visual_scores["shot_changes"],
        "cut_frequency_score": visual_scores["cut_frequency_score"],
        "face_visibility_score": visual_scores["face_visibility_score"],
        "text_overlay_score": visual_scores["text_overlay_score"],
        "visual_hook_score": visual_scores["visual_hook_score"],
        "has_movement": visual_scores["has_movement"],
        "visual_feedback": ai_feedback,
        "ai_feedback": ai_feedback,
    }).execute()

    # ── Step 7: Return ─────────────────────────────────────────────────────────
    return {
        "analysis_id": analysis_id,
        "job_id": job_id,
        "transcript": aai_data.get("text", ""),
        "words_per_minute": wpm,
        "audio_scores": {
            "tone_variety_score": tone_variety_score,
            "energy_level_score": energy_level_score,
            "pacing_score": pacing_score,
            "script_vs_delivery_gap": script_vs_delivery_gap,
        },
        "visual_scores": {
            "cut_frequency_score": visual_scores["cut_frequency_score"],
            "face_visibility_score": visual_scores["face_visibility_score"],
            "text_overlay_score": visual_scores["text_overlay_score"],
            "visual_hook_score": visual_scores["visual_hook_score"],
            "has_movement": visual_scores["has_movement"],
        },
        "ai_feedback": ai_feedback,
        "sentiment_breakdown": breakdown,
        "flat_tone_moments": flat_tone_moments,
        "shot_changes": visual_scores["shot_changes"],
        "highlights": highlights[:10],
        "iab_categories": iab_categories,
        "content_safety": content_safety,
        "assemblyai_transcript_id": transcript_id,
    }
