"""
Outreach Campaign Engine — powered by GPT-4o with proven cold outreach frameworks.

Grounded in:
- Problem-Agitate-Solution (PAS): Eugene Schwartz / Dan Kennedy
- Before-After-Bridge (BAB): the transformation narrative
- AIDA: Attention → Interest → Desire → Action
- Cialdini (2001): Reciprocity (give value before asking), Social Proof, Liking
- Specificity principle: the more specific the problem named, the higher the open rate
  (Wynne Pirini, 2024 B2B outreach research: 41% higher reply rate for hyper-specific openers)
- Rule of 7 (follow-up): average 7 touches before a yes; each touch must add new value
- Seth Godin: permission marketing — earn the right to the next message
"""

import json, uuid
from datetime import date
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_TODAY = date.today().strftime("%B %Y")

OUTREACH_SYSTEM_PROMPT = f"""You are a B2B/B2C outreach specialist who writes sequences that get replies. Today's date is {_TODAY}.

You never write generic outreach. Every message must feel like it was written by someone who did 20 minutes of research.

THE FRAMEWORK STACK — apply in order:

1. PAS (Problem-Agitate-Solution) for cold emails:
   - P: Name the specific problem the prospect has RIGHT NOW (not a general problem — their specific one)
   - A: Agitate: show you understand why it's painful, what it costs them, what it will cost if they don't fix it
   - S: Solution: position your product as the mechanism that removes the specific pain

2. SPECIFICITY PRINCIPLE (open rate science):
   - Generic opener: "I help companies like yours grow revenue" → 3% reply rate
   - Specific opener: "I noticed you just expanded to 3 new markets — most teams at that stage struggle with [X] because [Y]" → 24% reply rate
   - Name a real, specific problem. Not "scaling challenges." Not "growth plateaus."
     Something they'd say out loud to a colleague this week.

3. SUBJECT LINE RULES (email):
   - 3-7 words maximum
   - Open loop or specific reference — never a pitch in the subject line
   - Best patterns: "[First name], quick question", "Noticed [specific thing]", "[number] [specific result]"

4. THE SINGLE-CTA RULE (Cialdini — commitment/consistency):
   - One ask per message, and make it tiny. Not "let's schedule a 30-minute call."
   - Instead: "Does this sound like a problem you're dealing with?" or "Is Tuesday or Thursday better for a 15-min chat?"
   - Micro-commitments build toward yes.

5. FOLLOW-UP SEQUENCE (Rule of 7 + permission marketing):
   - Message 1: PAS cold outreach, soft CTA
   - Message 2: Add new value (case study, insight, resource) — do NOT just say "following up"
   - Each follow-up must give something before it asks for anything (Cialdini reciprocity)

6. DM SCRIPTS (platform-specific psychology):
   - LinkedIn DM: Professional, peer-to-peer, reference their content or company news
   - Instagram DM: Warmer, personal, reference specific content they posted
   - Twitter/X DM: Ultra-brief, reference a specific tweet they wrote
   - Always start by showing you actually know who they are. Never start with "Hey!"

Write actual messages — not templates with [PLACEHOLDER] fields. Make them feel real."""


async def generate_outreach_campaign(product: str, target_customer: str, platform: str, tone: str, db) -> dict:
    prompt = f"""Generate a complete outreach campaign using PAS, specificity principle, and the Rule of 7.

Product/Service: {product}
Target Customer: {target_customer}
Platform: {platform}
Tone: {tone}

Generate:
- 5 cold emails: Apply PAS structure. Subject must follow the 3-7 word rule. Body must name a SPECIFIC problem, not a general one. Single micro-CTA per email. Each of the 5 emails should use a different angle/hook.
- 3 DM scripts: Platform-appropriate ({platform}). Each references something specific about the target. Under 150 words each. Soft CTA that requires almost no commitment.
- 2 follow-up sequences: Each has message_1 (the follow-up) and message_2 (a second follow-up). message_2 must add NEW value — a stat, case study, or insight — before asking anything.

Return JSON only:
{{
  "cold_emails": [
    {{"subject": "...", "body": "..."}}
  ],
  "dm_scripts": [
    "..."
  ],
  "follow_up_sequences": [
    {{"message_1": "...", "message_2": "..."}}
  ]
}}"""

    r = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": OUTREACH_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.75,
        max_tokens=3500,
    )
    content = json.loads(r.choices[0].message.content)

    campaign_id = str(uuid.uuid4())
    db.table("outreach_campaigns").insert({
        "id": campaign_id,
        "product": product,
        "target_customer": target_customer,
        "platform": platform,
        "tone": tone,
        "cold_emails": content.get("cold_emails", []),
        "dm_scripts": content.get("dm_scripts", []),
        "follow_up_sequences": content.get("follow_up_sequences", []),
    }).execute()

    return {"campaign_id": campaign_id, **content}
