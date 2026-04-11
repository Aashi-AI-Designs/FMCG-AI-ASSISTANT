"""
intent_agent.py — Agent 2: Intent Classifier
----------------------------------------------
Model: Gemini 1.5 Flash (free tier)
Job:   Classifies the user's question into one of four intent types.
       Returns structured JSON — never free text.
"""

import json
from config.gemini_client import chat, FLASH_MODEL

SYSTEM_PROMPT = """You are an intent classification engine for an FMCG beverages analytics assistant.

Your only job is to read the user's question and return a JSON object with:
  - "intent": one of the four intent types listed below
  - "confidence": a float 0.0-1.0
  - "reasoning": one sentence explaining why

Valid intent types:
  - promotional_performance: questions about whether a promotion drove sales growth
  - inventory_movement: questions about stock clearance or inventory changes during promotions
  - regional_comparison: questions comparing performance across regions
  - campaign_impact_by_product: questions about which SKUs or products performed best

Rules:
  - Return ONLY a JSON object. No preamble, no markdown, no code fences.
  - If confidence is below 0.6, set intent to "unclear" and add a "clarification_needed" field.
  - Never invent intents not in the list above.

Example output:
{"intent": "promotional_performance", "confidence": 0.92, "reasoning": "User asks whether a campaign improved sales."}
"""


def classify_intent(user_query: str) -> dict:
    raw = chat(FLASH_MODEL, SYSTEM_PROMPT, user_query, max_tokens=256)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "intent": "unclear",
            "confidence": 0.0,
            "reasoning": "Could not parse model output.",
            "clarification_needed": "Could you rephrase your question?",
        }

    result["raw_query"] = user_query
    return result


if __name__ == "__main__":
    tests = [
        "Did last month's campaign improve sales in the South?",
        "Which categories saw inventory reduction during the promotion?",
        "How did the North perform versus the South during the summer campaign?",
        "Which SKUs benefited most from the February price promotion?",
        "Tell me about the weather",
    ]
    for q in tests:
        r = classify_intent(q)
        print(f"Q: {q}\n→ {r['intent']} ({r['confidence']})\n")
