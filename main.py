"""
main.py — CLI Entry Point
--------------------------
Run: python main.py
     python main.py --query "Did the February campaign improve sales in the South?"
     python main.py --setup-db
     python main.py --run-tests
     python main.py --diagnose
"""

import argparse
import sys
import os

from dotenv import load_dotenv
load_dotenv()


def check_api_key():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("ERROR: GEMINI_API_KEY not set.")
        print("  1. Go to https://aistudio.google.com/app/apikey")
        print("  2. Click 'Create API key'")
        print("  3. Add to .env:  GEMINI_API_KEY=AIza...")
        sys.exit(1)


def setup_database():
    print("Setting up mock database...")
    from data.mock_data import setup_database as _setup
    _setup()


def diagnose():
    """Step-by-step diagnostics — run this when something breaks."""
    print("\n--- FMCG Assistant Diagnostics ---\n")

    # 1. .env file
    from pathlib import Path
    if Path(".env").exists():
        print("[OK]   .env file found")
    else:
        print("[FAIL] .env file not found in:", os.getcwd())
        print("       Fix: cp .env.example .env  then add your API key")
        return

    # 2. API key present
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        print(f"[OK]   GEMINI_API_KEY set ({len(key)} chars, starts: {key[:8]}...)")
    else:
        print("[FAIL] GEMINI_API_KEY missing or empty in .env")
        print("       Fix: add line  GEMINI_API_KEY=AIza...  to your .env file")
        return

    # 3. google-genai importable
    try:
        from google import genai
        print("[OK]   google-genai package installed")
    except ImportError:
        print("[FAIL] google-genai not installed")
        print("       Fix: pip install google-genai")
        return

    # 4. Client initialises
    try:
        client = genai.Client(api_key=key)
        print("[OK]   Gemini client created")
    except Exception as e:
        print(f"[FAIL] Could not create Gemini client: {e}")
        return

    # 5. Real API call
    print("       Making test API call...")
    try:
        from google.genai import types
        resp = client.models.generate_content(
            model="gemini-1.5-flash",
            contents="Reply with only the word: WORKING",
            config=types.GenerateContentConfig(max_output_tokens=10, temperature=0),
        )
        print(f"[OK]   Gemini responded: '{resp.text.strip()}'")
    except Exception as e:
        print(f"[FAIL] Gemini API call failed: {e}")
        print("\n       Common causes:")
        print("       - Invalid/expired key  → regenerate at aistudio.google.com")
        print("       - Rate limit (429)     → wait 60 seconds and retry")
        print("       - No internet          → check your connection")
        return

    # 6. Database
    try:
        from data.db import execute_query
        df = execute_query("SELECT COUNT(*) as n FROM promo_performance_mart WHERE campaign_id='FEB_2025'")
        print(f"[OK]   Database connected ({df.iloc[0]['n']} rows for FEB_2025)")
    except Exception as e:
        print(f"[WARN] Database issue: {e}")
        print("       Fix: python main.py --setup-db")

    print("\n--- All checks passed. Run: python main.py ---\n")


def run_query(query: str):
    check_api_key()
    from agents.orchestrator import run_pipeline

    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print("="*60)

    def on_step(msg: str):
        print(f"  {msg}")

    result = run_pipeline(query, on_step=on_step)

    print(f"\n{'-'*60}")
    print(f"Status:   {result.status}")
    print(f"Intent:   {result.intent.get('intent', '--')} "
          f"(confidence: {round((result.intent.get('confidence', 0)) * 100)}%)")
    if result.enriched_context.get("campaign_id"):
        print(f"Campaign: {result.enriched_context['campaign_id']}")
    if result.enriched_context.get("region"):
        print(f"Region:   {result.enriched_context['region']}")
    print(f"Latency:  {result.total_latency_ms}ms")

    if result.error:
        print(f"\nERROR DETAIL:\n  {result.error}")

    print(f"\n{'-'*60}")
    if result.formatted_answer:
        print("Answer:")
        print(result.formatted_answer)

    if result.narrative.get("caveats"):
        print("\nCaveats:")
        for c in result.narrative["caveats"]:
            print(f"  WARNING: {c}")

    if result.query_result.get("sql"):
        print(f"\nSQL used:")
        print(result.query_result["sql"])

    return result


def interactive_mode():
    check_api_key()
    print("\n" + "="*60)
    print("  FMCG Beverages AI Analytics Assistant")
    print("  Powered by Gemini 1.5 Flash (free tier)")
    print("="*60)
    print("\nExample questions:")
    print("  - Did the February campaign improve sales in the South?")
    print("  - Which categories saw inventory reduction during the summer campaign?")
    print("  - How did the North compare to the South in Q1?")
    print("  - Which SKUs had the highest uplift in FEB_2025?")
    print("\nType 'quit' to exit.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break
        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break
        run_query(query)
        print()


def run_tests():
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FMCG Beverages AI Analytics Assistant")
    parser.add_argument("--query", "-q", type=str, help="Run a single query")
    parser.add_argument("--setup-db", action="store_true", help="Generate mock database")
    parser.add_argument("--run-tests", action="store_true", help="Run pytest suite")
    parser.add_argument("--diagnose", action="store_true", help="Test each component individually")
    args = parser.parse_args()

    if args.diagnose:
        diagnose()
    elif args.setup_db:
        setup_database()
    elif args.run_tests:
        run_tests()
    elif args.query:
        setup_database()
        run_query(args.query)
    else:
        setup_database()
        interactive_mode()