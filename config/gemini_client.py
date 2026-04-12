"""
now using Groq, free tier
----------------------------------------------------------
Groq free tier: 30 RPM, resets hourly — much better for development.

Get your free key at: https://console.groq.com → API Keys → Create
Add to .env:  GROQ_API_KEY=gsk_...
"""

import os
from dotenv import load_dotenv
load_dotenv()

# Model — Groq hosts Llama 3.3 70b, fully capable for this pipeline
FLASH_MODEL = "llama-3.3-70b-versatile"
PRO_MODEL   = "llama-3.3-70b-versatile"


def _get_client():
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "groq package not installed. Run:  pip install groq"
        )
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not set.\n"
            "Get a free key at https://console.groq.com\n"
            "Then add to .env:  GROQ_API_KEY=gsk_..."
        )
    return Groq(api_key=api_key)


def chat(model_name: str, system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn chat. Returns model text as string."""
    client = _get_client()
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()


def embed(text: str) -> list[float]:
    """
    Groq doesn't offer embeddings — using a local fallback with sklearn TF-IDF.
    This is only used by the vocabulary agent for fuzzy matching,
    which already has a dictionary-based fallback that works fine.
    """
    raise NotImplementedError(
        "Groq does not support embeddings. "
        "The vocabulary agent uses dictionary matching instead — this is fine."
    )