"""
gemini_client.py — Shared Gemini API Client
Model: gemini-2.0-flash-lite (confirmed available on your key, free tier)
"""

import os
from dotenv import load_dotenv
load_dotenv()

FLASH_MODEL = "gemini-2.0-flash-lite"
PRO_MODEL   = "gemini-2.0-flash-lite"


def _get_client():
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set.\n"
            "Get a free key at https://aistudio.google.com/app/apikey\n"
            "Then add to .env:  GEMINI_API_KEY=your_key_here"
        )
    return genai.Client(api_key=api_key)


def chat(model_name: str, system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn chat. Returns model text as string."""
    from google.genai import types
    client = _get_client()
    response = client.models.generate_content(
        model=model_name,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.1,
        ),
    )
    return response.text.strip()


def embed(text: str) -> list[float]:
    """Embed text using free embedding model."""
    client = _get_client()
    result = client.models.embed_content(
        model="text-embedding-004",
        contents=text,
    )
    return result.embeddings[0].values