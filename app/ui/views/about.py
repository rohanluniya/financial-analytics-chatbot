"""About page: what IRIS is, why it exists, scope, how it works, trust and version information."""
from __future__ import annotations

import streamlit as st

from app.semantic import time_intel as ti
from app.ui import branding as B
from app.ui import common as C

HOW_IT_WORKS_DOT = """
digraph {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#E6F4F1", color="#0F766E", fontname="Helvetica", fontsize=11];
  edge [color="#3730A3"];
  q [label="Your question\\n(plain English)", fillcolor="#EEF0FB", color="#3730A3"];
  a [label="AI assistant\\nchooses the query,\\nnever guesses numbers"];
  m [label="Governed metric\\ndefinitions"];
  s [label="Secure data access\\n(row-level security,\\nread-only)"];
  l [label="Landing engine\\n(separate, tested\\ncalculation)"];
  o [label="Answer:\\ninsight + table + chart", fillcolor="#EEF0FB", color="#3730A3"];
  q -> a; a -> m -> s -> o; a -> l -> o;
}
"""


def _live_facts(user_id: str, as_of) -> tuple[str, str]:
    """Last closed month (from the as-of date) and the last landing run, read live from landing_run."""
    last = ti.month_label(ti.last_closed_month(as_of))
    try:
        from app.db import get_engine
        from app.landing.query import last_refresh
        snap = last_refresh(get_engine(user_id))
    except Exception:  # noqa: BLE001 - the page must render before the first landing run
        snap = None
    if snap is None:
        return last, "not computed yet (run `make landing`)"
    when = snap.run_at.strftime("%Y-%m-%d %H:%M") if snap.run_at else snap.snapshot_date.isoformat()
    return last, f"{when} (landing for {snap.label}, as of {snap.snapshot_date.isoformat()})"


def render() -> None:
    cfg = st.session_state["cfg"]
    st.markdown(f"## About {B.APP_NAME}")
    st.markdown(
        f"**{B.APP_NAME}** ({B.APP_FULL_NAME}) is a conversational analytics assistant for leaders across all "
        f"businesses of {C.COMPANY}. Ask a question in plain English and get a short insight, a finance-style "
        "table and the most relevant chart.")
    st.markdown("#### Why it exists")
    st.markdown(
        "- Dashboards can't anticipate every question.\n"
        "- Every leader analyses differently: some start from billing, some from production, some from ratios.\n"
        f"- {B.APP_NAME} adapts to the user, instead of the user adapting to a dashboard.")
    st.markdown("#### Current scope")
    st.markdown(
        "- Monthly general-ledger (GL) P&L from billing to operating profit (and on to net income), by organisation "
        "level: group, region, country, product line, business and BU.\n"
        "- Actual, Budget, FC1, FC2 and FC3, from January 2022 to the latest closed month.\n"
        "- A **current-month landing** estimate: billing, revenue, production, operating profit and both operating "
        "margins (on revenue and on production).\n"
        "- Operational statistics (FTE, hours, utilization) and fictional employee records (headcount, hires, "
        "leavers, attrition).")
    st.markdown("#### Roadmap")
    st.markdown(
        "- Beyond finance: pipeline, customer and quality data in the same conversational way.\n"
        "- Single sign-on and the company's own entitlements instead of the demo sign-in and personas.\n"
        "- A managed language model endpoint (for example the enterprise's OpenAI service) instead of local models.\n"
        "- Month-to-date billing as an optional input to the landing once a daily feed exists.")
    st.markdown("#### How it works")
    st.markdown(
        "1. **Governed metric definitions** say exactly how every line and ratio is calculated.\n"
        "2. **Secure data access** reads the data with row-level security and a read-only login.\n"
        "3. **The AI assistant** chooses the right query for your question. It never guesses or calculates numbers.\n"
        "4. **You get** a table, a chart and a short insight.\n\n"
        "The landing estimate comes from a separate, tested calculation, not from the language model.")
    st.graphviz_chart(HOW_IT_WORKS_DOT)
    st.markdown("#### Trust and security")
    st.markdown(
        "- Every number comes from the database or the landing engine.\n"
        "- A numeric guardrail checks every number in the text against the data before you see it.\n"
        "- Row-level security per user: you only see the businesses you have access to.\n"
        "- Read-only access to the finance data.\n"
        "- *How I got this* under each answer shows the filters, the tool call and the SQL.")
    last, refreshed = _live_facts(cfg["user_id"], cfg["as_of"])
    st.markdown("#### This version")
    st.markdown(f"- {B.AUTHOR_LINE}\n- Version {B.VERSION}\n- Last closed month: {last}\n"
                f"- Last landing refresh: {refreshed}")
