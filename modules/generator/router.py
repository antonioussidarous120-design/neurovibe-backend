from fastapi import APIRouter
from pydantic import BaseModel
from openai import AsyncOpenAI
from core.config import settings

router = APIRouter()
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class ScriptRequest(BaseModel):
    product: str
    platform: str
    emotion: str


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

## BANNED PHRASES (never write these — they are automatic quality failures):
Generic motivation fluff: "You're unstoppable", "Feel the energy", "The world waits", "Celebrate the new you", "Live your best life", "Chase your dreams", "Be the change", "Your journey starts", "Embrace the transformation"
Weak openers: "Picture this:", "Ever wonder", "Have you ever", "Hey guys", "Let's talk about it", "So you want to"
Generic CTAs: "Click the link", "Check out my bio", "Check out our [X]", "Learn more", "Get started today" (too vague)
Filler transitions: "But wait", "Here's the thing", "The truth is" (overused)

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


@router.post("/script")
async def generate_script(req: ScriptRequest):
    platform_context = {
        "TikTok": "TikTok (15-60 sec, vertical video, Gen Z + Millennial, fast-paced, algorithm rewards completion rate + shares + comments, 40% watched muted)",
        "Instagram Reels": "Instagram Reels (15-90 sec, vertical video, visual-forward, saves + shares boost algorithm, mix of polished and authentic)",
        "YouTube Shorts": "YouTube Shorts (under 60 sec, higher intent audience, subscribers matter, drives long-form views)",
        "Email": "Email marketing (subject line = hook, 5 lines max body, single clear CTA, professional but human tone)",
        "Facebook Ad": "Facebook/Instagram Ad (scroll-stopping headline, benefit-led body, social proof, direct CTA)",
    }.get(req.platform, req.platform)

    emotion_context = {
        "Excitement": "excitement/hype — energy, momentum, forward motion, big promises, celebratory tone",
        "Trust": "trust/credibility — specific results, social proof, authority signals, authentic vulnerability, calm confidence",
        "Humor": "wit and relatability — clever observations, not cheesy jokes. Smart, not slapstick. The humor should make them feel understood, not patronized.",
        "Motivation": "inspiration — transformation stories, before/after, possibility thinking, emotional peak moments, direct challenge",
        "Confidence": "bold confidence — power words, identity-based framing, make them feel like winners for choosing this",
        "FOMO": "loss aversion / urgency — real consequences of inaction, others already winning, time-sensitive stakes",
    }.get(req.emotion, req.emotion)

    user_prompt = f"""Create a neuroscience-engineered script for:

PRODUCT/SERVICE: {req.product}
PLATFORM: {platform_context}
TARGET EMOTION: {emotion_context}

Apply ALL 7 neuroscience triggers. Use current {req.platform} trend formats. Be SPECIFIC and UNEXPECTED — make this stop someone mid-scroll.

Format your response with EXACTLY these labels on separate lines:

HOOK: [2-8 words max. Pattern interrupt. Creates open loop. Stops scroll cold. NO questions, NO "Picture this", NO "Ever wonder". Must be something only this specific product can say.]

BODY: [3-5 punchy lines. Agitate pain/desire. Use "you". Include at least ONE specific number, result, or timeframe. Build emotional intensity — NEVER default to vague motivation ("you're unstoppable", "feel the energy"). Every line must be as specific as the first line.]

CTA: [1-2 lines. Feels like relief, not a request. Tied to the emotional journey. Use loss aversion or identity language. Make the action feel small and immediate. NEVER "Click the link", "Check out", or "Celebrate the new you".]

CAPTION: [120-150 chars. First 5 words magnetic. Core value + 3-5 hashtags: 1 mega, 1 niche, 1 branded.]

SELF-CHECK before finalizing: scan your output for any banned phrases or vague motivation lines. If you find any, replace them with specific, concrete alternatives before submitting."""

    r = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": NEUROSCIENCE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=700,
    )
    return {"script": r.choices[0].message.content.strip()}
