import json, uuid
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_outreach_campaign(product: str, target_customer: str, platform: str, tone: str, db) -> dict:
    prompt = f"""You are an expert marketing copywriter. Generate outreach content for:
Product: {product}
Target Customer: {target_customer}
Platform: {platform}
Tone: {tone}

Generate exactly:
- 5 cold emails (each with subject line and body)
- 3 DM scripts (direct message scripts)
- 2 follow-up sequences (each with 2 messages: message_1 and message_2)

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
            {"role": "system", "content": "You are an expert marketing AI assistant. Today's date is March 2026. Use the most current marketing strategies and platform trends."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_tokens=3000,
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
