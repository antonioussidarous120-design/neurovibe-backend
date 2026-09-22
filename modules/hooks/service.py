"""
Hook A/B Testing Engine — powered by GPT-4o with neuroscience attention frameworks.

Scoring grounded in the same model as the Emotion Engine:
- Loewenstein (1994): Information Gap Theory — curiosity requires felt tension between known/unknown
- Nielsen Norman Group: 3.5-second decision window — hooks are judged before content begins
- Kahneman (2011): System 1 fast processing — hooks must work without thinking
- Berger & Milkman (2012): High-arousal emotions are 34% more share-worthy
- Cialdini (2001): Pattern interrupt → commitment/consistency — once curious, people finish
"""

import json, uuid, asyncio
from datetime import date
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_TODAY = date.today().strftime("%B %Y")

HOOK_SCORING_SYSTEM = f"""You are a computational attention scientist scoring marketing hooks against validated neuroscience frameworks. Today's date is {_TODAY}.

SCORING FRAMEWORK (apply rigorously, same model as NeuroVibe Emotion Engine):

CURIOSITY (Loewenstein Information Gap Theory, 1994):
Curiosity = felt gap between current knowledge and desired knowledge. Dopamine release in nucleus accumbens.
HIGH for: open loops, unanswered questions mid-hook, surprising statistics, "but here's what nobody tells you" structures, partial reveals.
LOW for: complete information upfront, predictable opener, generic benefit statement.

WARMTH (Mirror Neuron / Oxytocin activation — Rizzolatti & Craighero, 2004):
HIGH for: first-person "I" vulnerability, direct "you" address, shared struggle, hyper-specific relatable moment.
LOW for: corporate "we", abstract claims, no personal element, passive voice.

TRUST (mPFC Credibility Processing + Cialdini, 2001):
mPFC evaluates source credibility within 200ms. HIGH for: specific imprecise numbers (37%, not 40%), named concrete examples, acknowledged limitations, proof over claim.
LOW for: vague superlatives ("amazing", "powerful"), unsupported claims, generic benefit language.

EXCITEMENT (Amygdala/HPA — dopamine + norepinephrine co-release):
HIGH for: short punchy sentences (<10 words), action verbs at sentence start, future-pacing, high stakes, sensory concrete language.
LOW for: long complex sentences, passive constructions, abstract outcomes, no urgency.

BOREDOM_RISK (Default Mode Network — Buckner et al., 2008):
Nielsen Norman Group: users make a keep/leave decision within 3.5 seconds. DMN activates when arousal falls below threshold.
HIGH boredom (dangerous) for: predictable openers, generic claims any competitor could make, weak verbs, passive voice, no novelty.
LOW boredom (good) for: novelty signal in first 5 words, pattern interrupt, strong emotional anchor.

OVERALL_SCORE (0-100):
Weighted composite: curiosity (30%) + excitement (25%) + boredom penalty ((1-boredom_risk)×25%) + trust (10%) + warmth (10%).
Score accurately — most hooks score 35-65. Reserve 80+ for genuinely exceptional hooks.

Return JSON only. Be precise — the same hook should score within ±3 points on repeated scoring."""


async def _score_hook(hook: str, platform: str) -> dict:
    prompt = f"""Score this {platform} hook using the NeuroVibe neuroscience framework:

Hook: "{hook}"

Scoring guide: 0.0-0.3 = weak/absent, 0.3-0.6 = moderate, 0.6-0.8 = strong, 0.8-1.0 = exceptional.
boredom_risk: 0.0 = fully engaging, 1.0 = certain dropout.
overall_score: 0-100 weighted composite (see system prompt formula).

JSON only: {{"curiosity":0.0,"warmth":0.0,"trust":0.0,"excitement":0.0,"boredom_risk":0.0,"overall_score":0.0}}"""

    r = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": HOOK_SCORING_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=120,
    )
    d = json.loads(r.choices[0].message.content)
    return {k: max(0.0, min(1.0 if k != "overall_score" else 100.0, float(d.get(k, 0.3))))
            for k in ["curiosity", "warmth", "trust", "excitement", "boredom_risk", "overall_score"]}


async def test_hooks(hook_a: str, hook_b: str, platform: str, db) -> dict:
    scores_a, scores_b = await asyncio.gather(
        _score_hook(hook_a, platform),
        _score_hook(hook_b, platform),
    )

    if scores_a["overall_score"] > scores_b["overall_score"]:
        winner = "A"
        margin = round(scores_a["overall_score"] - scores_b["overall_score"], 1)
    elif scores_b["overall_score"] > scores_a["overall_score"]:
        winner = "B"
        margin = round(scores_b["overall_score"] - scores_a["overall_score"], 1)
    else:
        winner = "A" if scores_a["boredom_risk"] <= scores_b["boredom_risk"] else "B"
        margin = 0.0

    winner_scores = scores_a if winner == "A" else scores_b
    loser_scores = scores_b if winner == "A" else scores_a

    explanation = _build_neuro_explanation(winner, margin, winner_scores, loser_scores)

    test_id = str(uuid.uuid4())
    db.table("hook_tests").insert({
        "id": test_id,
        "hook_a": hook_a,
        "hook_b": hook_b,
        "platform": platform,
        "hook_a_scores": scores_a,
        "hook_b_scores": scores_b,
        "winner": winner,
        "explanation": explanation,
    }).execute()

    return {
        "test_id": test_id,
        "hook_a_scores": scores_a,
        "hook_b_scores": scores_b,
        "winner": winner,
        "explanation": explanation,
        "scoring_framework": "NeuroVibe Attention Model — Loewenstein (1994), Nielsen Norman Group, Kahneman (2011)",
    }


def _build_neuro_explanation(winner: str, margin: float, winner_scores: dict, loser_scores: dict) -> str:
    parts = [f"Hook {winner} wins by {margin:.1f} points."]

    strengths = []
    if winner_scores["curiosity"] > 0.65:
        strengths.append(f"strong curiosity gap ({winner_scores['curiosity']:.2f} — Information Gap Theory)")
    if winner_scores["excitement"] > 0.65:
        strengths.append(f"high arousal excitement ({winner_scores['excitement']:.2f} — amygdala activation)")
    if winner_scores["trust"] > 0.65:
        strengths.append(f"credibility signals ({winner_scores['trust']:.2f} — mPFC processing)")
    if winner_scores["warmth"] > 0.65:
        strengths.append(f"emotional warmth ({winner_scores['warmth']:.2f} — mirror neuron activation)")
    if winner_scores["boredom_risk"] < 0.30:
        strengths.append(f"low DMN activation risk ({winner_scores['boredom_risk']:.2f})")

    if strengths:
        parts.append(f"Scientific strengths: {'; '.join(strengths)}.")

    loser_label = "B" if winner == "A" else "A"
    if loser_scores["boredom_risk"] > 0.60:
        parts.append(
            f"Hook {loser_label} carries high Default Mode Network activation risk "
            f"({loser_scores['boredom_risk']:.2f}) — Nielsen Norman Group research shows "
            f"users decide within 3.5 seconds. This hook fails to clear the arousal threshold."
        )
    if loser_scores["curiosity"] < 0.30:
        parts.append(
            f"Hook {loser_label} has near-zero curiosity gap ({loser_scores['curiosity']:.2f}) — "
            f"Loewenstein (1994): without felt tension between known/unknown, there is no pull to continue."
        )

    return " ".join(parts)
