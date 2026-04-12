"""
streamlit_app.py — FMCG Analytics Web App with Visualizations
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from agents.orchestrator import run_pipeline

st.set_page_config(
    page_title="FMCG Analytics Assistant",
    page_icon="📊",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #1e1e2e;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    border: 1px solid #2e2e3e;
}
.metric-value { font-size: 2rem; font-weight: 700; color: #7c3aed; }
.metric-label { font-size: 0.85rem; color: #9ca3af; margin-top: 4px; }
.headline-box {
    background: #f5f0ff;
    border-left: 4px solid #7c3aed;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 16px;
    color: #1a1a2e !important;
}
.headline-box strong {
    color: #4c1d95 !important;
    font-size: 1.1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Chart Functions ───────────────────────────────────────────────────────

def chart_promotional_performance(df: pd.DataFrame, campaign_id: str):
    """Bar chart: promo vs baseline units, uplift % as line."""
    if df.empty:
        return

    group_col = next((c for c in ["region", "sku_name", "category"] if c in df.columns), None)
    if not group_col:
        return

    uplift_col = _find_pct_uplift_col(df)

    # If only one row, still show chart — single bar is fine
    # Promo vs Baseline grouped bar
    if "promo_sales_units" in df.columns and "baseline_sales_units" in df.columns:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Baseline Units",
            x=df[group_col],
            y=df["baseline_sales_units"],
            marker_color="#4b5563",
        ))
        fig.add_trace(go.Bar(
            name="Promo Units",
            x=df[group_col],
            y=df["promo_sales_units"],
            marker_color="#7c3aed",
        ))
        fig.update_layout(
            title=f"Promo vs Baseline Sales — {campaign_id}",
            barmode="group",
            plot_bgcolor="#0e0e1a",
            paper_bgcolor="#0e0e1a",
            font_color="#e5e7eb",
            legend=dict(bgcolor="#1e1e2e"),
            xaxis=dict(gridcolor="#2e2e3e"),
            yaxis=dict(gridcolor="#2e2e3e", title="Units"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Uplift % bar
    uplift_col = next((c for c in df.columns if "uplift" in c.lower() and "flagged" not in c), None)
    if uplift_col and group_col:
        df_sorted = df.sort_values(uplift_col, ascending=False)
        colors = ["#ef4444" if v < 0 else "#7c3aed" for v in df_sorted[uplift_col]]
        fig2 = go.Figure(go.Bar(
            x=df_sorted[group_col],
            y=df_sorted[uplift_col],
            marker_color=colors,
            text=[f"{v:.1f}%" for v in df_sorted[uplift_col]],
            textposition="outside",
        ))
        fig2.update_layout(
            title=f"Uplift % by {group_col.replace('_', ' ').title()}",
            plot_bgcolor="#0e0e1a",
            paper_bgcolor="#0e0e1a",
            font_color="#e5e7eb",
            xaxis=dict(gridcolor="#2e2e3e"),
            yaxis=dict(gridcolor="#2e2e3e", title="Uplift %"),
        )
        st.plotly_chart(fig2, use_container_width=True)


def chart_regional_comparison(df: pd.DataFrame, campaign_id: str):
    """Side-by-side regional comparison with uplift and volume."""
    if df.empty or "region" not in df.columns:
        return

    uplift_col = _find_pct_uplift_col(df)

    col1, col2 = st.columns(2)

    # Uplift by region — horizontal bar
    if uplift_col:
        df_sorted = df.sort_values(uplift_col, ascending=True)
        fig = go.Figure(go.Bar(
            x=df_sorted[uplift_col],
            y=df_sorted["region"],
            orientation="h",
            marker_color=["#ef4444" if v < 0 else "#7c3aed" for v in df_sorted[uplift_col]],
            text=[f"{v:.1f}%" for v in df_sorted[uplift_col]],
            textposition="outside",
        ))
        fig.update_layout(
            title="Uplift % by Region",
            plot_bgcolor="#0e0e1a",
            paper_bgcolor="#0e0e1a",
            font_color="#e5e7eb",
            xaxis=dict(gridcolor="#2e2e3e", title="Uplift %"),
            yaxis=dict(gridcolor="#2e2e3e"),
        )
        col1.plotly_chart(fig, use_container_width=True)

    # Volume by region — pie chart
    volume_col = next((c for c in ["promo_sales_units", "promo_units"] if c in df.columns), None)
    if volume_col:
        fig2 = px.pie(
            df,
            values=volume_col,
            names="region",
            title="Volume Share by Region",
            color_discrete_sequence=px.colors.sequential.Purples_r,
        )
        fig2.update_layout(
            plot_bgcolor="#0e0e1a",
            paper_bgcolor="#0e0e1a",
            font_color="#e5e7eb",
        )
        col2.plotly_chart(fig2, use_container_width=True)


def chart_inventory_movement(df: pd.DataFrame, campaign_id: str):
    """Inventory delta chart — before vs during promo."""
    if df.empty:
        return

    group_col = next((c for c in ["category", "region"] if c in df.columns), None)
    if not group_col:
        return

    if "prior_week_units_cleared" in df.columns and "promo_week_units_cleared" in df.columns:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Prior Week",
            x=df[group_col],
            y=df["prior_week_units_cleared"],
            marker_color="#4b5563",
        ))
        fig.add_trace(go.Bar(
            name="Promo Week",
            x=df[group_col],
            y=df["promo_week_units_cleared"],
            marker_color="#7c3aed",
        ))
        fig.update_layout(
            title=f"Stock Clearance: Prior Week vs Promo Week — {campaign_id}",
            barmode="group",
            plot_bgcolor="#0e0e1a",
            paper_bgcolor="#0e0e1a",
            font_color="#e5e7eb",
            legend=dict(bgcolor="#1e1e2e"),
            xaxis=dict(gridcolor="#2e2e3e"),
            yaxis=dict(gridcolor="#2e2e3e", title="Units Cleared"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Delta % bar
    if "inventory_delta_pct" in df.columns:
        df_sorted = df.sort_values("inventory_delta_pct", ascending=False)
        fig2 = go.Figure(go.Bar(
            x=df_sorted[group_col],
            y=df_sorted["inventory_delta_pct"],
            marker_color="#7c3aed",
            text=[f"{v:.1f}%" for v in df_sorted["inventory_delta_pct"]],
            textposition="outside",
        ))
        fig2.update_layout(
            title="Inventory Clearance Improvement %",
            plot_bgcolor="#0e0e1a",
            paper_bgcolor="#0e0e1a",
            font_color="#e5e7eb",
            xaxis=dict(gridcolor="#2e2e3e"),
            yaxis=dict(gridcolor="#2e2e3e", title="Delta %"),
        )
        st.plotly_chart(fig2, use_container_width=True)


def chart_campaign_impact_by_product(df: pd.DataFrame, campaign_id: str):
    """Top SKUs by uplift — horizontal bar + treemap."""
    if df.empty:
        return

    name_col = next((c for c in ["sku_name", "sku_code"] if c in df.columns), None)
    uplift_col = _find_pct_uplift_col(df)

    if not name_col or not uplift_col:
        return

    df_sorted = df.sort_values(uplift_col, ascending=False).head(10)

    col1, col2 = st.columns(2)

    # Top 10 horizontal bar
    fig = go.Figure(go.Bar(
        x=df_sorted[uplift_col],
        y=df_sorted[name_col],
        orientation="h",
        marker_color=px.colors.sequential.Purples_r[:len(df_sorted)],
        text=[f"{v:.1f}%" for v in df_sorted[uplift_col]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Top 10 SKUs by Uplift %",
        plot_bgcolor="#0e0e1a",
        paper_bgcolor="#0e0e1a",
        font_color="#e5e7eb",
        xaxis=dict(gridcolor="#2e2e3e", title="Uplift %"),
        yaxis=dict(gridcolor="#2e2e3e", autorange="reversed"),
    )
    col1.plotly_chart(fig, use_container_width=True)

    # Volume treemap
    volume_col = next((c for c in ["promo_sales_units", "promo_units"] if c in df.columns), None)
    if volume_col:
        fig2 = px.treemap(
            df_sorted,
            path=[name_col],
            values=volume_col,
            color=uplift_col,
            color_continuous_scale="Purples",
            title="SKU Volume Share (sized by units, coloured by uplift)",
        )
        fig2.update_layout(
            paper_bgcolor="#0e0e1a",
            font_color="#e5e7eb",
        )
        col2.plotly_chart(fig2, use_container_width=True)


def render_charts(result, intent: str, campaign_id: str):
    """Route to the right chart function based on intent."""
    df = result.validation.get("result_df", pd.DataFrame())
    if df.empty:
        return
    # Drop flagged columns before charting
    df = df[[c for c in df.columns if not c.endswith("_flagged")]].copy()

    st.markdown("### 📊 Visualisation")
    try:
        if intent == "promotional_performance":
            chart_promotional_performance(df, campaign_id)
        elif intent == "regional_comparison":
            # Fall back to promotional chart if region column missing
            if "region" in df.columns:
                chart_regional_comparison(df, campaign_id)
            else:
                chart_promotional_performance(df, campaign_id)
        elif intent == "inventory_movement":
            chart_inventory_movement(df, campaign_id)
        elif intent == "campaign_impact_by_product":
            chart_campaign_impact_by_product(df, campaign_id)
        else:
            chart_promotional_performance(df, campaign_id)
    except Exception as e:
        st.warning(f"Could not render chart: {e}")


def _find_pct_uplift_col(df: pd.DataFrame):
    """Find the column that contains percentage uplift values (not absolute units)."""
    candidates = [c for c in df.columns if "uplift" in c.lower() and "flagged" not in c]
    for col in candidates:
        vals = df[col].dropna()
        if len(vals) > 0 and vals.abs().max() < 1000:  # pct values are small; unit values are large
            return col
    return None

def _find_volume_col(df: pd.DataFrame):
    preferred = ["promo_sales_units", "promo_units", "total_promo_sales",
                 "promo_week_units_cleared", "promo_week_cleared"]
    for c in preferred:
        if c in df.columns:
            return c
    # fallback: any column with "promo" and "unit" or "sales"
    for c in df.columns:
        if "promo" in c.lower() and ("unit" in c.lower() or "sales" in c.lower()):
            return c
    return None

def _find_baseline_col(df: pd.DataFrame):
    preferred = ["baseline_sales_units", "total_baseline_sales", "baseline_units",
                 "prior_week_units_cleared", "prior_week_cleared"]
    for c in preferred:
        if c in df.columns:
            return c
    return None

def render_kpi_cards(df: pd.DataFrame, intent: str):
    """Top-line KPI metrics above the charts."""
    if df.empty:
        return

    uplift_col  = _find_pct_uplift_col(df)
    volume_col  = _find_volume_col(df)
    baseline_col = _find_baseline_col(df)

    cols = st.columns(4)
    if uplift_col:
        avg_uplift = df[uplift_col].mean()
        max_uplift = df[uplift_col].max()
        cols[0].metric("Avg Uplift %", f"{avg_uplift:.1f}%")
        cols[1].metric("Peak Uplift %", f"{max_uplift:.1f}%")
    else:
        cols[0].metric("Avg Uplift %", "N/A")
        cols[1].metric("Peak Uplift %", "N/A")
    if volume_col:
        cols[2].metric("Total Promo Units", f"{df[volume_col].sum():,.0f}")
    if baseline_col:
        cols[3].metric("Total Baseline Units", f"{df[baseline_col].sum():,.0f}")


# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 FMCG Analytics")
    st.caption("AI Analytics Assistant · Powered by Groq")
    st.divider()
    st.markdown("**Example questions:**")
    examples = [
        "Did the February campaign improve sales in the South?",
        "Which categories saw inventory reduction during the summer campaign?",
        "How did the North compare to the South in Q1?",
        "Which SKUs had the highest uplift from the FEB_2025 campaign?",
        "How did the winter campaign perform across all regions?",
        "Which region had the best uplift in the summer campaign?",
    ]
    for ex in examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state["prefill"] = ex

    st.divider()
    st.caption("Pipeline:")
    st.caption("Orchestrator → Intent → Vocabulary → Query → Validation → Narrative")
    st.divider()
    if st.session_state.get("history"):
        st.metric("Queries this session", len(st.session_state["history"]))

# ── Session State ─────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ── Header ────────────────────────────────────────────────────────────────
st.title("FMCG Beverages Analytics Assistant")
st.caption("Ask questions about promotional performance, inventory, regional sales, and campaign impact.")

# ── Query Input ───────────────────────────────────────────────────────────
prefill = st.session_state.pop("prefill", "")
user_query = st.chat_input("Ask a question about your promotions...")
if prefill and not user_query:
    user_query = prefill

if user_query:
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        progress_msgs = []

        def on_step(msg: str):
            progress_msgs.append(msg)
            status_placeholder.markdown("\n\n".join(progress_msgs))

        result = run_pipeline(user_query, on_step=on_step)
        status_placeholder.empty()

        if result.status == "success":
            intent = result.intent.get("intent", "")
            campaign_id = result.enriched_context.get("campaign_id", "")
            df = result.validation.get("result_df", pd.DataFrame())

            # Headline answer
            st.markdown(
                f'<div class="headline-box"><strong>{result.narrative.get("headline", "")}</strong>'
                f'<br><br>{result.narrative.get("body", "")}</div>',
                unsafe_allow_html=True,
            )

            # Caveats
            for caveat in result.narrative.get("caveats", []):
                st.warning(caveat)

            # KPI cards
            if not df.empty:
                render_kpi_cards(df, intent)

            # Charts
            render_charts(result, intent, campaign_id)

            # Raw data table
            if not df.empty:
                with st.expander("📋 View underlying data"):
                    display_df = df[[c for c in df.columns if not c.endswith("_flagged")]]
                    st.dataframe(display_df, use_container_width=True)

            # Debug: show raw dataframe columns + sample
            with st.expander("🔬 Debug: raw data returned"):
                st.write("**Columns:**", df.columns.tolist())
                st.dataframe(df.head(5), use_container_width=True)

            # Pipeline details
            with st.expander("🔍 Pipeline details"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Intent", intent.replace("_", " ").title())
                c2.metric("Confidence", f"{round(result.intent.get('confidence', 0) * 100)}%")
                c3.metric("Campaign", campaign_id or "—")
                c4.metric("Latency", f"{result.total_latency_ms}ms")
                if result.query_result.get("sql"):
                    st.code(result.query_result["sql"], language="sql")

        elif result.status == "clarification_needed":
            st.info(result.formatted_answer)
        elif result.status == "blocked":
            st.error(result.formatted_answer)
        else:
            st.error(f"Pipeline error: {result.error}")

    st.session_state.history.append({
        "query": user_query,
        "answer": result.formatted_answer,
        "status": result.status,
        "intent": result.intent.get("intent"),
    })

# ── History ───────────────────────────────────────────────────────────────
if len(st.session_state.history) > 1:
    with st.expander(f"📜 Query history ({len(st.session_state.history)} queries)"):
        for item in reversed(st.session_state.history[:-1]):
            st.markdown(f"**Q:** {item['query']}")
            st.markdown(f"**A:** {item['answer'][:200]}{'...' if len(item['answer']) > 200 else ''}")
            st.divider()