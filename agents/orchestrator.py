"""
orchestrator.py — Agent 1: Orchestrator
-----------------------------------------
Model: Claude Haiku 4.5 (routing only — no reasoning needed)
Job:   Receives user query, runs the six-agent pipeline in sequence,
       assembles final response.

Pipeline sequence:
  1. Orchestrator (this file) — receives query
  2. Intent Agent — classifies question type
  3. Vocabulary / Enrichment Agent — resolves FMCG trade terms
  4. Query Agent — builds SQL, executes, returns raw data
  5. Validation Agent — checks result (pure Python, no LLM)
  6. Narrative Agent — writes plain-language answer

"Think of it as a relay race: each component runs its leg and passes
the baton." — Design doc, Section B
"""

import os
import time
import json
from typing import Optional, Callable
from dotenv import load_dotenv

# Importing gemini_client here validates the API key at startup
from config import gemini_client  # noqa: F401

from agents.intent_agent import classify_intent
from agents.vocabulary_agent import enrich_query
from agents.query_agent import build_and_execute_query
from agents.validation_agent import validate_result
from agents.narrative_agent import generate_narrative, format_for_slack

load_dotenv()


class PipelineResult:
    """Structured result from the full pipeline run."""

    def __init__(self):
        self.query: str = ""
        self.intent: dict = {}
        self.enriched_context: dict = {}
        self.query_result: dict = {}
        self.validation: dict = {}
        self.narrative: dict = {}
        self.formatted_answer: str = ""
        self.slack_answer: str = ""
        self.status: str = "pending"
        self.error: Optional[str] = None
        self.latency_ms: dict = {}
        self.total_latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "intent": self.intent.get("intent"),
            "confidence": self.intent.get("confidence"),
            "campaign_id": self.enriched_context.get("campaign_id"),
            "region": self.enriched_context.get("region"),
            "status": self.status,
            "formatted_answer": self.formatted_answer,
            "caveats": self.narrative.get("caveats", []),
            "data_rows": self.narrative.get("data_rows", 0),
            "total_latency_ms": self.total_latency_ms,
            "error": self.error,
        }


def run_pipeline(
    user_query: str,
    on_step: Optional[Callable[[str], None]] = None,
) -> PipelineResult:
    """
    Run the full six-agent pipeline for a user query.

    Args:
        user_query: The natural language question from a CXO / manager
        on_step: Optional callback called after each step with a status message
                 (used by Slack bot / Streamlit to show progress)

    Returns:
        PipelineResult with the final formatted answer and all intermediate state
    """
    result = PipelineResult()
    result.query = user_query
    pipeline_start = time.time()

    def _step(name: str, message: str):
        if on_step:
            on_step(f"⏳ {message}")

    # ── Step 1: Intent Classification ─────────────────────────────────────
    _step("intent", "Classifying your question...")
    t0 = time.time()
    try:
        intent_result = classify_intent(user_query)
        result.intent = intent_result
        result.latency_ms["intent"] = round((time.time() - t0) * 1000)
    except Exception as e:
        result.status = "error"
        result.error = f"Intent classification failed: {e}"
        return result

    # Handle unclear intent
    if intent_result.get("intent") == "unclear":
        result.status = "clarification_needed"
        clarification = intent_result.get(
            "clarification_needed",
            "Could you rephrase your question? I support promotional performance, "
            "inventory movement, regional comparisons, and campaign impact by product.",
        )
        result.formatted_answer = clarification
        result.slack_answer = clarification
        return result

    intent = intent_result["intent"]

    # ── Step 2: Vocabulary / Enrichment ───────────────────────────────────
    _step("vocab", "Resolving trade terms and campaign references...")
    t0 = time.time()
    try:
        enriched = enrich_query(user_query, intent)
        result.enriched_context = enriched
        result.latency_ms["vocabulary"] = round((time.time() - t0) * 1000)
    except Exception as e:
        result.status = "error"
        result.error = f"Vocabulary resolution failed: {e}"
        return result

    # ── Step 3: Query Building + Execution ────────────────────────────────
    _step("query", "Querying the data mart...")
    t0 = time.time()
    try:
        query_result = build_and_execute_query(enriched)
        result.query_result = query_result
        result.latency_ms["query"] = round((time.time() - t0) * 1000)
    except Exception as e:
        result.status = "error"
        result.error = f"Query execution failed: {e}"
        return result

    # ── Step 4: Validation (pure Python — no LLM) ─────────────────────────
    _step("validation", "Validating results...")
    t0 = time.time()
    try:
        validation = validate_result(query_result, intent, enriched)
        result.validation = validation
        result.latency_ms["validation"] = round((time.time() - t0) * 1000)
    except Exception as e:
        result.status = "error"
        result.error = f"Validation failed: {e}"
        return result

    # Blocked by validation
    if validation["status"] == "blocked":
        result.status = "blocked"
        reason = validation.get("blocked_reason", "The data for this query could not be validated.")
        result.formatted_answer = f"⚠️ {reason}"
        result.slack_answer = result.formatted_answer
        return result

    # ── Step 5: Narrative Generation ─────────────────────────────────────
    _step("narrative", "Writing your answer...")
    t0 = time.time()
    try:
        narrative = generate_narrative(validation, enriched, intent)
        result.narrative = narrative
        result.latency_ms["narrative"] = round((time.time() - t0) * 1000)
    except Exception as e:
        result.status = "error"
        result.error = f"Narrative generation failed: {e}"
        return result

    # ── Assemble Final Answer ─────────────────────────────────────────────
    result.formatted_answer = narrative.get("formatted_answer", "")
    result.slack_answer = format_for_slack(narrative)
    result.status = "success"
    result.total_latency_ms = round((time.time() - pipeline_start) * 1000)

    return result


if __name__ == "__main__":
    test_queries = [
        "Did the February campaign improve sales in the South?",
        "Which categories saw the most inventory reduction during the summer campaign?",
        "How did the North compare to the South in the summer campaign?",
        "Which SKUs had the highest uplift from the Q1 campaign?",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("="*60)

        def progress(msg):
            print(f"  {msg}")

        result = run_pipeline(query, on_step=progress)
        print(f"\nStatus: {result.status}")
        print(f"Intent: {result.intent.get('intent')} (confidence: {result.intent.get('confidence')})")
        print(f"Campaign: {result.enriched_context.get('campaign_id')}")
        print(f"Total latency: {result.total_latency_ms}ms")
        print(f"\nAnswer:\n{result.formatted_answer}")
