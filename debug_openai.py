"""Quick debug script - paste into backend folder and run to test OpenAI connection"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import settings
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def test():
    print(f"\nOpenAI key starts with: {settings.OPENAI_API_KEY[:8]}...")
    print(f"Model: {settings.OPENAI_MODEL}")
    print("\nTesting GPT-4o call...")
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": "Return this JSON exactly: {\"test\": true}"}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=50,
        )
        print(f"✓ SUCCESS: {response.choices[0].message.content}")
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")

asyncio.run(test())
