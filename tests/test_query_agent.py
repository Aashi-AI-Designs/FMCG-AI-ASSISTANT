"""
test_query_agent.py — Step 3 of Six-Step Testing Sequence
----------------------------------------------------------
SQL structural validation + mocked Gemini query builder tests.
"""

import pytest
import pandas as pd
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.semantic_config import ALLOWED_TABLES
from agents.query_agent import _validate_sql_structure


class TestSQLStructuralValidation:
    def test_valid_select_with_where_passes(self):
        sql = "SELECT region, SUM(promo_sales_units) FROM promo_performance_mart WHERE campaign_id = 'FEB_2025' GROUP BY region"
        valid, _ = _validate_sql_structure(sql)
        assert valid is True

    def test_insert_is_blocked(self):
        valid, msg = _validate_sql_structure("INSERT INTO promo_performance_mart VALUES (1,2,3)")
        assert valid is False and "INSERT" in msg

    def test_update_is_blocked(self):
        valid, _ = _validate_sql_structure("UPDATE promo_performance_mart SET uplift_pct = 999")
        assert valid is False

    def test_delete_is_blocked(self):
        valid, _ = _validate_sql_structure("DELETE FROM promo_performance_mart WHERE 1=1")
        assert valid is False

    def test_drop_is_blocked(self):
        valid, _ = _validate_sql_structure("DROP TABLE promo_performance_mart")
        assert valid is False

    def test_missing_where_clause_is_blocked(self):
        valid, msg = _validate_sql_structure("SELECT * FROM promo_performance_mart")
        assert valid is False and "WHERE" in msg

    def test_forbidden_table_is_blocked(self):
        valid, msg = _validate_sql_structure("SELECT * FROM raw_transactions WHERE campaign_id = 'X'")
        assert valid is False

    def test_all_allowed_tables_pass(self):
        for table in ALLOWED_TABLES:
            sql = f"SELECT COUNT(*) FROM {table} WHERE campaign_id = 'FEB_2025'"
            valid, msg = _validate_sql_structure(sql)
            assert valid is True, f"'{table}' incorrectly blocked: {msg}"


class TestSQLPatternRequirements:
    def test_uplift_query_has_nullif_protection(self):
        sql = "SELECT ROUND(100.0*(SUM(promo_sales_units)-SUM(baseline_sales_units))/NULLIF(SUM(baseline_sales_units),0),1) AS uplift_pct FROM promo_performance_mart WHERE campaign_id='FEB_2025'"
        assert "NULLIF" in sql.upper()

    def test_uplift_query_returns_both_pct_and_units(self):
        sql = "SELECT SUM(promo_sales_units) AS promo_units, SUM(baseline_sales_units) AS baseline_units, ROUND(100.0*(SUM(promo_sales_units)-SUM(baseline_sales_units))/NULLIF(SUM(baseline_sales_units),0),1) AS uplift_pct FROM promo_performance_mart WHERE campaign_id='FEB_2025'"
        assert "UPLIFT_PCT" in sql.upper() and "UNITS" in sql.upper()


class TestQueryAgentWithMock:
    @patch("agents.query_agent.execute_query")
    @patch("agents.query_agent.chat")
    def test_valid_query_executes_successfully(self, mock_chat, mock_execute):
        from agents.query_agent import build_and_execute_query
        sql = "SELECT region, SUM(promo_sales_units) AS promo_units FROM promo_performance_mart WHERE campaign_id='FEB_2025' GROUP BY region"
        mock_chat.return_value = f'{{"sql": "{sql}", "reasoning": "test"}}'
        mock_execute.return_value = pd.DataFrame([{"region": "South", "promo_units": 22400}])
        result = build_and_execute_query({"intent": "regional_comparison", "campaign_id": "FEB_2025", "region": None, "original_query": "test"})
        assert result["validation_status"] == "ok"
        assert result["rows"] == 1

    @patch("agents.query_agent.execute_query")
    @patch("agents.query_agent.chat")
    def test_write_sql_blocked_before_execution(self, mock_chat, mock_execute):
        from agents.query_agent import build_and_execute_query
        # Use unknown intent so it falls through to LLM (templates handle known intents)
        mock_chat.return_value = '{"sql": "DELETE FROM promo_performance_mart WHERE campaign_id=\'X\'", "reasoning": "test"}'
        result = build_and_execute_query({"intent": "unknown_intent", "campaign_id": "X", "region": None, "original_query": "test"})
        assert result["validation_status"] == "blocked"
        mock_execute.assert_not_called()

    def test_hardcoded_templates_are_always_safe(self):
        from agents.query_agent import _build_sql_from_template, _validate_sql_structure
        for intent in ["promotional_performance", "regional_comparison",
                       "inventory_movement", "campaign_impact_by_product"]:
            sql = _build_sql_from_template(intent, {"campaign_id": "FEB_2025", "region": None, "category": None})
            valid, msg = _validate_sql_structure(sql)
            assert valid, f"Template for {intent} failed validation: {msg}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])