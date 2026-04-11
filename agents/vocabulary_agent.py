"""
vocabulary_agent.py — Agent 3: Enrichment / Vocabulary Agent
--------------------------------------------------------------
Model: Gemini 1.5 Flash (free tier)
Job:   Translates FMCG trade terms to canonical DB field names
       and extracts structured entities (campaign_id, region, etc.)
"""

import json
import re
from difflib import SequenceMatcher
from typing import Optional

from config.gemini_client import chat, FLASH_MODEL
from config.semantic_config import VOCABULARY, CAMPAIGN_REGISTRY

SYSTEM_PROMPT = """You are a vocabulary resolution engine for an FMCG beverages analytics assistant.

Extract structured entities from the user's question and map FMCG trade terms to canonical database values.
Return ONLY a JSON object — no markdown, no code fences, no preamble.

{
  "campaign_id": string or null,
  "region": string or null,
  "category": string or null,
  "sku_code": string or null,
  "time_reference": string or null,
  "resolved_terms": {},
  "ambiguities": []
}

Known campaign IDs: FEB_2025, SUMMER_2025, WINTER_2024, Q1_2025
Known regions: North, South, East, West, Central
Known categories: Carbonates, Juices, Energy, Water, RTD Tea, Sports
Time references: LAST_MONTH, LAST_WEEK, THIS_MONTH map to dynamic windows.
"""


def _fuzzy_match(term: str, vocab: dict, threshold: float = 0.75) -> Optional[str]:
    term_lower = term.lower().strip()
    if term_lower in vocab:
        return vocab[term_lower]
    best_score, best_match = 0.0, None
    for key, value in vocab.items():
        score = SequenceMatcher(None, term_lower, key).ratio()
        if score > best_score:
            best_score, best_match = score, value
    return best_match if best_score >= threshold else None


def enrich_query(user_query: str, intent: str) -> dict:
    # Step 1: free fuzzy match against vocabulary dict
    pre_resolved = {}
    for token in re.split(r"[\s,]+", user_query.lower()):
        match = _fuzzy_match(token, VOCABULARY)
        if match:
            pre_resolved[token] = match

    # Step 2: Gemini extracts structured entities
    prompt = f"Question: {user_query}\nIntent type: {intent}"
    raw = chat(FLASH_MODEL, SYSTEM_PROMPT, prompt, max_tokens=512)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        extracted = json.loads(raw)
    except json.JSONDecodeError:
        extracted = {
            "campaign_id": None, "region": None, "category": None,
            "sku_code": None, "time_reference": None,
            "resolved_terms": {}, "ambiguities": ["Failed to parse model output"],
        }

    extracted["resolved_terms"].update(pre_resolved)

    # Resolve time references to campaign_ids
    time_ref = extracted.get("time_reference")
    if time_ref and time_ref in CAMPAIGN_REGISTRY:
        entry = CAMPAIGN_REGISTRY[time_ref]
        if entry.get("campaign_id") and not extracted.get("campaign_id"):
            extracted["campaign_id"] = entry["campaign_id"]

    extracted["original_query"] = user_query
    extracted["intent"] = intent
    return extracted


if __name__ == "__main__":
    tests = [
        ("Did last month's campaign improve sales in the South?", "promotional_performance"),
        ("How did the North perform versus the South during the summer campaign?", "regional_comparison"),
    ]
    for query, intent in tests:
        r = enrich_query(query, intent)
        print(f"Q: {query}\n→ campaign={r.get('campaign_id')} region={r.get('region')}\n")
