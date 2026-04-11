"""
test_pipeline_e2e.py — Step 6: Full Pipeline E2E + 30+ Question Bank
"""

import pytest
import pandas as pd
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

QUESTION_BANK = {
    "promotional_performance": [
        "Did the February campaign improve sales in the South?",
        "What was the uplift from the summer campaign?",
        "How did the Q1 campaign perform overall?",
        "Did the winter campaign drive sales growth in the North?",
        "What was the promotional uplift for FEB_2025?",
        "How effective was last month's campaign?",
    ],
    "inventory_movement": [
        "Which categories saw inventory reduction during the summer promotion?",
        "How did stock levels change during the Q1 campaign?",
        "What was the sell-through rate improvement in the February campaign?",
        "Which category cleared the most stock during the winter campaign?",
        "How did carbonates inventory move during the summer campaign?",
        "Did energy drinks see stock clearance improvement in FEB_2025?",
    ],
    "regional_comparison": [
        "How did the North perform versus the South during the summer campaign?",
        "Compare regional performance for the February promotion",
        "Which region had the best uplift in the Q1 campaign?",
        "North vs South performance in winter campaign",
        "How did East and West compare in the summer campaign?",
        "Which was the top performing region in FEB_2025?",
    ],
    "campaign_impact_by_product": [
        "Which SKUs benefited most from the February price promotion?",
        "What products drove the most volume during the summer campaign?",
        "Which SKU had the highest incremental lift in Q1?",
        "Top performing products in the winter campaign?",
        "Which beverages saw the highest uplift in FEB_2025?",
        "What were the hero SKUs in the summer campaign?",
    ],
    "edge_cases": [
        "How did the region with overlapping campaigns perform?",
        "What was the baseline for the campaign with no data?",
        "Which SKUs had unusual uplift in East during February?",
    ],
    "ambiguous_should_clarify": [
        "How did things go?",
        "What happened last month?",
        "Tell me about performance",
        "Is it good?",
    ],
    "out_of_scope_must_clarify": [
        "What's the weather like today?",
        "Book me a flight to London",
        "What is the stock price of Coca-Cola?",
    ],
}

GOOD_DF = pd.DataFrame([{
    "campaign_id": "FEB_2025", "region": "South", "uplift_pct": 14.3,
    "promo_sales_units": 22400, "baseline_sales_units": 19600, "data_completeness": 0.97,
}])

INTENT_JSON = '{"intent": "promotional_performance", "confidence": 0.92, "reasoning": "test"}'
VOCAB_JSON  = '{"campaign_id": "FEB_2025", "region": "South", "category": null, "sku_code": null, "time_reference": "FEB_2025", "resolved_terms": {}, "ambiguities": []}'
SQL_JSON    = '{"sql": "SELECT region, SUM(promo_sales_units) AS promo_units, SUM(baseline_sales_units) AS baseline_units, ROUND(100.0*(SUM(promo_sales_units)-SUM(baseline_sales_units))/NULLIF(SUM(baseline_sales_units),0),1) AS uplift_pct FROM promo_performance_mart WHERE campaign_id=\'FEB_2025\' GROUP BY region", "reasoning": "test"}'
NARR_JSON   = '{"headline": "South delivered 14.3% uplift.", "body": "The South region showed strong response.", "caveats": [], "formatted_answer": "South delivered 14.3% uplift. Strong promotional response."}'


class TestPipelineMockedE2E:
    @patch("agents.narrative_agent.chat", return_value=NARR_JSON)
    @patch("agents.query_agent.execute_query", return_value=GOOD_DF)
    @patch("agents.query_agent.chat", return_value=SQL_JSON)
    @patch("agents.vocabulary_agent.chat", return_value=VOCAB_JSON)
    @patch("agents.intent_agent.chat", return_value=INTENT_JSON)
    def test_successful_pipeline_run(self, *mocks):
        from agents.orchestrator import run_pipeline
        result = run_pipeline("Did the February campaign improve sales in the South?")
        assert result.status == "success"
        assert len(result.formatted_answer) > 10
        assert result.intent.get("intent") == "promotional_performance"

    @patch("agents.narrative_agent.chat", return_value=NARR_JSON)
    @patch("agents.query_agent.execute_query", return_value=GOOD_DF)
    @patch("agents.query_agent.chat", return_value=SQL_JSON)
    @patch("agents.vocabulary_agent.chat", return_value=VOCAB_JSON)
    @patch("agents.intent_agent.chat", return_value=INTENT_JSON)
    def test_pipeline_records_latency(self, *mocks):
        from agents.orchestrator import run_pipeline
        result = run_pipeline("Did the campaign work?")
        assert result.total_latency_ms > 0

    @patch("agents.intent_agent.chat", return_value='{"intent": "unclear", "confidence": 0.05, "reasoning": "weather", "clarification_needed": "Please ask about promotions."}')
    def test_out_of_scope_returns_clarification(self, mock_chat):
        from agents.orchestrator import run_pipeline
        result = run_pipeline("What is the weather today?")
        assert result.status == "clarification_needed"

    @patch("agents.narrative_agent.chat")
    @patch("agents.query_agent.execute_query", return_value=pd.DataFrame())
    @patch("agents.query_agent.chat", return_value=SQL_JSON)
    @patch("agents.vocabulary_agent.chat", return_value=VOCAB_JSON)
    @patch("agents.intent_agent.chat", return_value=INTENT_JSON)
    def test_empty_db_result_blocks_pipeline(self, mi, mv, mq, me, mn):
        from agents.orchestrator import run_pipeline
        result = run_pipeline("Did FAKE_CAMPAIGN work?")
        assert result.status == "blocked"
        mn.assert_not_called()


class TestQuestionBankCoverage:
    def test_question_bank_has_minimum_30_queries(self):
        total = sum(len(v) for v in QUESTION_BANK.values())
        assert total >= 30, f"Only {total} queries — need 30+"

    def test_all_four_intent_types_covered(self):
        for intent in ["promotional_performance", "inventory_movement",
                       "regional_comparison", "campaign_impact_by_product"]:
            assert intent in QUESTION_BANK
            assert len(QUESTION_BANK[intent]) >= 5

    def test_edge_cases_included(self):
        assert len(QUESTION_BANK["edge_cases"]) >= 2

    def test_ambiguous_queries_included(self):
        assert len(QUESTION_BANK["ambiguous_should_clarify"]) >= 3

    def test_out_of_scope_queries_included(self):
        assert len(QUESTION_BANK["out_of_scope_must_clarify"]) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
