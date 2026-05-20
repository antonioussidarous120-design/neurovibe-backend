"""
Rewrite Engine — powered by Claude claude-sonnet-4-6 with neuroscience-backed rhetorical techniques.
"""

import json
import uuid
import anthropic
from openai import AsyncOpenAI
from core.config import settings

_use_claude = bool(settings.ANTHROPIC_API_KEY)
_anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if _use_claude else None
_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

REWRITE_SYSTEM = """You are a neuroscience-informed content strategist and copywriter. You rewrite marketing content using specific, evidence-backed psychological techniques. You write in a direct, human voice — never corporate, never buzzwordy, never AI-sounding.

Your rewrites apply the exact technique needed for the target emotion:

CURIOSITY rewrites (Loewenstein Information Gap Theory):
- Create a felt gap: reveal just enough to make them need to know more
- Start mid-thought, use "but here's the thing...", drop a surprising fact then cut off
- Add rhetorical questions that have no obvious answer
- Use "most people think X... but actually Y" structure

WARMTH rewrites (Mirror Neuron / Oxytocin activation):
- Switch to first person "I" — specificity over generality
- Use direct "you" — make the reader feel seen
- Include a micro-vulnerability: something slightly uncomfortable to admit
- Ground it in a real, specific moment not a general claim

TRUST rewrites (mPFC Credibility Processing):
- Replace round numbers with precise ones (37%, not 40%)
- Add a specific named example or concrete case
- Acknowledge a limitation — counterintuitively, this raises trust
- Lead with demonstration not claim

EXCITEMENT rewrites (Amygdala/Dopamine — High Arousal):
- Shorten sentences to under 10 words each
- Start with a strong action verb
- Use present tense, active voice
- Include the outcome state in vivid sensory terms

BOREDOM_RISK rewrites (DMN interruption):
- Cut everything that isn't earning its place
- Lead with the most surprising or valuable word
- Break long sentences into short punchy ones
- Add a pattern interrupt at the start

OUTPUT: Valid JSON only. No markdown. The improved_text must be the actual rewrite — not a description of what to do."""

REWRITE_USER_TEMPLATE = """Target emotion to boost: {target_emotion}
Current emotion scores — curiosity: {curiosity}, warmth: {warmth}, trust: {trust}, excitement: {excitement}, boredom_risk: {boredom_risk}

Original text to rewrite:
"{original_text}"

Rules:
- Same core message, similar length (±30%)
- Sound like a real human wrote it — contractions, direct voice, no fluff
- Do NOT change facts, numbers, or key claims
- Apply the {target_emotion} technique precisely

Return ONLY this JSON (no markdown, no explanation):
{{"improved_text": "your rewrite here", "emotion_delta": {{"curiosity": 0.0, "warmth": 0.0, "trust": 0.0, "excitement": 0.0, "boredom_risk": 0.0}}, "technique_used": "one sentence: what specific technique you applied and why"}}"""


async def generate_rewrites_for_drop_moments(job_id: str, db) -> list:
    res = db.table("job_segments").select("*").eq("job_id", job_id).eq("is_drop_moment", True).execute()
    rewrites = []
    for seg in res.data:
        scores = {
            "warmth": seg.get("warmth") or 0.3,
            "curiosity": seg.get("curiosity") or 0.3,
            "trust": seg.get("trust") or 0.3,
            "excitement": seg.get("excitement") or 0.3,
            "boredom_risk": seg.get("boredom_risk") or 0.7,
        }
        # Target the weakest positive emotion (not boredom_risk)
        positive = {k: v for k, v in scores.items() if k != "boredom_risk"}
        target = min(positive, key=positive.get)
        rewrite = await generate_rewrite(seg["text"], target, scores)
        rewrite_id = str(uuid.uuid4())
        db.table("rewrites").insert({
            "id": rewrite_id,
            "segment_id": seg["id"],
            "job_id": job_id,
            "original_text": seg["text"],
            "improved_text": rewrite["improved_text"],
            "target_emotion": target,
            "emotion_delta": rewrite["emotion_delta"],
        }).execute()
        rewrites.append({"segment_id": seg["id"], "original_text": seg["text"], **rewrite})
    return rewrites


async def generate_rewrite(
    original_text: str,
    target_emotion: str,
    current_scores: dict,
    emotion_targets: dict = None,
) -> dict:
    if _use_claude and _anthropic_client:
        return await _claude_rewrite(original_text, target_emotion, current_scores)
    elif _openai_client:
        return await _gpt_rewrite(original_text, target_emotion, current_scores)
    else:
        return {"improved_text": original_text, "emotion_delta": {}, "technique_used": "no AI key configured"}


async def _claude_rewrite(original_text: str, target_emotion: str, current_scores: dict) -> dict:
    prompt = REWRITE_USER_TEMPLATE.format(
        target_emotion=target_emotion,
        original_text=original_text,
        curiosity=round(current_scores.get("curiosity", 0.3), 2),
        warmth=round(current_scores.get("warmth", 0.3), 2),
        trust=round(current_scores.get("trust", 0.3), 2),
        excitement=round(current_scores.get("excitement", 0.3), 2),
        boredom_risk=round(current_scores.get("boredom_risk", 0.5), 2),
    )
    try:
        response = await _anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=REWRITE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        result = json.loads(raw[start:end])
        return {
            "improved_text": result.get("improved_text", original_text),
            "emotion_delta": result.get("emotion_delta", {}),
            "technique_used": result.get("technique_used", ""),
        }
    except Exception:
        return {"improved_text": original_text, "emotion_delta": {}, "technique_used": "error"}


async def _gpt_rewrite(original_text: str, target_emotion: str, current_scores: dict) -> dict:
    prompt = REWRITE_USER_TEMPLATE.format(
        target_emotion=target_emotion,
        original_text=original_text,
        curiosity=round(current_scores.get("curiosity", 0.3), 2),
        warmth=round(current_scores.get("warmth", 0.3), 2),
        trust=round(current_scores.get("trust", 0.3), 2),
        excitement=round(current_scores.get("excitement", 0.3), 2),
        boredom_risk=round(current_scores.get("boredom_risk", 0.5), 2),
    )
    try:
        r = await _openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=500,
        )
        result = json.loads(r.choices[0].message.content)
        return {
            "improved_text": result.get("improved_text", original_text),
            "emotion_delta": result.get("emotion_delta", {}),
            "technique_used": result.get("technique_used", ""),
        }
    except Exception:
        return {"improved_text": original_text, "emotion_delta": {}, "technique_used": "error"}
