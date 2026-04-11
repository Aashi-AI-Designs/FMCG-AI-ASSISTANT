"""
narrative_agent.py — Agent 6: Narrative Agent
----------------------------------------------
Model: Gemini 1.5 Flash (free tier)
Job:   Converts validated query results into plain-language answers.
       Receives ONLY pre-computed validated figures — never does arithmetic.
"""

import json
import pandas as pd
from config.gemini_client import chat, PRO_MODEL

SYSTEM_PROMPT = """You are a plain-language analytics communicator for an FMCG beverages company.

Write a clear, factual business answer based ONLY on the validated figures provided.
You are explaining results — you are NOT calculating them.

RULES:
1. Never invent a number. Only use figures in validated_results.
2. Maximum 5 sentences. Be concise.
3. Always include both percentage uplift AND absolute units when uplift is present.
4. Write in past tense — campaigns are historical events.
5. No jargon, no SQL, no technical terms.
6. Return ONLY a JSON object — no markdown, no code fences:
{
  "headline": "one sentence summary",
  "body": "2-4 sentence explanation",
  "caveats": ["caveat 1"],
  "formatted_answer": "full answer combining headline + body + caveats"
}
"""


def generate_narrative(validated_result: dict, enriched_context: dict, intent: str) -> dict:
    df: pd.DataFrame = validated_result.get("result_df", pd.DataFrame())
    caveats: list = validated_result.get("caveats", [])
    result_summary = df.head(30).to_dict(orient="records")

    prompt = f"""
Original question: {enriched_context.get('original_query', '')}
Intent: {intent}
Campaign: {enriched_context.get('campaign_id', 'not specified')}
Region filter: {enriched_context.get('region', 'all regions')}

Validated results (ONLY numbers you may reference):
{json.dumps(result_summary, indent=2, default=str)}

Pre-computed caveats to include if applicable:
{json.dumps(caveats)}
"""

    raw = chat(PRO_MODEL, SYSTEM_PROMPT, prompt, max_tokens=1024)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "headline": "Results retrieved successfully.",
            "body": raw[:500],
            "caveats": caveats,
            "formatted_answer": raw[:500],
        }

    result["data_rows"] = len(df)
    result["intent"] = intent
    return result


def format_for_slack(narrative: dict) -> str:
    parts = [f"*{narrative.get('headline', '')}*", ""]
    if narrative.get("body"):
        parts.append(narrative["body"])
    for caveat in narrative.get("caveats", []):
        parts.append(f"_{caveat}_")
    return "\n".join(parts).strip()


def format_for_email(narrative: dict, subject_prefix: str = "FMCG Analytics") -> dict:
    return {
        "subject": f"{subject_prefix}: {narrative.get('headline', 'Analytics Result')}",
        "body_html": f"""
<p><strong>{narrative.get('headline', '')}</strong></p>
<p>{narrative.get('body', '')}</p>
{''.join(f'<p><em>{c}</em></p>' for c in narrative.get('caveats', []))}
""",
    }


if __name__ == "__main__":
    mock_df = pd.DataFrame([{
        "campaign_id": "FEB_2025", "region": "South",
        "uplift_pct": 14.3, "promo_units": 22400,
        "baseline_sales_units": 19600, "data_completeness": 0.95,
    }])
    result = generate_narrative(
        {"status": "pass", "result_df": mock_df, "caveats": []},
        {"original_query": "Did the February campaign improve sales in the South?", "campaign_id": "FEB_2025", "region": "South"},
        "promotional_performance",
    )
    print(result["formatted_answer"])
