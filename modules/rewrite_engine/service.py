import json, uuid
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_rewrites_for_drop_moments(job_id: str, db) -> list:
    res = db.table("job_segments").select("*").eq("job_id", job_id).eq("is_drop_moment", True).execute()
    rewrites = []
    for seg in res.data:
        scores = {"warmth": seg.get("warmth") or 0.3, "curiosity": seg.get("curiosity") or 0.3, "trust": seg.get("trust") or 0.3}
        target = min(scores, key=scores.get)
        rewrite = await generate_rewrite(seg["text"], target, {k: seg.get(k) or 0.3 for k in ["curiosity","warmth","trust","excitement","boredom_risk"]})
        rewrite_id = str(uuid.uuid4())
        db.table("rewrites").insert({"id": rewrite_id, "segment_id": seg["id"], "job_id": job_id, "original_text": seg["text"], "improved_text": rewrite["improved_text"], "target_emotion": target, "emotion_delta": rewrite["emotion_delta"]}).execute()
        rewrites.append({"segment_id": seg["id"], "original_text": seg["text"], **rewrite})
    return rewrites

async def generate_rewrite(original_text: str, target_emotion: str, current_scores: dict, emotion_targets: dict = None) -> dict:
    techniques = {"warmth": "personal pronouns, empathy, vulnerability, relatable stories", "curiosity": "open loops, surprising facts, provocative questions", "trust": "specific numbers, honest caveats, concrete examples", "excitement": "action verbs, future-pacing, possibility framing"}
    prompt = f"""Rewrite this to increase "{target_emotion}". Use: {techniques.get(target_emotion, "emotional resonance")}.
Keep same message, similar length, sound human not AI.

Original: "{original_text}"

JSON only: {{"improved_text": "rewrite here", "emotion_delta": {{"warmth": 0.0, "curiosity": 0.0, "trust": 0.0, "excitement": 0.0, "boredom_risk": 0.0}}, "technique_used": "one sentence"}}"""
    try:
        r = await client.chat.completions.create(model=settings.OPENAI_MODEL, messages=[{"role":"user","content":prompt}], response_format={"type":"json_object"}, temperature=0.75, max_tokens=400)
        result = json.loads(r.choices[0].message.content)
        return {"improved_text": result.get("improved_text", original_text), "emotion_delta": result.get("emotion_delta", {}), "technique_used": result.get("technique_used", "")}
    except Exception:
        return {"improved_text": original_text, "emotion_delta": {}, "technique_used": "error"}
