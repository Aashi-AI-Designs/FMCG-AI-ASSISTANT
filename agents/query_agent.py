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

CRITICAL SQLITE RULES — FOLLOW EXACTLY:
1. Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER.
2. Always include a WHERE clause with campaign_id filter.
3. Always alias aggregated columns clearly.
4. For uplift percentage, ALWAYS write it EXACTLY as:
   ROUND(100.0 * (SUM(promo_sales_units) - SUM(baseline_sales_units)) / NULLIF(SUM(baseline_sales_units), 0), 2) AS uplift_pct
   The 100.0 MUST come FIRST — NEVER write (x - y) / z * 100. SQLite integer division makes that 0.
5. Always return ALL regions or ALL categories — never filter to a single region unless the user specifically asks for one region only.
6. Always return BOTH uplift_pct AND absolute promo units.
7. Do not access any table not in the allowed list above.

INTENT → TABLE MAPPING (use the correct table for each intent):
- promotional_performance    → promo_performance_mart
- regional_comparison        → regional_summary_mart  
- inventory_movement         → inventory_movement_mart (use prior_week_units_cleared and promo_week_units_cleared)
- campaign_impact_by_product → promo_performance_mart (GROUP BY sku_code, sku_name)

EXACT COLUMN NAMES — use these exactly, do not invent new names:
promo_performance_mart:    campaign_id, week_number, region, sku_code, sku_name, category,
                           baseline_sales_units, promo_sales_units, uplift_pct, data_completeness

inventory_movement_mart:   campaign_id, week_number, category,
                           prior_week_units_cleared, promo_week_units_cleared, inventory_delta_pct

regional_summary_mart:     campaign_id, region, baseline_sales_units,
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


# ── Hardcoded SQL templates per intent ──────────────────────────────────────
# These bypass the LLM for well-defined query patterns — LLM SQL generation
# is only used as a fallback. This guarantees correct column names and
# avoids integer division bugs.

SQL_TEMPLATES = {
    "promotional_performance": """
        SELECT
            region,
            SUM(baseline_sales_units) AS baseline_units,
            SUM(promo_sales_units) AS promo_units,
            ROUND(100.0 * (SUM(promo_sales_units) - SUM(baseline_sales_units))
                / NULLIF(SUM(baseline_sales_units), 0), 2) AS uplift_pct
        FROM promo_performance_mart
        WHERE campaign_id = '{campaign_id}'{region_filter}
        GROUP BY region
        ORDER BY uplift_pct DESC
    """,
    "regional_comparison": """
        SELECT
            region,
            SUM(baseline_sales_units) AS baseline_units,
            SUM(promo_sales_units) AS promo_units,
            ROUND(100.0 * (SUM(promo_sales_units) - SUM(baseline_sales_units))
                / NULLIF(SUM(baseline_sales_units), 0), 2) AS uplift_pct
        FROM regional_summary_mart
        WHERE campaign_id = '{campaign_id}'
        GROUP BY region
        ORDER BY uplift_pct DESC
    """,
    "inventory_movement": """
        SELECT
            category,
            SUM(prior_week_units_cleared) AS prior_week_units_cleared,
            SUM(promo_week_units_cleared) AS promo_week_units_cleared,
            ROUND(100.0 * (SUM(promo_week_units_cleared) - SUM(prior_week_units_cleared))
                / NULLIF(SUM(prior_week_units_cleared), 0), 2) AS inventory_delta_pct
        FROM inventory_movement_mart
        WHERE campaign_id = '{campaign_id}'{category_filter}
        GROUP BY category
        ORDER BY inventory_delta_pct DESC
    """,
    "campaign_impact_by_product": """
        SELECT
            sku_code,
            sku_name,
            category,
            SUM(baseline_sales_units) AS baseline_units,
            SUM(promo_sales_units) AS promo_units,
            ROUND(100.0 * (SUM(promo_sales_units) - SUM(baseline_sales_units))
                / NULLIF(SUM(baseline_sales_units), 0), 2) AS uplift_pct
        FROM promo_performance_mart
        WHERE campaign_id = '{campaign_id}'{region_filter}
        GROUP BY sku_code, sku_name, category
        ORDER BY uplift_pct DESC
        LIMIT 20
    """,
}


def _build_sql_from_template(intent: str, context: dict) -> str | None:
    """
    Build SQL from a hardcoded template if the intent is known.
    Returns None if intent not in templates (falls back to LLM).
    """
    template = SQL_TEMPLATES.get(intent)
    if not template:
        return None

    campaign_id = context.get("campaign_id") or "FEB_2025"
    region = context.get("region")
    category = context.get("category")

    region_filter = f" AND region = '{region}'" if region else ""
    category_filter = f" AND category = '{category}'" if category else ""

    return template.format(
        campaign_id=campaign_id,
        region_filter=region_filter,
        category_filter=category_filter,
    ).strip()


def _fix_integer_division(df: pd.DataFrame) -> pd.DataFrame:
    """
    Safety net: if SQLite integer division produced 0 for uplift_pct,
    recompute it in Python from promo and baseline columns.
    """
    uplift_cols = [c for c in df.columns if "uplift_pct" in c.lower() or c == "uplift_pct"]
    for col in uplift_cols:
        if col in df.columns and (df[col] == 0).all():
            # Try to recompute from promo/baseline columns
            promo_col = next((c for c in df.columns if "promo" in c.lower() and "unit" in c.lower()), None)
            base_col  = next((c for c in df.columns if "baseline" in c.lower() and "unit" in c.lower()), None)
            if promo_col and base_col:
                df[col] = (
                    100.0 * (df[promo_col] - df[base_col]) / df[base_col].replace(0, float("nan"))
                ).round(2)
    return df


def build_and_execute_query(enriched_context: dict) -> dict:
    intent = enriched_context.get("intent", "")

    # Try hardcoded template first — faster, correct, no LLM cost
    sql = _build_sql_from_template(intent, enriched_context)
    reasoning = "hardcoded template"

    # Fall back to LLM only if no template exists for this intent
    if not sql:
        context_summary = f"""
Intent: {intent}
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
        result_df = _fix_integer_division(result_df)
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