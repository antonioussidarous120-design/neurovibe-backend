import json, uuid
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_content_calendar(product: str, platform: str, posting_goal: str, days: int, db) -> dict:
    prompt = f"""Create a {days}-day content calendar for:
Product: {product}
Platform: {platform}
Posting Goal: {posting_goal}

For each day produce:
- day (integer, 1 to {days})
- topic (the content topic)
- hook (opening line or video hook)
- format (e.g. "talking head", "carousel", "short-form video", "story", "thread", "newsletter")
- best_posting_time (e.g. "7:00 AM", "12:00 PM", "6:30 PM")
- emotion_target (one of: curiosity, warmth, trust, excitement)

Return JSON only:
{{
  "calendar": [
    {{
      "day": 1,
      "topic": "...",
      "hook": "...",
      "format": "...",
      "best_posting_time": "...",
      "emotion_target": "..."
    }}
  ]
}}"""

    r = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.8,
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
