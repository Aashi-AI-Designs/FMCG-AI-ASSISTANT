"""
query_agent.py — Agent 4: Query Builder
-----------------------------------------
Model: Gemini 1.5 Flash (free tier)
Job:   Converts enriched context into parameterised SQL, validates it,
       executes it, and returns raw data. Never generates numbers.
"""

import json
import re
from typing import Optional

import pandas as pd

from config.gemini_client import chat, PRO_MODEL
from config.semantic_config import ALLOWED_TABLES
from data.db import execute_query

SYSTEM_PROMPT = f"""You are a SQL query builder for an FMCG beverages analytics system.

Generate READ-ONLY SQLite-compatible SQL. Return ONLY a JSON object — no markdown, no code fences:
{{"sql": "<your SQL here>", "reasoning": "<one sentence>"}}

ALLOWED TABLES ONLY (no others):
{json.dumps(ALLOWED_TABLES)}

RULES:
1. Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER.
2. Always include a WHERE clause.
3. Always alias aggregated columns clearly.
4. For uplift, always return BOTH percentage AND absolute units.
5. Use NULLIF to avoid division by zero.
6. Do not access any table not in the allowed list above.

MART SCHEMAS:
promo_performance_mart: campaign_id, week_number, region, sku_code, sku_name,
  category, baseline_sales_units, promo_sales_units, uplift_pct, data_completeness

inventory_movement_mart: campaign_id, week_number, category,
  prior_week_units_cleared, promo_week_units_cleared, inventory_delta_pct

regional_summary_mart: campaign_id, region, baseline_sales_units,
  promo_sales_units, regional_uplift_pct, data_completeness
"""


def _validate_sql_structure(sql: str) -> tuple[bool, str]:
    sql_upper = sql.upper()
    for bad_kw in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]:
        if re.search(rf"\b{bad_kw}\b", sql_upper):
            return False, f"Forbidden keyword detected: {bad_kw}"
    if "WHERE" not in sql_upper:
        return False, "SQL must contain a WHERE clause — no full table scans allowed."
    for table in re.findall(r"FROM\s+(\w+)", sql_upper):
        if table.lower() not in [t.lower() for t in ALLOWED_TABLES]:
            return False, f"Forbidden table reference: {table}"
    return True, "OK"


def build_and_execute_query(enriched_context: dict) -> dict:
    context_summary = f"""
Intent: {enriched_context.get('intent', '')}
Campaign ID: {enriched_context.get('campaign_id') or 'not specified'}
Region filter: {enriched_context.get('region') or 'all regions'}
Category filter: {enriched_context.get('category') or 'all categories'}
SKU code filter: {enriched_context.get('sku_code') or 'all SKUs'}
Original question: {enriched_context.get('original_query', '')}
"""

    raw = chat(PRO_MODEL, SYSTEM_PROMPT, context_summary, max_tokens=1024)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(raw)
        sql = parsed.get("sql", "").strip()
        reasoning = parsed.get("reasoning", "")
    except json.JSONDecodeError:
        match = re.search(r"```sql\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1).strip()
            reasoning = "Extracted from code block"
        else:
            return {"sql": "", "result_df": pd.DataFrame(), "rows": 0,
                    "validation_status": "error", "error": "Could not parse SQL from model output."}

    valid, msg = _validate_sql_structure(sql)
    if not valid:
        return {"sql": sql, "result_df": pd.DataFrame(), "rows": 0,
                "validation_status": "blocked", "error": msg}

    try:
        result_df = execute_query(sql)
        return {"sql": sql, "reasoning": reasoning, "result_df": result_df,
                "rows": len(result_df), "validation_status": "ok", "error": None}
    except Exception as e:
        return {"sql": sql, "result_df": pd.DataFrame(), "rows": 0,
                "validation_status": "execution_error", "error": str(e)}


if __name__ == "__main__":
    context = {
        "intent": "promotional_performance", "campaign_id": "FEB_2025",
        "region": "South", "category": None, "sku_code": None,
        "original_query": "Did the February campaign improve sales in the South?",
    }
    result = build_and_execute_query(context)
    print(f"SQL:\n{result['sql']}\nStatus: {result['validation_status']}")
    if not result["result_df"].empty:
        print(result["result_df"].head())
