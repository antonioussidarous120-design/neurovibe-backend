import json, uuid
from openai import AsyncOpenAI
from core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

PLATFORM_GUIDELINES = {
    "tiktok": "Hook in first 3 seconds, casual Gen-Z tone, trending references, 15-60 seconds, ends with a CTA.",
    "instagram": "Visual-first storytelling, mix of caption and hook, 3-5 hashtag suggestions at end, 30-60 seconds.",
    "youtube": "SEO-friendly intro, longer format okay, subscribe/like CTA, value-packed structure.",
    "linkedin": "Professional tone, thought-leadership angle, value-first, ends with insight or question.",
    "twitter": "Thread format (1/n), punchy and shareable, max 280 chars per tweet, hook in tweet 1.",
    "email": "Return as object with 'subject' and 'body' keys. Personal, scannable, single clear CTA.",
}


async def convert_to_platforms(original_script: str, platform_list: list, db) -> dict:
    guidelines = "\n".join(
        f"- {p.lower()}: {PLATFORM_GUIDELINES.get(p.lower(), 'Adapt for this platform.')}"
        for p in platform_list
    )
    platforms_str = ", ".join(platform_list)

    prompt = f"""Convert this script into optimized versions for each platform listed.

Original Script:
\"\"\"{original_script}\"\"\"

Platforms to generate: {platforms_str}

Platform guidelines:
{guidelines}

Return JSON only. For email, use {{"subject": "...", "body": "..."}}. All other platforms return a string.
{{
  "versions": {{
    "<platform_name>": "..."
  }}
}}

Only include the platforms listed above."""

    r = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.75,
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
