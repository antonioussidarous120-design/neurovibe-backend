"""
Multi-Platform Content Adapter — powered by GPT-4o with StoryBrand + JTBD frameworks.

Grounded in:
- Donald Miller (2017): StoryBrand 7-part framework — character, problem, guide, plan, CTA, success, failure
- Clayton Christensen (2016): Jobs To Be Done — people hire content to do a specific job
- Russell Brunson: Hook-Story-Offer structure for conversion-optimised content
- Platform neuroscience: Each platform activates different social motivations
  (TikTok: novelty/identity; LinkedIn: status/belonging; Instagram: aspiration/warmth)
"""

import json, uuid
from datetime import date
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_TODAY = date.today().strftime("%B %Y")

CONTENT_SYSTEM_PROMPT = f"""You are a conversion copywriter and platform strategist. Today's date is {_TODAY}.

CORE FRAMEWORKS — apply to every adaptation:

STORYBRAND (Donald Miller, 2017) — the skeleton of every piece:
  Character (the customer, not the brand) encounters a Problem (external/internal/philosophical).
  A Guide (the brand) appears with Authority + Empathy. The Guide gives a Plan.
  The CTA calls to action. Stakes: Success if they act, Failure if they don't.
  Apply this arc in every adaptation — even in 15 seconds.

JOBS TO BE DONE (Christensen, 2016):
  People don't buy products — they hire them to do a job. Identify the functional job ("get more clients"),
  emotional job ("feel confident"), and social job ("be seen as successful").
  Every piece of content must address the emotional or social job, not just the functional one.

HOOK-STORY-OFFER (Brunson):
  Hook = pattern interrupt that creates a curiosity gap.
  Story = proof that the transformation is real (specific, not abstract).
  Offer = the smallest logical next step.
  Every adaptation must have all three, compressed to fit the platform format.

PLATFORM-SPECIFIC PSYCHOLOGY:
- TikTok: Identity-formation content performs best. "I am someone who does X" → show that identity. Open with result, then reverse-reveal process. Novelty = dopamine = watch time. Max 60 words for short-form.
- Instagram: Aspiration + warmth. Lead with the transformation, not the product. Saves signal value more than likes → write something people save for later. Carousel = teach something step-by-step. 120-150 char caption max + 3-5 targeted hashtags.
- YouTube: SEO-first hook. The first 30 seconds must answer "why should I keep watching?" Promise a specific payoff. Chapters. End with subscribe framing as identity lock-in ("People who do X subscribe so they don't miss Y").
- LinkedIn: Thought leadership with vulnerability. The most-engaged LinkedIn posts open with a controversial or surprising professional opinion. Use short paragraphs (1-2 lines each). End with a question that makes comments feel easy.
- Twitter/X: Thread format. Tweet 1 = the most counterintuitive conclusion. Each tweet = one idea, completeable standalone, but unsatisfying without the next. Last tweet = the reframe.
- Email: Subject line = open loop or specific number. First sentence continues subject directly (no "Hi [name], I hope this finds you well"). 5 sentences max, one clear CTA. Never write "please" in a CTA — it signals low confidence.

OUTPUT: Adapt content for maximum impact on each platform. Be specific — write the actual adapted content, not a description of how to write it."""


PLATFORM_GUIDELINES = {
    "tiktok": "Identity-formation hook, result-first reverse-reveal, 60 words max, conversational voice.",
    "instagram": "Aspiration + warmth lead, transformation story, 120-150 char caption, 3-5 hashtags.",
    "youtube": "SEO hook answering 'why keep watching', value promise in first 30s, subscribe as identity.",
    "linkedin": "Controversial professional opinion open, short paragraphs, thought leadership + vulnerability.",
    "twitter": "Thread format (1/n), tweet 1 = counterintuitive conclusion, each tweet standalone but incomplete.",
    "email": "Open-loop subject, first sentence continues it, 5 sentences max, one direct CTA, no 'please'.",
    "facebook": "Longer narrative okay, community framing, question at end drives comments.",
}


async def convert_to_platforms(original_script: str, platform_list: list, db) -> dict:
    guidelines = "\n".join(
        f"- {p.lower()}: {PLATFORM_GUIDELINES.get(p.lower(), 'Adapt using StoryBrand + JTBD framework.')}"
        for p in platform_list
    )
    platforms_str = ", ".join(platform_list)

    prompt = f"""Apply StoryBrand, JTBD, and Hook-Story-Offer to adapt this content for each platform.

Original Script:
\"\"\"{original_script}\"\"\"

Platforms: {platforms_str}

Platform guidelines:
{guidelines}

For each platform: identify the Job To Be Done, apply StoryBrand arc, write the Hook-Story-Offer.
For email, return {{"subject": "...", "body": "..."}}. All other platforms return a string.

Return JSON only:
{{
  "versions": {{
    "<platform_name>": "..."
  }}
}}

Only include platforms listed above. Write actual content — not descriptions of what to write."""

    r = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": CONTENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=3000,
    )
    result = json.loads(r.choices[0].message.content)
    versions = result.get("versions", {})

    content_id = str(uuid.uuid4())
    db.table("platform_content").insert({
        "id": content_id,
        "original_script": original_script,
        "platform_list": platform_list,
        "versions": versions,
    }).execute()

    return {"content_id": content_id, "versions": versions}
