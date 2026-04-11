"""
test_validation_agent.py — Step 4 of Six-Step Testing Sequence
---------------------------------------------------------------
Pure Python — no LLM, no mocking needed.
"Tests with mock result sets covering each failure and pass scenario."

Scenarios tested:
  ✓ Empty result → blocked
  ✓ Null uplift values → warning + removed
  ✓ Uplift >200% → flagged
  ✓ Low baseline → caveat added
  ✓ Low data completeness → caveat added
  ✓ Campaign ID mismatch → caveat added
  ✓ Good data → passes all checks (status == "pass")
  ✓ Execution error propagated → blocked
"""

import pytest
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.validation_agent import validate_result
from config.semantic_config import VALIDATION_RULES


def make_good_result(overrides: dict | None = None) -> dict:
    """Helper: create a baseline passing query result."""
    df = pd.DataFrame([{
        "campaign_id": "FEB_2025",
        "region": "South",
        "uplift_pct": 14.3,
        "promo_sales_units": 22400,
        "baseline_sales_units": 19600,
        "data_completeness": 0.97,
    }])
    result = {"validation_status": "ok", "result_df": df, "error": None}
    if overrides:
        result.update(overrides)
    return result


GOOD_CONTEXT = {"campaign_id": "FEB_2025", "region": "South"}


class TestBlockedScenarios:
    """Cases where Validation Agent must block the result entirely."""

    def test_empty_dataframe_is_blocked(self):
        result = make_good_result({"result_df": pd.DataFrame()})
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert v["status"] == "blocked"
        assert v["blocked_reason"] is not None
        assert v["result_df"].empty

    def test_none_dataframe_is_blocked(self):
        result = make_good_result({"result_df": None})
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert v["status"] == "blocked"

    def test_execution_error_is_blocked(self):
        result = {
            "validation_status": "execution_error",
            "result_df": pd.DataFrame(),
            "error": "no such table: promo_performance_mart",
        }
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert v["status"] == "blocked"
        assert "no such table" in v["blocked_reason"].lower() or "Query failed" in v["blocked_reason"]

    def test_query_blocked_by_sql_validator_is_blocked(self):
        result = {
            "validation_status": "blocked",
            "result_df": pd.DataFrame(),
            "error": "Forbidden keyword: DELETE",
        }
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert v["status"] == "blocked"

    def test_all_rows_null_uplift_leaves_empty_df_and_blocks(self):
        df = pd.DataFrame([
            {"campaign_id": "FEB_2025", "region": "South",
             "uplift_pct": None, "baseline_sales_units": 19600, "data_completeness": 0.9},
            {"campaign_id": "FEB_2025", "region": "North",
             "uplift_pct": None, "baseline_sales_units": 45000, "data_completeness": 0.9},
        ])
        result = make_good_result({"result_df": df})
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert v["status"] == "blocked"
        assert v["result_df"].empty


class TestWarningScenarios:
    """Cases where the result passes but caveats are added."""

    def test_suspicious_uplift_adds_warning_but_does_not_block(self):
        df = pd.DataFrame([{
            "campaign_id": "FEB_2025",
            "region": "East",
            "uplift_pct": 245.0,  # above 200% threshold
            "promo_sales_units": 3100,
            "baseline_sales_units": 900,
            "data_completeness": 0.88,
        }])
        result = make_good_result({"result_df": df})
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert v["status"] in ("warning", "pass")  # not blocked
        caveats_text = " ".join(v["caveats"])
        assert "200" in caveats_text or "above" in caveats_text.lower()
        assert not v["result_df"].empty  # row is retained, just flagged

    def test_low_data_completeness_adds_caveat(self):
        df = pd.DataFrame([{
            "campaign_id": "FEB_2025",
            "region": "North",
            "uplift_pct": 10.5,
            "promo_sales_units": 15000,
            "baseline_sales_units": 13600,
            "data_completeness": 0.72,  # below 0.80 threshold
        }])
        result = make_good_result({"result_df": df})
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert len(v["caveats"]) > 0
        caveats_text = " ".join(v["caveats"])
        assert "completeness" in caveats_text.lower() or "%" in caveats_text

    def test_low_baseline_units_adds_caveat(self):
        df = pd.DataFrame([{
            "campaign_id": "FEB_2025",
            "region": "West",
            "uplift_pct": 8.2,
            "promo_sales_units": 110,
            "baseline_sales_units": 50,  # below min_baseline_units = 100
            "data_completeness": 0.95,
        }])
        result = make_good_result({"result_df": df})
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        caveats_text = " ".join(v["caveats"])
        assert "baseline" in caveats_text.lower()

    def test_partial_null_uplift_removes_null_rows_and_warns(self):
        df = pd.DataFrame([
            {"campaign_id": "FEB_2025", "region": "South",
             "uplift_pct": 14.3, "baseline_sales_units": 19600, "data_completeness": 0.97},
            {"campaign_id": "FEB_2025", "region": "West",
             "uplift_pct": None, "baseline_sales_units": 5000, "data_completeness": 0.9},
        ])
        result = make_good_result({"result_df": df})
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert len(v["result_df"]) == 1  # West row removed
        assert v["result_df"].iloc[0]["region"] == "South"
        assert len(v["caveats"]) > 0  # warning about removed row

    def test_campaign_id_mismatch_adds_caveat(self):
        df = pd.DataFrame([{
            "campaign_id": "SUMMER_2025",  # different from queried FEB_2025
            "region": "South",
            "uplift_pct": 18.0,
            "promo_sales_units": 30000,
            "baseline_sales_units": 25000,
            "data_completeness": 0.95,
        }])
        result = make_good_result({"result_df": df})
        v = validate_result(result, "promotional_performance", {"campaign_id": "FEB_2025"})
        caveats_text = " ".join(v["caveats"])
        assert "FEB_2025" in caveats_text or "campaign" in caveats_text.lower()


class TestPassScenarios:
    """Clean data scenarios — all four checks should pass cleanly."""

    def test_clean_single_row_passes(self):
        result = make_good_result()
        v = validate_result(result, "promotional_performance", GOOD_CONTEXT)
        assert v["status"] == "pass"
        assert v["blocked_reason"] is None
        assert len(v["result_df"]) == 1

    def test_clean_multi_region_comparison_passes(self):
        df = pd.DataFrame([
            {"campaign_id": "SUMMER_2025", "region": "North",
             "regional_uplift_pct": 9.1, "promo_sales_units": 61200,
             "baseline_sales_units": 56100, "data_completeness": 0.96},
            {"campaign_id": "SUMMER_2025", "region": "South",
             "regional_uplift_pct": 14.3, "promo_sales_units": 22400,
             "baseline_sales_units": 19600, "data_completeness": 0.94},
        ])
        result = make_good_result({"result_df": df})
        v = validate_result(result, "regional_comparison", {"campaign_id": "SUMMER_2025"})
        assert v["status"] == "pass"
        assert len(v["result_df"]) == 2
        assert v["caveats"] == []

    def test_validation_rules_thresholds_match_config(self):
        """Ensure tests stay in sync with config values."""
        assert VALIDATION_RULES["max_uplift_pct"] == 200.0
        assert VALIDATION_RULES["min_baseline_units"] == 100
        assert VALIDATION_RULES["min_data_completeness"] == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
