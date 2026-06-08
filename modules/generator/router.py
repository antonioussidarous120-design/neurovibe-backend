import asyncio
import json
from fastapi import APIRouter
from pydantic import BaseModel
from openai import AsyncOpenAI
from supabase import create_client
from core.config import settings

router = APIRouter()
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def get_supabase():
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY or settings.SUPABASE_ANON_KEY
    return create_client(settings.SUPABASE_URL, key)


class ScriptRequest(BaseModel):
    product: str
    platform: str
    emotion: str
    user_id: str | None = None


NEUROSCIENCE_SYSTEM_PROMPT = """You are NeuroVibe — an elite content strategist trained in neuroscience, behavioral psychology, and viral platform intelligence. You write scripts that are neurologically engineered to stop scrolls, trigger emotional responses, and drive action.

## THE 7 NEUROSCIENCE TRIGGERS YOU APPLY TO EVERY SCRIPT:
1. PATTERN INTERRUPT (0-3 sec) — Break expected patterns. Unexpected = brain pays attention. Use contrast, shock, paradox, or direct challenge. NEVER open with questions like "Ever wonder..." or "Have you ever..." or "Picture this:"
2. OPEN LOOP — Create a curiosity gap the brain NEEDS to close. Never answer the hook's question in the hook itself.
3. LOSS AVERSION — Fear of missing out is 2.5x stronger than desire for gain (Kahneman). Frame benefits as things they're LOSING by not acting.
4. MIRROR NEURONS — Use "you" language + hyper-specific relatable scenarios. When people see themselves in the content, they feel it physically.
5. DOPAMINE REWARD LOOP — Tease → build tension → partial reveal → build more → payoff. This keeps people watching.
6. SOCIAL PROOF SPECIFICITY — "78% of people" triggers truth-detection more than "most people". Specific numbers = credibility.
7. EMOTIONAL CONTAGION — High-arousal emotions spread virally: awe, anger, fear, excitement. Embed at least one per script.

## PLATFORM-SPECIFIC TREND FORMATS (2025-2026):

TIKTOK:
- Reverse reveal: show the RESULT first, then how — brain demands explanation
- "Nobody tells you [truth]" — pattern interrupt + open loop
- "I spent [specific amount/time] doing X. Here's what actually happened"
- "The [industry] doesn't want you to know this" — conspiracy framing = max curiosity
- Controversy bait: state an opinion that makes people comment to agree or disagree
- Hook MUST work without sound (40% watch muted) — make first line visual-text friendly
- Optimal: 21-34 seconds. End with comment CTA or share trigger.

INSTAGRAM REELS:
- "Save this if you want [specific result]" — saves = algorithm's highest signal
- Tutorial format: lead with transformation, not process
- Problem → Agitate → Solve in under 30 seconds
- Behind-the-scenes authenticity outperforms polished content

YOUTUBE SHORTS:
- Strong curiosity hook in first 5 seconds — make them need to know what comes next
- Clear beginning, middle, end arc
- Subscribe CTA at the end

EMAIL:
- Subject line is the hook — open loop or specific benefit
- First line continues the subject's promise immediately
- 5 lines max, one clear CTA

## SCRIPT QUALITY RULES:
- Every sentence earns the right to the next — no filler
- Use sentence fragments. Short punches. Like this. Vary the rhythm.
- Build emotional intensity line by line — NEVER plateau or default to vague language
- End lines on strong, concrete words (recency effect — last word is remembered most)
- CTA must feel like natural emotional conclusion, not a request
- MAINTAIN SPECIFICITY THROUGHOUT — if your hook is specific, every line after must be equally specific. Never trade specificity for vague motivation mid-script.

## BANNED PHRASES (automatic quality failures):
Generic motivation fluff: "You're unstoppable", "Feel the energy", "The world waits", "Celebrate the new you", "Live your best life", "Chase your dreams", "Be the change", "Your journey starts", "Embrace the transformation", "Grab the momentum", "level up", "game changer", "change your life", "transform your life", "unlock your potential"
Weak openers: "Picture this:", "Ever wonder", "Have you ever", "Hey guys", "Let's talk about it", "So you want to", "Imagine if", "What if I told you"
Vague mid-script words: "imagine", "picture", "busy folks", "people like you", "everyone knows", "we all know", "things", "stuff", "something", "amazing", "incredible", "powerful", "awesome"
Generic CTAs: "Click the link", "Check out my bio", "Check out our [X]", "Learn more", "Get started today", "Grab yours", "Grab it", "Don't miss out", "Take action now", "Start your journey"
Filler transitions: "But wait", "Here's the thing", "The truth is" (overused), "And the best part", "Not only that"

## SPECIFICITY RULES (non-negotiable):
- NEVER use vague audience descriptors ("busy people", "everyone", "most people") — name the EXACT person ("28-year-old marketing manager", "new mom who hasn't slept in weeks")
- NEVER use vague results ("see results", "feel better", "make money") — use exact numbers and timeframes ("lost 11 lbs in 3 weeks", "added $2,300 in 6 days")
- NEVER use vague product descriptions — name the mechanism ("the 4-ingredient formula", "the 12-minute protocol", "the one swap that cuts cravings by 60%")
- If you catch yourself writing a line any other product could say, delete it and rewrite with THIS product's unique angle

## THE SPECIFICITY TEST — before writing each line, ask:
- Can I make this more specific? (add a number, name, timeframe, or result)
- Is this something only THIS product can say, or could any product say it?
- Does this line make someone feel something, or just fill space?
If a line fails any of these, rewrite it.

## STRONG CTA FORMULA:
- Reference others already winning: "While you're reading this, [X people] are on Day [X]"
- Make the action feel tiny: "[Product] — [small time commitment] from now, you've already started"
- Identity lock-in: "People who [identity] don't wait. [Action]."
- Loss frame close: "Every [time unit] you don't [action] is another [specific loss]"
"""

SCORE_PROMPT = """You are a neuromarketing analyst scoring a social media script on 7 psychological triggers.

Script to score:
{script}

Score each trigger 0-100 based on how effectively the script uses it. Be honest and critical.

Return ONLY valid JSON in this exact shape — no explanation, no markdown:
{{
  "overall_score": <weighted average, 0-100 integer>,
  "trigger_scores": {{
    "Pattern Interrupt": <0-100>,
    "Open Loop": <0-100>,
    "Loss Aversion": <0-100>,
    "Mirror Neurons": <0-100>,
    "Dopamine Reward Loop": <0-100>,
    "Social Proof Specificity": <0-100>,
    "Emotional Contagion": <0-100>
  }},
  "trigger_fixes": {{
    "<trigger name>": "<one specific, actionable 1-line fix for this exact script>"
  }}
}}

Only include triggers scoring below 60 in trigger_fixes. If all triggers score 60+, trigger_fixes should be empty {{}}."""


async def score_script_async(script_text: str, user_id: str | None, script_id: str | None) -> dict:
    """Score a script using gpt-4o-mini and optionally save to Supabase."""
    try:
        score_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise neuromarketing analyst. Return only valid JSON."},
                {"role": "user", "content": SCORE_PROMPT.format(script=script_text)},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        score_data = json.loads(score_response.choices[0].message.content)

        # Save to Supabase asynchronously (non-blocking)
        if user_id or script_id:
            try:
                db = get_supabase()
                db.table("viral_scores").insert({
                    "script_id": script_id,
                    "user_id": user_id,
                    "overall_score": score_data.get("overall_score", 0),
                    "trigger_scores": score_data.get("trigger_scores", {}),
                    "trigger_fixes": score_data.get("trigger_fixes", {}),
                }).execute()
            except Exception:
                pass  # Non-fatal

        return score_data
    except Exception:
        # Return neutral score if scoring fails — never block the main response
        return {
            "overall_score": 0,
            "trigger_scores": {},
            "trigger_fixes": {},
        }


@router.post("/script")
async def generate_script(req: ScriptRequest):
    # Fetch brand profile if user_id provided
    brand_block = ""
    if req.user_id:
        try:
            db = get_supabase()
            res = db.table("brand_profiles").select("*").eq("user_id", req.user_id).maybe_single().execute()
            if res.data:
                bp = res.data
                parts = []
                if bp.get("niche"):
                    parts.append(f"- Niche: {bp['niche']}")
                if bp.get("audience"):
                    parts.append(f"- Target audience: {bp['audience']}")
                if bp.get("tone"):
                    parts.append(f"- Brand tone: {bp['tone']}")
                if bp.get("voice_notes"):
                    parts.append(f"- Voice rules: {bp['voice_notes']}")
                if parts:
                    brand_block = "\n\nBRAND CONTEXT (apply to every line — makes this feel like THEIR brand, not a template):\n" + "\n".join(parts) + "\n"
        except Exception:
            pass  # Non-fatal — generate without brand context

    emotion_context = {
        "Excitement": "excitement/hype — energy, momentum, forward motion, big promises, celebratory tone",
        "Trust": "trust/credibility — specific results, social proof, authority signals, authentic vulnerability, calm confidence",
        "Humor": "wit and relatability — clever observations, not cheesy jokes. Smart, not slapstick. The humor should make them feel understood, not patronized.",
        "Motivation": "inspiration — transformation stories, before/after, possibility thinking, emotional peak moments, direct challenge",
        "Confidence": "bold confidence — power words, identity-based framing, make them feel like winners for choosing this",
        "FOMO": "loss aversion / urgency — real consequences of inaction, others already winning, time-sensitive stakes",
    }.get(req.emotion, req.emotion)

    # Platform-specific output format
    if req.platform == "Email":
        format_instructions = """CRITICAL: This is an EMAIL. Use ONLY this exact format — no HOOK/CAPTION labels:

SUBJECT: [6-10 words. Open loop or shocking specific stat. Makes them NEED to open it.]

BODY:
[Line 1: Directly continues the subject line's promise. Specific fact or result.]
[Line 2: Agitate — what they're missing or losing right now. Use "you".]
[Line 3: The mechanism — what makes this different/unique. Specific.]
[Line 4: Social proof with a number. "X people already did Y in Z days."]
[Line 5: Make the action feel inevitable, not optional.]

CTA: [One button/link text + 1 sentence of context. Loss aversion or identity. NOT "Click here" or "Learn more".]

SELF-CHECK: Is every line as specific as line 1? Replace any vague motivation with concrete facts."""
    elif req.platform == "Facebook Ad":
        format_instructions = """CRITICAL: This is a FACEBOOK/INSTAGRAM AD. Use this exact format:

HOOK: [Scroll-stopping headline. Specific result or bold claim. 5-10 words.]

BODY: [3-4 lines. Lead with biggest benefit. Add social proof. Remove main objection.]

CTA: [Button text + urgency line. Direct. Specific. NOT "Learn more" or "Click here".]

CAPTION: [N/A]

SELF-CHECK: Does every line pass the specificity test? Replace vague lines before submitting."""
    else:
        format_instructions = """Format your response with EXACTLY these labels on separate lines:

HOOK: [2-8 words max. Pattern interrupt. Creates open loop. Stops scroll cold. NO questions, NO "Picture this", NO "Ever wonder". Must be something only this specific product can say.]

BODY: [3-5 punchy lines. Agitate pain/desire. Use "you". Include at least ONE specific number, result, or timeframe. Build emotional intensity — NEVER default to vague motivation. Every line must be as specific as the hook.]

CTA: [1-2 lines. Feels like relief, not a request. Tied to the emotional journey. Use loss aversion or identity language. Make the action feel small and immediate. NEVER "Click the link", "Check out", or "Celebrate the new you".]

CAPTION: [120-150 chars. First 5 words magnetic. Core value + 3-5 hashtags: 1 mega, 1 niche, 1 branded.]

SELF-CHECK before finalizing: scan your output for any banned phrases or vague motivation lines. Replace them with specific, concrete alternatives."""

    user_prompt = f"""Create a neuroscience-engineered script for:

PRODUCT/SERVICE: {req.product}
PLATFORM: {req.platform}
TARGET EMOTION: {emotion_context}
{brand_block}
Apply ALL 7 neuroscience triggers. Be SPECIFIC and UNEXPECTED. Every line must earn its place.

{format_instructions}"""

    # Generate script and score it concurrently
    generate_task = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": NEUROSCIENCE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=700,
    )

    r = await generate_task
    script_text = r.choices[0].message.content.strip()

    # Score concurrently — don't wait for it to block the response
    viral_score = await score_script_async(script_text, req.user_id, None)

    return {
        "script": script_text,
        "viral_score": viral_score,
    }
