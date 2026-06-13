import asyncio
import json
from fastapi import APIRouter
from pydantic import BaseModel
from openai import AsyncOpenAI
import anthropic
from supabase import create_client
from core.config import settings

router = APIRouter()
# Claude for script generation (better instruction-following, sharper creative writing)
claude_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
# OpenAI kept for scoring (fast, cheap, structured JSON)
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


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

## HUMAN VOICE RULES (most scripts fail here):
- Write like a real person talking on camera — raw, direct, slightly imperfect
- NEVER write a "clever" line that sounds constructed. If it reads like a tagline or an ad, rewrite it.
- Avoid overly neat analogies or metaphors that nobody would actually say out loud ("tastes like a hostage situation", "a war on your wallet") — if it's too polished, it's AI
- Use the rhythm of actual speech: short bursts, half-thoughts, the way people actually talk
- THE TEST: read every line out loud. If it would sound weird coming out of a real person's mouth on camera, cut it.
- Contractions always. Run-ons okay. Perfect grammar never.
- The goal is for viewers to think "this person gets me" — not "this is well-written copy"

## BANNED PHRASES (automatic quality failures):
Generic motivation fluff: "You're unstoppable", "Feel the energy", "The world waits", "Celebrate the new you", "Live your best life", "Chase your dreams", "Be the change", "Your journey starts", "Embrace the transformation", "Grab the momentum", "level up", "game changer", "change your life", "transform your life", "unlock your potential"
Weak openers: "Picture this:", "Ever wonder", "Have you ever", "Hey guys", "Let's talk about it", "So you want to", "Imagine if", "What if I told you"
Vague mid-script words: "imagine", "picture", "busy folks", "people like you", "everyone knows", "we all know", "things", "stuff", "something", "amazing", "incredible", "powerful", "awesome"
Generic CTAs: "Click the link", "Check out my bio", "Check out our [X]", "Learn more", "Get started today", "Grab yours", "Grab it", "Don't miss out", "Take action now", "Start your journey"
Filler transitions: "But wait", "Here's the thing", "The truth is" (overused), "And the best part", "Not only that"

## VAGUE INPUT PROTOCOL (critical):
When the product/service description is broad or one-word (e.g. "cooking", "fitness", "business", "skincare"), DO NOT write to the vague word. Instead:
1. Infer the most specific, high-pain, commercially compelling version of that product
2. Write to THAT specific version — as if the user had described it fully
Examples:
- "cooking" → "15-minute weeknight meal app for adults who eat takeout or cereal for dinner"
- "fitness" → "home workout program for people who've quit the gym 3 times"
- "skincare" → "3-step AM routine for people whose skin breaks out from stress"
- "business" → "freelance client-landing system for people billing under $2k/month"
Never mention that you inferred anything — just write the best script for the specific version you chose.

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

SCORE_PROMPT = """You are a brutally honest neuromarketing analyst. Your job is to score a social media script on 7 psychological triggers — and be ACCURATE, not generous.

Script to score:
{script}

SCORING RULES:
- Most scripts score between 45-75. A 90+ means it's genuinely exceptional.
- Each trigger must be evaluated INDEPENDENTLY based on what's actually in this specific script.
- DO NOT round to nice numbers. 67, 53, 81 are good scores. 50, 60, 70 are lazy scores.
- If the script uses a trigger well, score high. If it barely uses it or uses it poorly, score low.
- The overall_score should be a weighted average where Pattern Interrupt and Emotional Contagion count 1.5x.

TRIGGER DEFINITIONS (score based on these):
- Pattern Interrupt (0-100): Does the hook break expected patterns? Is it genuinely surprising? Score low if the opener is predictable or sounds like any other ad.
- Open Loop (0-100): Does it create a curiosity gap the viewer NEEDS to close? Low if the hook gives away the answer immediately.
- Loss Aversion (0-100): Does it frame the problem as something they're LOSING right now? Low if it only describes gain without fear of loss.
- Mirror Neurons (0-100): Does "you" language make specific people feel personally seen? Low if it's generic.
- Dopamine Reward Loop (0-100): Does it tease → build tension → partially reveal → build more? Low if it's flat with no tension arc.
- Social Proof Specificity (0-100): Does it use specific numbers/names/results that feel real? Low if it uses "most people" or no social proof.
- Emotional Contagion (0-100): Does it embed high-arousal emotion (awe, fear, excitement, anger)? Low if it's neutral or motivational-poster-generic.

Return ONLY valid JSON in this exact shape — no explanation, no markdown:
{{
  "overall_score": <weighted average as integer, be accurate not generous>,
  "trigger_scores": {{
    "Pattern Interrupt": <0-100, specific to this script>,
    "Open Loop": <0-100, specific to this script>,
    "Loss Aversion": <0-100, specific to this script>,
    "Mirror Neurons": <0-100, specific to this script>,
    "Dopamine Reward Loop": <0-100, specific to this script>,
    "Social Proof Specificity": <0-100, specific to this script>,
    "Emotional Contagion": <0-100, specific to this script>
  }},
  "trigger_fixes": {{
    "<trigger name>": "<one specific, actionable fix using the ACTUAL words from this script — not generic advice>"
  }}
}}

Only include triggers scoring below 65 in trigger_fixes. If all triggers score 65+, trigger_fixes should be empty {{}}."""


async def score_script_async(script_text: str, user_id: str | None, script_id: str | None) -> dict:
    """Score a script using gpt-4o-mini and optionally save to Supabase."""
    try:
        score_response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a brutally honest neuromarketing analyst. Return only valid JSON. Never give round numbers — be precise and script-specific."},
                {"role": "user", "content": SCORE_PROMPT.format(script=script_text)},
            ],
            temperature=0.6,
            max_tokens=600,
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

    # Generate script with Claude (better instruction-following and creative quality)
    r = await claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=900,
        temperature=1,  # Claude uses 1 as max for creative tasks
        system=NEUROSCIENCE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    script_text = r.content[0].text.strip()

    # Score concurrently — don't wait for it to block the response
    viral_score = await score_script_async(script_text, req.user_id, None)

    return {
        "script": script_text,
        "viral_score": viral_score,
    }
