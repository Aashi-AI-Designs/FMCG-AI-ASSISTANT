"""
test_intent_agent.py — Step 2 of Six-Step Testing Sequence
-----------------------------------------------------------
Deterministic tests + mocked Gemini responses.
"""

import pytest
import sys, os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.semantic_config import INTENT_TYPES


class TestIntentTypes:
    def test_all_four_intents_defined(self):
        expected = {"promotional_performance", "inventory_movement",
                    "regional_comparison", "campaign_impact_by_product"}
        assert set(INTENT_TYPES.keys()) == expected

    def test_each_intent_has_required_fields(self):
        for name, defn in INTENT_TYPES.items():
            for f in ["description", "required_dimensions", "primary_metric", "mart", "example_queries"]:
                assert f in defn, f"Intent '{name}' missing '{f}'"

    def test_each_intent_has_example_queries(self):
        for name, defn in INTENT_TYPES.items():
            assert len(defn["example_queries"]) >= 2

    def test_intent_marts_are_valid_tables(self):
        from config.semantic_config import ALLOWED_TABLES
        for name, defn in INTENT_TYPES.items():
            assert defn["mart"] in ALLOWED_TABLES


class TestIntentAgentParsing:
    @patch("agents.intent_agent.chat")
    def test_promotional_performance(self, mock_chat):
        from agents.intent_agent import classify_intent
        mock_chat.return_value = '{"intent": "promotional_performance", "confidence": 0.95, "reasoning": "test"}'
        r = classify_intent("Did the February campaign improve sales in the South?")
        assert r["intent"] == "promotional_performance"
        assert r["confidence"] >= 0.85

    @patch("agents.intent_agent.chat")
    def test_inventory_movement(self, mock_chat):
        from agents.intent_agent import classify_intent
        mock_chat.return_value = '{"intent": "inventory_movement", "confidence": 0.91, "reasoning": "test"}'
        r = classify_intent("Which categories saw inventory reduction?")
        assert r["intent"] == "inventory_movement"

    @patch("agents.intent_agent.chat")
    def test_regional_comparison(self, mock_chat):
        from agents.intent_agent import classify_intent
        mock_chat.return_value = '{"intent": "regional_comparison", "confidence": 0.93, "reasoning": "test"}'
        r = classify_intent("How did North compare to South?")
        assert r["intent"] == "regional_comparison"

    @patch("agents.intent_agent.chat")
    def test_out_of_scope_returns_unclear(self, mock_chat):
        from agents.intent_agent import classify_intent
        mock_chat.return_value = '{"intent": "unclear", "confidence": 0.1, "reasoning": "weather", "clarification_needed": "Please ask about promotions."}'
        r = classify_intent("What is the weather?")
        assert r["intent"] == "unclear"
        assert "clarification_needed" in r

    @patch("agents.intent_agent.chat")
    def test_malformed_json_returns_safe_fallback(self, mock_chat):
        from agents.intent_agent import classify_intent
        mock_chat.return_value = "This is not JSON"
        r = classify_intent("Some query")
        assert r["intent"] == "unclear"
        assert r["confidence"] == 0.0

    @patch("agents.intent_agent.chat")
    def test_result_always_has_raw_query(self, mock_chat):
        from agents.intent_agent import classify_intent
        mock_chat.return_value = '{"intent": "promotional_performance", "confidence": 0.9, "reasoning": "test"}'
        q = "Did the campaign work?"
        r = classify_intent(q)
        assert r["raw_query"] == q


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
