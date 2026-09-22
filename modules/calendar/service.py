"""
Content Calendar Engine — powered by GPT-4o with behavioural science posting frameworks.

Grounded in:
- Buffer / Sprout Social 2024-25 research: optimal posting windows by platform
- HubSpot State of Marketing (2025): content type performance by platform
- Cialdini (2001): reciprocity and commitment/consistency in content sequences
- Berger & Milkman (2012): weekly emotional arc — Monday motivation, mid-week curiosity,
  Friday reward-nostalgia, Sunday planning intent
- Gary Vaynerchuk's 80/20 Jab-Jab-Jab-Right-Hook: 80% value, 20% promotional
- Content pillar strategy: Educational / Entertainment / Inspirational / Promotional
"""

import json, uuid
from datetime import date
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Injected dynamically so the model never uses a stale date
_TODAY = date.today().strftime("%B %Y")

CALENDAR_SYSTEM_PROMPT = f"""You are a content strategist and behavioural scientist who builds data-driven posting calendars. Today's date is {_TODAY}.

CORE FRAMEWORK — apply to every calendar:

1. THE 80/20 CONTENT MIX (Vaynerchuk / Godin):
   - 80% value-first posts: Educational, Entertainment, Inspirational
   - 20% promotional posts: product/service CTAs
   Never cluster two promotional posts back-to-back.

2. WEEKLY EMOTION RHYTHM (Berger & Milkman, 2012 — viral content timing):
   - Monday: Motivation, aspiration, future-pacing ("start the week right")
   - Tuesday–Wednesday: Educational, curiosity, problem-solving content
   - Thursday: Social proof, case studies, trust-building
   - Friday: Entertainment, lighthearted, reward/nostalgia
   - Saturday: Inspirational, transformation stories
   - Sunday: Planning, tips, preparation-framing

3. PLATFORM PEAK WINDOWS (Buffer / Sprout Social 2025 research):
   - TikTok: 7–9 AM, 12–3 PM, 7–9 PM (user's local timezone)
   - Instagram: 6–9 AM, 11 AM–1 PM, 7–9 PM
   - YouTube: 2–4 PM, 8–11 PM (longer viewing sessions)
   - LinkedIn: 7:30–8:30 AM, 12 PM, 5–6 PM (weekdays only)
   - Twitter/X: 8 AM, 12 PM, 5 PM (news-cycle aligned)
   - Facebook: 1–4 PM weekdays, 12–1 PM Saturday
   Schedule 80% of posts within peak windows.

4. CONTENT PILLAR ROTATION (never repeat same pillar two days in a row):
   - Educational: How-to, explainer, tips, debunk myths
   - Entertainment: Behind-the-scenes, humour, storytelling, challenge
   - Inspirational: Transformation, quote+context, vulnerability
   - Promotional: Product demo, offer, testimonial, direct CTA

5. HOOK FORMULA (Loewenstein Information Gap + Pattern Interrupt):
   Every hook must either:
   a) Open a loop: state a surprising fact, then cut off before the reveal
   b) Pattern interrupt: begin with the counterintuitive conclusion
   c) Identity statement: address the exact person ("If you're a [specific person] who...")
   NEVER open with a question starting with "Have you ever" or "Do you want"

6. EMOTION TARGETING (match to day and content type):
   - curiosity: mid-week educational posts, open-loop hooks
   - excitement: Monday launches, Friday entertainment
   - trust: Thursday case studies, testimonials
   - warmth: Saturday/Sunday inspirational, behind-the-scenes

Output every field. Be specific — hooks must be actual hooks, not placeholders."""


async def generate_content_calendar(product: str, platform: str, posting_goal: str, days: int, db) -> dict:
    prompt = f"""Create a {days}-day content calendar for:
Product/Brand: {product}
Platform: {platform}
Posting Goal: {posting_goal}

Apply ALL 6 framework rules from your system prompt. For each day produce:
- day (integer 1 to {days})
- topic (specific content topic — not "post about benefits", but the actual angle)
- hook (actual opening line — not a description of what the hook should do)
- format ("talking head" | "carousel" | "short-form video" | "story" | "thread" | "newsletter" | "text post" | "live")
- best_posting_time ("7:00 AM" format, within peak windows for {platform})
- emotion_target ("curiosity" | "warmth" | "trust" | "excitement")
- content_pillar ("Educational" | "Entertainment" | "Inspirational" | "Promotional")
- why (one sentence: which framework rule drove this day's choice)

Ensure the 80/20 mix across the full {days} days. Rotate pillars — no two consecutive days same pillar.

Return JSON only:
{{
  "calendar": [
    {{
      "day": 1,
      "topic": "...",
      "hook": "...",
      "format": "...",
      "best_posting_time": "...",
      "emotion_target": "...",
      "content_pillar": "...",
      "why": "..."
    }}
  ]
}}"""

    r = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": CALENDAR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.75,
        max_tokens=4000,
    )
    result = json.loads(r.choices[0].message.content)
    calendar = result.get("calendar", [])

    calendar_id = str(uuid.uuid4())
    db.table("content_calendar").insert({
        "id": calendar_id,
        "product": product,
        "platform": platform,
        "posting_goal": posting_goal,
        "days": days,
        "calendar": calendar,
    }).execute()

    return {"calendar_id": calendar_id, "days": days, "calendar": calendar}
