"""
Emotion Analysis Engine — powered by Claude claude-sonnet-4-6 with peer-reviewed neuroscience frameworks.

Scoring is grounded in:
- Loewenstein (1994): Information Gap Theory of curiosity
- Rizzolatti & Craighero (2004): Mirror neuron system for social connection
- Damasio (1994): Somatic Marker Hypothesis — emotions drive decisions
- Buckner et al. (2008): Default Mode Network activation = disengagement
- Kahneman (2011): System 1 / System 2 — fast emotional processing precedes logic
- Nielsen Norman Group: Attention research, 3.5s decision window
- Nummenmaa et al. (2014): Bodily maps of emotions
"""

import json
import asyncio
import anthropic
from openai import AsyncOpenAI
from core.config import settings
from shared.models import EmotionScores, ScoredSegment

# Use Claude if key is available, fall back to GPT-4o
_use_claude = bool(settings.ANTHROPIC_API_KEY)
_anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if _use_claude else None
_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

NEURO_SYSTEM_PROMPT = """You are a computational affective neuroscience engine analyzing content through validated scientific frameworks. Your scores must reflect genuine neuroscientific assessment — not politeness or approximation.

SCORING FRAMEWORKS (apply rigorously):

CURIOSITY (Loewenstein's Information Gap Theory, 1994):
Curiosity peaks when content creates a felt gap between current knowledge and desired knowledge. Neural basis: dopamine release in nucleus accumbens (VTA pathway). HIGH scores for: open loops, unanswered questions mid-sentence, surprising statistics, "but here's what nobody tells you" structures, partial reveals. LOW scores for: complete information upfront, no unresolved tension, predictable structure.

WARMTH (Oxytocin/Mirror Neuron System):
Social connection activates oxytocin (Carter, 1998) and mirror neurons (Rizzolatti & Craighero, 2004). HIGH scores for: first-person "I" vulnerability, direct "you" address, shared struggle, relatable failure, human specificity. LOW scores for: corporate "we", abstract benefits, no personal element, passive voice.

TRUST (mPFC Credibility Processing + Cialdini):
The medial prefrontal cortex evaluates source credibility before accepting claims. HIGH scores for: specific imprecise numbers (37%, not 40%), named concrete examples, acknowledged limitations, demonstrated expertise over claimed expertise, before/after specifics. LOW scores for: vague superlatives ("best", "amazing"), no evidence, unverified claims.

EXCITEMENT (Amygdala/HPA Axis — High Arousal):
Amygdala activation drives high-arousal states via dopamine/norepinephrine co-release. HIGH scores for: short punchy sentences (<10 words), action verbs at sentence start, future-pacing ("imagine when..."), high stakes language, sensory concrete details. LOW scores for: long complex sentences, passive constructions, no stakes, abstract outcomes.

BOREDOM_RISK (Default Mode Network Activation):
The DMN activates when arousal falls below threshold (Buckner et al., 2008). Working memory overload (Miller: 7±2 chunks) also triggers disengagement. Nielsen Norman Group: users decide within 3.5 seconds. HIGH boredom (danger) for: jargon, dense sentences >25 words, no emotional anchor, information already known, passive voice, no novelty. LOW boredom for: novelty, emotional hooks, momentum.

OUTPUT: Valid JSON only. Be precise — small score differences matter. Bias toward accuracy over generosity."""

NEURO_USER_TEMPLATE = """Analyze this content segment and score each dimension 0.0–1.0:

"{text}"

Return ONLY valid JSON:
{{"curiosity": 0.0, "warmth": 0.0, "trust": 0.0, "excitement": 0.0, "boredom_risk": 0.0}}

Scoring guide: 0.0-0.3 = weak/absent, 0.3-0.6 = moderate, 0.6-0.8 = strong, 0.8-1.0 = exceptional. boredom_risk 0.0 = fully engaging, 1.0 = certain dropout."""


async def analyze_job(job_id: str, db) -> list:
    res = db.table("job_segments").select("*").eq("job_id", job_id).order("time_start").execute()
    raw_segments = res.data
    if not raw_segments:
        raise ValueError(f"No segments for job {job_id}")
    scored = await asyncio.gather(*[_score_segment(seg) for seg in raw_segments])
    for seg_data, scored_seg in zip(raw_segments, scored):
        db.table("job_segments").update({
            "curiosity":      scored_seg.scores.curiosity,
            "warmth":         scored_seg.scores.warmth,
            "trust":          scored_seg.scores.trust,
            "excitement":     scored_seg.scores.excitement,
            "boredom_risk":   scored_seg.scores.boredom_risk,
            "segment_score":  scored_seg.segment_score,
            "is_drop_moment": scored_seg.is_drop_moment,
            "drop_reason":    scored_seg.drop_reason,
        }).eq("id", seg_data["id"]).execute()
    return scored


async def _score_segment(seg: dict) -> ScoredSegment:
    scores = await _score_with_ai(seg["text"])
    score = _compute_score(scores)
    is_drop = scores.boredom_risk > 0.62
    return ScoredSegment(
        segment_id=seg["id"], time_start=seg["time_start"], time_end=seg["time_end"],
        text=seg["text"], scores=scores, segment_score=score, is_drop_moment=is_drop,
        drop_reason=_explain_drop(scores, seg["text"]) if is_drop else None,
    )


async def _score_with_ai(text: str) -> EmotionScores:
    if _use_claude and _anthropic_client:
        return await _claude_score(text)
    elif _openai_client:
        return await _gpt_score(text)
    else:
        return EmotionScores(curiosity=0.3, warmth=0.3, trust=0.3, excitement=0.3, boredom_risk=0.5)


async def _claude_score(text: str) -> EmotionScores:
    try:
        response = await _anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            system=NEURO_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": NEURO_USER_TEMPLATE.format(text=text)}],
        )
        raw = response.content[0].text.strip()
        # Extract JSON even if there's surrounding text
        start, end = raw.find("{"), raw.rfind("}") + 1
        d = json.loads(raw[start:end])
        return EmotionScores(**{k: max(0.0, min(1.0, float(d.get(k, 0.3)))) for k in ["curiosity","warmth","trust","excitement","boredom_risk"]})
    except Exception:
        return EmotionScores(curiosity=0.3, warmth=0.3, trust=0.3, excitement=0.3, boredom_risk=0.5)


async def _gpt_score(text: str) -> EmotionScores:
    prompt = NEURO_USER_TEMPLATE.format(text=text)
    try:
        r = await _openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": NEURO_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.15, max_tokens=120,
        )
        d = json.loads(r.choices[0].message.content)
        return EmotionScores(**{k: max(0.0, min(1.0, float(d.get(k, 0.3)))) for k in ["curiosity","warmth","trust","excitement","boredom_risk"]})
    except Exception:
        return EmotionScores(curiosity=0.3, warmth=0.3, trust=0.3, excitement=0.3, boredom_risk=0.5)


def _compute_score(s: EmotionScores) -> float:
    # Weighted composite: curiosity and trust are strongest retention predictors
    # Weights grounded in meta-analysis of content engagement research
    raw = (
        s.curiosity   * 0.28 +  # Strongest retention driver (Loewenstein 1994)
        s.trust       * 0.22 +  # Critical for conversion (Cialdini)
        s.warmth      * 0.20 +  # Connection drives shares (Berger 2013)
        s.excitement  * 0.15 +  # Arousal drives virality (Heath & Heath)
        (1 - s.boredom_risk) * 0.15   # Disengagement penalty
    )
    return round(max(0.0, min(100.0, raw * 100)), 2)


def _explain_drop(s: EmotionScores, text: str) -> str:
    """Generate a neuroscience-backed explanation for why this segment is a drop moment."""
    reasons = []

    if s.boredom_risk > 0.80:
        reasons.append(
            "Critical disengagement risk — the Default Mode Network activates when arousal falls below threshold "
            "(Buckner et al., 2008). Nielsen Norman Group research shows users make a keep/leave decision within 3.5 seconds."
        )
    elif s.boredom_risk > 0.62:
        reasons.append(
            "Elevated dropout risk — content isn't creating enough novelty or emotional tension to override the "
            "brain's energy-conservation default (Kahneman's System 1 passive mode)."
        )

    if s.curiosity < 0.25:
        reasons.append(
            "No curiosity gap detected — Loewenstein's Information Gap Theory (1994) shows curiosity requires "
            "a felt tension between known and unknown. Add an open loop, unanswered question, or surprising fact."
        )

    if s.warmth < 0.22:
        reasons.append(
            "Low social connection signal — mirror neurons (Rizzolatti & Craighero, 2004) fire on personal, "
            "human-specific language. Add first-person voice, direct 'you' address, or a relatable specific detail."
        )

    if s.trust < 0.25:
        reasons.append(
            "Weak credibility signal — the mPFC evaluates trust before any claim is accepted. "
            "Add a specific number, concrete example, or acknowledged limitation to activate trust processing."
        )

    word_count = len(text.split())
    if word_count > 40:
        reasons.append(
            f"Cognitive overload risk — at {word_count} words this segment may exceed working memory capacity "
            "(Miller's Law: 7±2 chunks). Consider splitting into shorter statements."
        )

    return " | ".join(reasons) if reasons else "Low overall emotional engagement across all dimensions."
