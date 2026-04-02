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
    techniques = {"warmth": "personal pronouns, real stories, saying 'I' and 'you', being vulnerable and relatable", "curiosity": "leaving a question hanging, dropping a surprising fact, starting mid-thought so they have to keep reading", "trust": "dropping a real number, admitting something, naming a specific detail only someone who knows would say", "excitement": "short punchy sentences, starting with a verb, painting what life looks like after"}
    prompt = f"""Rewrite this line to boost "{target_emotion}". Technique: {techniques.get(target_emotion, "make it feel real and human")}.

Rules:
- Keep the same core message and roughly the same length
- Sound like a real person talking, not an AI
- No buzzwords, no corporate speak, no inspirational fluff
- If the original is stiff, loosen it up — contractions, casual phrasing, first person
- Don't make it cheesy or over-the-top

Original: "{original_text}"

JSON only: {{"improved_text": "rewrite here", "emotion_delta": {{"warmth": 0.0, "curiosity": 0.0, "trust": 0.0, "excitement": 0.0, "boredom_risk": 0.0}}, "technique_used": "one short sentence describing what you actually changed"}}"""
    try:
        r = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a straight-talking content coach — like a friend who works in marketing and gives real honest feedback. Never use corporate language, AI buzzwords, or formal tone. Write like you're texting a friend who asked for advice. Be specific, direct, and real. Say things like 'your hook is weak here because...' not 'the engagement metrics indicate suboptimal performance'. Use casual language, be encouraging but honest. Short sentences. Get to the point fast."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"}, temperature=0.75, max_tokens=400)
        result = json.loads(r.choices[0].message.content)
        return {"improved_text": result.get("improved_text", original_text), "emotion_delta": result.get("emotion_delta", {}), "technique_used": result.get("technique_used", "")}
    except Exception:
        return {"improved_text": original_text, "emotion_delta": {}, "technique_used": "error"}
