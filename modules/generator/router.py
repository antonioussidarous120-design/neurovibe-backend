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


@router.post("/script")
async def generate_script(req: ScriptRequest):
    prompt = f"""You are an expert viral content writer. Write a high-converting {req.platform} script for:
Product/Topic: {req.product}
Target Emotion: {req.emotion}

Format your response EXACTLY like this (use these exact labels):
HOOK: [1-2 punchy opening sentences that stop the scroll]
BODY: [3-5 sentences delivering the core message with storytelling]
CTA: [1 clear call to action]
CAPTION: [A short social media caption with 3-5 relevant hashtags]

Make it feel authentic, not salesy. Use the energy and style of top {req.platform} creators in 2026."""

    r = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are an expert viral content strategist specializing in short-form content that drives emotional engagement and conversions."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=600,
    )
    return {"script": r.choices[0].message.content.strip()}
