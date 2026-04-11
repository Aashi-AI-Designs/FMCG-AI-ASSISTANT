"""
validation_agent.py — Agent 5: Validation Agent
-------------------------------------------------
Model: NONE — pure Python only
Job:   Checks query results for missing data, outliers, impossible values,
       and data completeness before the language model ever sees them.

This is the structural firewall between raw query results and the
Narrative Agent. A wrong number NEVER reaches a CXO.

Validation rules (from VALIDATION_RULES in semantic_config):
  1. Empty result → blocked, clarification requested
  2. Null uplift values → warning, row removed
  3. Uplift > 200% → flagged as suspicious, human review recommended
  4. Data completeness < 80% → caveat statement added
  5. Good data → all checks pass, result forwarded

"Every mitigation below is enforced by how the pipeline is built,
not by how the model is prompted." — Research doc, Section D
"""

import pandas as pd
from typing import Optional
from config.semantic_config import VALIDATION_RULES


def validate_result(
    result: dict,
    intent: str,
    enriched_context: dict,
) -> dict:
    """
    Validate a query result dict (from query_agent.build_and_execute_query).

    Returns:
        dict with:
          - status: "pass" | "blocked" | "warning"
          - result_df: cleaned DataFrame (nulls removed)
          - caveats: list of caveat strings to include in narrative
          - blocked_reason: str if status == "blocked"
    """
    df: pd.DataFrame = result.get("result_df", pd.DataFrame())
    caveats = []
    warnings = []

    # ── Check 1: Execution error propagated ──────────────────────────────
    if result.get("validation_status") in ("error", "blocked", "execution_error"):
        return {
            "status": "blocked",
            "result_df": pd.DataFrame(),
            "caveats": [],
            "blocked_reason": f"Query failed: {result.get('error', 'unknown error')}",
        }

    # ── Check 2: Empty result set ─────────────────────────────────────────
    if df is None or df.empty:
        return {
            "status": "blocked",
            "result_df": pd.DataFrame(),
            "caveats": [],
            "blocked_reason": (
                "No data returned for this query. The campaign ID or filter "
                "combination may not exist in the database. Please check the "
                "campaign name and try again."
            ),
        }

    # ── Check 3: Remove null uplift rows ─────────────────────────────────
    uplift_cols = [c for c in df.columns if "uplift" in c.lower()]
    for col in uplift_cols:
        null_mask = df[col].isnull()
        if null_mask.any():
            null_count = null_mask.sum()
            df = df[~null_mask].copy()
            warnings.append(
                f"Note: {null_count} row(s) with missing uplift values were "
                f"excluded from this result."
            )

    # ── Check 4: Suspicious uplift > threshold ───────────────────────────
    max_threshold = VALIDATION_RULES["max_uplift_pct"]
    for col in uplift_cols:
        if col in df.columns:
            suspicious = df[df[col] > max_threshold]
            if not suspicious.empty:
                caveats.append(
                    f"⚠️ Warning: {len(suspicious)} row(s) show uplift above "
                    f"{max_threshold}% which is outside normal range. "
                    f"These figures should be reviewed before presenting externally."
                )
                # Flag but don't remove — human should decide
                df[f"{col}_flagged"] = df[col] > max_threshold

    # ── Check 5: Low baseline units ──────────────────────────────────────
    baseline_cols = [c for c in df.columns if "baseline" in c.lower() and "units" in c.lower()]
    for col in baseline_cols:
        low_baseline = df[df[col] < VALIDATION_RULES["min_baseline_units"]]
        if not low_baseline.empty:
            caveats.append(
                f"Note: Some baseline figures are below {VALIDATION_RULES['min_baseline_units']} units, "
                f"which may make the uplift percentage less reliable."
            )

    # ── Check 6: Data completeness ───────────────────────────────────────
    if "data_completeness" in df.columns:
        low_completeness = df[df["data_completeness"] < VALIDATION_RULES["min_data_completeness"]]
        if not low_completeness.empty:
            pct = round(low_completeness["data_completeness"].min() * 100)
            caveats.append(
                f"Note: Some data in this result has completeness of {pct}% — "
                f"this result may not cover all trading days in the window."
            )

    # ── Check 7: Validate campaign_id matches query ───────────────────────
    queried_campaign = enriched_context.get("campaign_id")
    if queried_campaign and "campaign_id" in df.columns:
        returned_campaigns = df["campaign_id"].unique().tolist()
        if queried_campaign not in returned_campaigns and returned_campaigns:
            caveats.append(
                f"Note: The query returned data for campaign(s) {returned_campaigns} "
                f"but the question referenced '{queried_campaign}'. Please verify the campaign name."
            )

    caveats.extend(warnings)

    # ── Final check: was anything left after cleaning? ────────────────────
    if df.empty:
        return {
            "status": "blocked",
            "result_df": pd.DataFrame(),
            "caveats": caveats,
            "blocked_reason": (
                "After removing invalid rows, no data remains to report. "
                "Please verify the data for this campaign and period."
            ),
        }

    return {
        "status": "pass" if not caveats else "warning",
        "result_df": df,
        "caveats": caveats,
        "blocked_reason": None,
    }


if __name__ == "__main__":
    # Test: suspicious uplift
    test_df = pd.DataFrame([
        {"campaign_id": "FEB_2025", "region": "South", "uplift_pct": 14.3,
         "promo_units": 22400, "baseline_sales_units": 19600, "data_completeness": 0.95},
        {"campaign_id": "FEB_2025", "region": "East", "uplift_pct": 245.0,  # suspicious
         "promo_units": 3100, "baseline_sales_units": 900, "data_completeness": 0.88},
    ])
    mock_result = {"validation_status": "ok", "result_df": test_df, "error": None}
    validation = validate_result(mock_result, "promotional_performance", {"campaign_id": "FEB_2025"})
    print(f"Status: {validation['status']}")
    print(f"Caveats: {validation['caveats']}")
    print(validation["result_df"])
