"""
test_vocabulary_agent.py — Step 1 of Six-Step Testing Sequence
---------------------------------------------------------------
Deterministic vocabulary dictionary tests + mocked Gemini tests.
"""

import pytest
import sys, os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.semantic_config import VOCABULARY, CAMPAIGN_REGISTRY


class TestVocabularyDictionary:
    def test_uplift_synonyms_all_resolve(self):
        for term in ["uplift", "sales uplift", "incremental uplift", "lift", "sales lift"]:
            assert VOCABULARY[term] == "uplift_pct"

    def test_baseline_synonyms_all_resolve(self):
        for term in ["baseline", "pre-promo baseline", "benchmark", "normal sales", "base sales"]:
            assert VOCABULARY[term] == "baseline_units"

    def test_inventory_synonyms_resolve(self):
        for term in ["stock clearance", "inventory reduction", "stock movement", "sell-through rate"]:
            assert VOCABULARY[term] == "inventory_delta_pct"

    def test_region_synonyms_resolve_to_canonical(self):
        assert VOCABULARY["south region"] == "South"
        assert VOCABULARY["north region"] == "North"
        assert VOCABULARY["east region"] == "East"
        assert VOCABULARY["west region"] == "West"

    def test_campaign_registry_has_required_campaigns(self):
        for cid in ["FEB_2025", "SUMMER_2025", "WINTER_2024", "Q1_2025"]:
            assert cid in CAMPAIGN_REGISTRY

    def test_campaign_registry_has_week_numbers(self):
        for cid, meta in CAMPAIGN_REGISTRY.items():
            if meta.get("campaign_id"):
                assert len(meta.get("weeks", [])) > 0


class TestEnrichQueryWithMock:
    @patch("agents.vocabulary_agent.chat")
    def test_south_region_extraction(self, mock_chat):
        from agents.vocabulary_agent import enrich_query
        mock_chat.return_value = '{"campaign_id": "FEB_2025", "region": "South", "category": null, "sku_code": null, "time_reference": "FEB_2025", "resolved_terms": {}, "ambiguities": []}'
        r = enrich_query("Did the February campaign improve sales in the South?", "promotional_performance")
        assert r["region"] == "South"
        assert r["campaign_id"] == "FEB_2025"

    @patch("agents.vocabulary_agent.chat")
    def test_unknown_region_returns_ambiguity(self, mock_chat):
        from agents.vocabulary_agent import enrich_query
        mock_chat.return_value = '{"campaign_id": null, "region": null, "category": null, "sku_code": null, "time_reference": null, "resolved_terms": {}, "ambiguities": ["Could not resolve region: Midlands"]}'
        r = enrich_query("How did the Midlands campaign go?", "promotional_performance")
        assert len(r["ambiguities"]) > 0

    @patch("agents.vocabulary_agent.chat")
    def test_malformed_output_returns_safe_default(self, mock_chat):
        from agents.vocabulary_agent import enrich_query
        mock_chat.return_value = "not valid json"
        r = enrich_query("Some query", "promotional_performance")
        assert isinstance(r, dict)
        assert "ambiguities" in r


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
