"""Data Catalog page: what IRIS covers, live from the database and metrics.yaml, filtered by the persona's
row-level security. Nothing here is hardcoded: counts, months, ranges and accuracy are read when the page
opens. Every card has an "Ask IRIS" button, and every table row can be sent to Chat as a prefilled
question (select the row, then "Ask IRIS"). The same content is exported to docs/data_manual.md
(`make data-manual`).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.semantic import catalog as K
from app.semantic import time_intel as ti
from app.ui import branding as B
from app.ui import common as C

TABS = ["Overview", "Organisation", "Metrics & P&L lines", "Ratios", "Versions & periods", "Landing",
        "Data & sources", "Capabilities"]


# ------------------------------------------------------------------------------------------ cached reads
@st.cache_data(ttl=600, show_spinner=False)
def _coverage(user_id: str, as_of: date) -> dict:
    cov = K.coverage(user_id, as_of)
    snap = cov.pop("landing")
    cov["landing_text"] = (f"{snap.run_at:%Y-%m-%d %H:%M}" if snap and snap.run_at else "not computed yet")
    return cov


@st.cache_data(ttl=600, show_spinner=False)
def _revenue_heatmap(user_id: str, as_of: date) -> pd.DataFrame:
    return K.revenue_heatmap(user_id, as_of)


@st.cache_data(ttl=600, show_spinner=False)
def _ratios(user_id: str) -> pd.DataFrame:
    return K.ratio_rows(user_id)


@st.cache_data(ttl=600, show_spinner=False)
def _describe(kind: str, user_id: str, as_of: date) -> tuple[pd.DataFrame, str]:
    r = K.describe(kind, user_id, as_of=as_of)
    return r.df, r.description


@st.cache_data(ttl=600, show_spinner=False)
def _row_counts(user_id: str) -> pd.DataFrame:
    return K.version_row_counts(user_id)


@st.cache_data(ttl=600, show_spinner=False)
def _backtest(user_id: str) -> dict:
    return K.backtest_tables(user_id)


# ------------------------------------------------------------------------------------------ widgets
def _queue(question: str) -> None:
    st.session_state.pending = question
    st.session_state.nav_goto = "chat"


def ask_button(question: str, key: str, label: str = f"💬 Ask {B.APP_NAME}") -> None:
    st.button(label, key=key, help=question, on_click=_queue, args=(question,))


def card(col, label: str, value: str, question: str, key: str) -> None:
    with col:
        st.markdown(f"<div class='iris-card'><div class='v'>{C.esc(value)}</div><div class='l'>{C.esc(label)}</div></div>",
                    unsafe_allow_html=True)
        ask_button(question, f"card_{key}")


def table_with_ask(df: pd.DataFrame, key: str, question_for, height: int | None = None) -> None:
    """Interactive table; selecting a row offers an 'Ask IRIS' button with a question about that row."""
    if df is None or df.empty:
        st.caption("No rows in your scope.")
        return
    ev = st.dataframe(df, key=f"tbl_{key}", hide_index=True, width="stretch", on_select="rerun",
                      selection_mode="single-row", height=height or "auto")
    rows = (ev.selection.rows if ev is not None and hasattr(ev, "selection") else []) or []
    if rows:
        q = question_for(df.iloc[rows[0]])
        c1, c2 = st.columns([1, 4])
        with c1:
            ask_button(q, f"ask_{key}")
        c2.caption(q)
    else:
        st.caption(f"Select a row, then **Ask {B.APP_NAME}** to open Chat with a question about it.")


# ------------------------------------------------------------------------------------------ tabs
def _overview(user_id: str, as_of: date) -> None:
    cov = _coverage(user_id, as_of)
    open_lbl, last_lbl = ti.month_label(cov["open_month"]), ti.month_label(cov["last_closed"])
    mname = ti.MONTH_NAMES[cov["open_month"] % 100 - 1]
    cards = [
        ("Regions", cov["regions"], "Which regions are in scope?"),
        ("Countries", cov["countries"], "Which countries are in scope?"),
        ("Product lines", cov["product_lines"], "Which product lines can I ask about?"),
        ("Businesses", cov["businesses"], "Which businesses can I ask about?"),
        ("Business units", cov["bus"], "List the business units in my scope"),
        ("Leaf accounts", cov["accounts"], "List all P&L lines"),
        ("First month", ti.month_label(cov["first_month"]), "Show revenue by month since 2022"),
        ("Last closed month", last_lbl, f"How is operating profit in {last_lbl} vs budget?"),
        ("Next close date", cov["next_close"].isoformat(), "What periods and close dates do you cover?"),
        ("Open (landing) month", open_lbl, f"What's the {mname} landing?"),
        ("Last landing refresh", cov["landing_text"], "Explain the landing"),
    ]
    for start in range(0, len(cards), 6):
        cols = st.columns(6)
        for col, (label, value, q) in zip(cols, cards[start:start + 6]):
            card(col, label, str(value), q, label.lower().replace(" ", "_").replace("(", "").replace(")", ""))
    st.markdown("#### Coverage by country and product line")
    view = st.radio("Show", ["Business units", f"Revenue YTD {last_lbl} ({C.CUR} M)"], horizontal=True,
                    key="cat_heat_view", label_visibility="collapsed")
    if view == "Business units":
        mat, fmt, title = K.bu_heatmap(user_id), "d", "Number of BUs"
    else:
        mat = _revenue_heatmap(user_id, as_of) / 1e6
        fmt, title = ".1f", f"Revenue YTD {last_lbl}, {C.CUR} M"
    if mat is None or mat.empty:
        st.caption("No data in your scope.")
        return
    fig = go.Figure(go.Heatmap(z=mat.values, x=list(mat.columns), y=list(mat.index), colorscale="Teal",
                               text=mat.values, texttemplate="%{text:" + fmt + "}", hoverongaps=False,
                               colorbar={"title": title}))
    fig.update_layout(height=120 + 34 * len(mat.index), margin={"l": 10, "r": 10, "t": 10, "b": 10},
                      xaxis={"side": "top"}, yaxis={"autorange": "reversed"})
    st.plotly_chart(fig, width="stretch", key="cat_heatmap")
    c1, c2 = st.columns([1, 1])
    country = c1.selectbox("Ask about a country and product line", list(mat.index), key="cat_heat_country")
    pl = c2.selectbox("Product line", list(mat.columns), key="cat_heat_pl", label_visibility="hidden")
    ask_button(f"How is {country} {pl} doing YTD vs budget?", "heat_ask")


def _organisation(user_id: str) -> None:
    df = K.org_table(user_id)
    if df.empty:
        st.caption("No organisation units in your scope.")
        return
    tree = df.assign(Group=C.COMPANY, n=1)
    fig = go.Figure(go.Sunburst(**_sunburst(tree), branchvalues="total", maxdepth=3,
                                marker={"colorscale": "Teal"}))
    fig.update_layout(height=520, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(fig, width="stretch", key="cat_sunburst")
    st.caption("Click a segment to zoom in (group > region > country > product line > business > BU).")
    q = st.text_input("Search the organisation", key="cat_org_search", placeholder="e.g. Toronto, Metals, MX-")
    view = df
    if q:
        mask = pd.Series(False, index=df.index)
        for c in df.columns:
            mask |= df[c].astype(str).str.contains(q, case=False, regex=False)
        view = df[mask]
    table_with_ask(view, "org", lambda r: f"How is {r['BU']} doing YTD vs budget?", height=380)


def _sunburst(df: pd.DataFrame) -> dict:
    levels = ["Group", "Region", "Country", "Product line", "Business", "BU"]
    ids, labels, parents, values = [], [], [], []
    for depth, lvl in enumerate(levels):
        keys = levels[:depth + 1]
        g = df.groupby(keys)["n"].sum().reset_index()
        for _, r in g.iterrows():
            ids.append("/".join(str(r[k]) for k in keys))
            labels.append(str(r[lvl]))
            parents.append("/".join(str(r[k]) for k in keys[:-1]) if depth else "")
            values.append(int(r["n"]))
    return {"ids": ids, "labels": labels, "parents": parents, "values": values}


def _metrics() -> None:
    st.markdown("P&L lines are shown by name; subtotals (revenue, production, gross profit, operating profit, EBIT, "
                "net income) are computed from the accounts by the semantic layer, never stored.")
    st.markdown("#### P&L lines and their accounts")
    table_with_ask(K._line_rows(), "lines", lambda r: f"Show {r['P&L line'].lower()} by month this year vs last year")
    st.markdown("#### All metrics")
    table_with_ask(K._metric_rows(), "metrics", lambda r: f"How is {r['Metric'].lower()} YTD vs budget?")


def _ratios_tab(user_id: str) -> None:
    st.markdown("Every ratio is computed as a **ratio of sums** at the level you ask for; a zero or negative "
                "denominator shows *n/a*. Asking for *profit %*, *margin* or *MAOP %* without a base returns "
                "both operating margins side by side: **on revenue** and **on production**.")
    with st.spinner("Computing typical ranges ..."):
        df = _ratios(user_id)
    table_with_ask(df, "ratios", lambda r: (f"What is our {r['Ratio'].lower()} YTD vs budget?"
                                            if not r["Ratio"].startswith("Profit %") else "What is our profit % YTD?"))


def _versions(user_id: str, as_of: date) -> None:
    vdf, vdesc = _describe("versions", user_id, as_of)
    st.markdown(vdesc)
    table_with_ask(vdf, "versions", lambda r: (f"Compare {r['Version']} vs Actual YTD" if r["Version"] not in
                                               ("Actual", "Landing") else
                                               ("What's the landing this month?" if r["Version"] == "Landing"
                                                else "How is operating profit YTD vs last year?")))
    pdf, pdesc = _describe("periods", user_id, as_of)
    st.markdown("#### Periods")
    st.markdown(pdesc)
    table_with_ask(pdf, "periods", lambda r: f"How is revenue {r['Example']} vs budget?")
    st.markdown("#### Close calendar")
    table_with_ask(K.close_schedule(as_of), "close",
                   lambda r: (f"How is operating profit in {r['Month']} vs budget?" if r["Status"] == "Closed"
                              else ("What's the landing this month?" if r["Status"].startswith("Open")
                                    else f"What is the latest forecast for {r['Month']}?")))


def _landing(user_id: str, as_of: date) -> None:
    st.markdown(K.LANDING_METHOD_TEXT)
    pdf, _ = _describe("billing_patterns", user_id, as_of)
    st.markdown("#### Billing patterns")
    table_with_ask(pdf, "patterns", lambda r: f"Which {r['Pattern'].split(' (')[0].lower()} BUs will miss budget this month?")
    bus, _ = _describe("business_units", user_id, as_of)
    if "Billing pattern" in bus.columns:
        st.markdown("#### Pattern class per BU")
        table_with_ask(bus[["BU", "Business", "Country", "Billing pattern"]], "bu_patterns",
                       lambda r: f"Explain the landing for {r['BU']}", height=320)
    bt = _backtest(user_id)
    st.markdown("#### Measured accuracy (backtest)")
    if not bt:
        st.info("No backtest has been run yet: `make backtest` measures the landing on the last 24 closed months.")
        return
    st.caption(f"Measured by `make backtest` (run {bt['run_date']}) over the last 24 closed months, using only the "
               "data available at each point in time. WAPE = sum of absolute errors / sum of actuals.")
    for key, title in (("group", "Group level, by method"), ("coverage", "Actual inside the P10-P90 range"),
                       ("pattern", "BU billing error by pattern class"), ("product_line", "BU billing error by product line")):
        if key in bt:
            st.markdown(f"**{title}**")
            st.dataframe(bt[key], hide_index=True, width="stretch")


def _sources(user_id: str, as_of: date) -> None:
    cov = _coverage(user_id, as_of)
    rec = K.reconcile_status()
    if rec is None:
        st.warning("Reconciliation: not run yet (`make reconcile`).")
    elif rec["mismatches"] == 0 and rec["integrity_failures"] == 0:
        st.success(f"Reconciled: 0 mismatches in {rec['checks']} subtotal checks and no integrity failures "
                   f"(last `make reconcile` {rec['run_at']}).")
    else:
        st.error(f"Reconciliation: {rec['mismatches']} mismatches, {rec['integrity_failures']} integrity failures "
                 f"(last run {rec['run_at']}).")
    st.markdown(
        f"- **Storage:** leaf accounts only, monthly, in {C.CUR}; subtotals and ratios are computed by the semantic "
        "layer from `metrics.yaml`.\n"
        f"- **Refresh:** {K.REFRESH_TEXT.format(close_day=cov['close_day'])}\n"
        f"- **Coverage:** {ti.month_label(cov['first_month'])} to {ti.month_label(cov['last_closed'])} (closed), "
        f"landing for {ti.month_label(cov['open_month'])}.")
    st.markdown("#### Lineage")
    st.graphviz_chart(K.LINEAGE_DOT)
    st.markdown("#### Stored rows per version (your scope)")
    table_with_ask(_row_counts(user_id), "rows", lambda r: f"Compare {r['Version']} vs Actual for the group this year")
    st.markdown("#### Assumptions")
    st.markdown("\n".join(f"- {a.format(close_day=cov['close_day'])}" for a in K.ASSUMPTIONS))
    st.caption(f"The same content is in docs/data_manual.md ({B.APP_NAME} repository), regenerated by `make data-manual`.")


def _capabilities() -> None:
    df = pd.DataFrame(K.CAPABILITIES, columns=["Capability", "Example question"])
    table_with_ask(df, "caps", lambda r: r["Example question"])
    st.markdown("#### Example questions by intent")
    ex = pd.DataFrame(K.EXAMPLES, columns=["Intent", "Example question"])
    table_with_ask(ex, "examples", lambda r: r["Example question"])


def render() -> None:
    cfg = st.session_state["cfg"]
    user_id, as_of = cfg["user_id"], cfg["as_of"]
    st.markdown("## Data Catalog")
    st.caption("Live from the database and the metric definitions, filtered by your data access. "
               "Synthetic data generated for this prototype; structure mirrors the target model.")
    tabs = st.tabs(TABS)
    with tabs[0]:
        _overview(user_id, as_of)
    with tabs[1]:
        _organisation(user_id)
    with tabs[2]:
        _metrics()
    with tabs[3]:
        _ratios_tab(user_id)
    with tabs[4]:
        _versions(user_id, as_of)
    with tabs[5]:
        _landing(user_id, as_of)
    with tabs[6]:
        _sources(user_id, as_of)
    with tabs[7]:
        _capabilities()
