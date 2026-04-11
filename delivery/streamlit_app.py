"""
streamlit_app.py — Delivery: Web App for Analysts
---------------------------------------------------
For power users and analysts who need charts, multi-query history,
and a richer interface than Slack.

NOT the primary CXO interface — that's Slack + email digest.

Run:
  streamlit run delivery/streamlit_app.py
"""

import streamlit as st
import pandas as pd
import time
from agents.orchestrator import run_pipeline

st.set_page_config(
    page_title="FMCG Analytics Assistant",
    page_icon="📊",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 FMCG Analytics")
    st.caption("AI Analytics Assistant for CXOs and Managers")
    st.divider()
    st.markdown("**Example questions:**")
    examples = [
        "Did the February campaign improve sales in the South?",
        "Which categories saw inventory reduction during the summer campaign?",
        "How did the North compare to the South in the Q1 campaign?",
        "Which SKUs had the highest uplift from the FEB_2025 campaign?",
    ]
    for ex in examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state["prefill"] = ex

    st.divider()
    st.caption("Pipeline: Orchestrator → Intent → Vocabulary → Query → Validation → Narrative")
    st.caption("Models: Claude Haiku 4.5 (routing) · Claude Sonnet 4.6 (query + narrative)")

# ── Session State ─────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ── Main Header ───────────────────────────────────────────────────────────
st.title("FMCG Beverages Analytics Assistant")
st.caption("Ask questions about promotional performance, inventory, regional sales, and campaign impact.")

# ── Query Input ───────────────────────────────────────────────────────────
prefill = st.session_state.pop("prefill", "")
user_query = st.chat_input("Ask a question about your promotions...", key="main_input")

# Handle example button clicks
if prefill and not user_query:
    user_query = prefill

if user_query:
    # Show user message
    with st.chat_message("user"):
        st.write(user_query)

    # Run pipeline with streaming progress
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        progress_msgs = []

        def on_step(msg: str):
            progress_msgs.append(msg)
            status_placeholder.markdown("\n\n".join(progress_msgs))

        start = time.time()
        result = run_pipeline(user_query, on_step=on_step)
        elapsed = round(time.time() - start, 2)

        status_placeholder.empty()

        if result.status == "success":
            # Headline
            st.markdown(f"**{result.narrative.get('headline', '')}**")
            st.markdown(result.narrative.get("body", ""))

            # Caveats
            for caveat in result.narrative.get("caveats", []):
                st.warning(caveat)

            # Show data table
            df = result.validation.get("result_df", pd.DataFrame())
            if not df.empty:
                with st.expander("📋 View underlying data"):
                    # Drop internal columns
                    display_cols = [c for c in df.columns if not c.endswith("_flagged")]
                    st.dataframe(df[display_cols], use_container_width=True)

                    # Simple chart if uplift data present
                    uplift_col = next(
                        (c for c in df.columns if "uplift" in c.lower() and "flagged" not in c),
                        None,
                    )
                    group_col = next(
                        (c for c in ["region", "sku_name", "category"] if c in df.columns),
                        None,
                    )
                    if uplift_col and group_col and len(df) > 1:
                        chart_df = df[[group_col, uplift_col]].set_index(group_col)
                        st.bar_chart(chart_df)

            # Pipeline metadata
            with st.expander("🔍 Pipeline details"):
                meta_cols = st.columns(4)
                meta_cols[0].metric("Intent", result.intent.get("intent", "—"))
                meta_cols[1].metric("Confidence", f"{round((result.intent.get('confidence', 0))*100)}%")
                meta_cols[2].metric("Campaign", result.enriched_context.get("campaign_id", "—"))
                meta_cols[3].metric("Latency", f"{result.total_latency_ms}ms")

                st.code(result.query_result.get("sql", ""), language="sql")

        elif result.status == "clarification_needed":
            st.info(result.formatted_answer)

        elif result.status == "blocked":
            st.error(result.formatted_answer)

        else:
            st.error(f"Pipeline error: {result.error}")

    # Add to history
    st.session_state.history.append({
        "query": user_query,
        "answer": result.formatted_answer,
        "status": result.status,
        "intent": result.intent.get("intent"),
    })

# ── Conversation History ──────────────────────────────────────────────────
if st.session_state.history:
    with st.expander(f"📜 Query history ({len(st.session_state.history)} queries)"):
        for item in reversed(st.session_state.history[:-1]):
            st.markdown(f"**Q:** {item['query']}")
            st.markdown(f"**A:** {item['answer'][:200]}{'...' if len(item['answer']) > 200 else ''}")
            st.divider()
