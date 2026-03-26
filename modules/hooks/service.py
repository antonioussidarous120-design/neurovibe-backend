import json, uuid, asyncio
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def _score_hook(hook: str, platform: str) -> dict:
    prompt = f"""Score this marketing hook for {platform} (0.0 to 1.0 each):
- curiosity: does it provoke intrigue or open a loop?
- warmth: emotional connection, empathy?
- trust: credibility, specificity?
- excitement: energy, motivation to keep watching/reading?
- boredom_risk: likelihood of losing the audience? (1.0 = certain skip)
- overall_score: weighted effectiveness score (0-100)

Hook: "{hook}"

JSON only: {{"curiosity":0.0,"warmth":0.0,"trust":0.0,"excitement":0.0,"boredom_risk":0.0,"overall_score":0.0}}"""

    r = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
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

    # Pick winner by overall_score; tie-break by lower boredom_risk
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

    explanation = _build_explanation(winner, margin, winner_scores, loser_scores)

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
    }


def _build_explanation(winner: str, margin: float, winner_scores: dict, loser_scores: dict) -> str:
    parts = [f"Hook {winner} wins by {margin:.1f} points."]

    strengths = []
    if winner_scores["curiosity"] > 0.7:
        strengths.append("high curiosity")
    if winner_scores["excitement"] > 0.7:
        strengths.append("strong excitement")
    if winner_scores["trust"] > 0.7:
        strengths.append("credibility")
    if winner_scores["warmth"] > 0.7:
        strengths.append("emotional warmth")
    if winner_scores["boredom_risk"] < 0.3:
        strengths.append("low boredom risk")

    if strengths:
        parts.append(f"It scores well on: {', '.join(strengths)}.")

    if loser_scores["boredom_risk"] > 0.6:
        parts.append(f"Hook {'B' if winner == 'A' else 'A'} carries high boredom risk ({loser_scores['boredom_risk']:.2f}), likely to lose the audience.")

    return " ".join(parts)
