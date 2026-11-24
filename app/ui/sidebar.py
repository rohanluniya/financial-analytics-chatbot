"""Sidebar: quick guide, settings, scope filters, conversations and the footer.

Scope filters cascade Region -> Country -> Product line -> Business -> BU. Their options come from the
organisation dimension filtered by the persona's row-level security, so a United States Country Head only
sees the United States and its children. The filters are the default context of every question: a scope or
period named in the question wins, and the answer lists which filters were applied.
"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from app.config import backend, data_as_of_date, settings
from app.semantic import time_intel as ti
from app.semantic.access import allowed_bus, scope_label
from app.semantic.dims import dims
from app.ui import branding as B
from app.ui import common as C

QUICK_TIPS = """
1. **Ask in plain English** with a measure, a scope, a period and a comparison, for example
   *"How is operating profit YTD vs budget for Canada?"*
2. **Use the scope filters** in the sidebar as the default context. A business or period named in the
   question wins for that question, and the answer says which filters were applied.
3. **Ask about the current month:** *"What's the November landing for the United States?"* gives the
   expected month-end with a P10-P90 range; *"What will YTD margin be through November including the
   landing?"* adds it to the closed months.
4. **Keep the conversation going:** *"now for Mexico"*, *"no, I meant Q3"*, *"why?"*. If something looks
   wrong, say *"that's not right"* to see exactly what was used and change it.
5. **Check the source:** open *How I got this* under any answer for the filters, the tool call and the SQL,
   and download the table as CSV or Excel.
"""
LEVELS = [("l2_region", "Region", "flt_region"), ("l3_country", "Country", "flt_country"),
          ("l4_product_line", "Product line", "flt_pl"), ("l5_business", "Business", "flt_business"),
          ("l6_bu", "BU", "flt_bu")]
PLURAL = {"Region": "regions", "Country": "countries", "Product line": "product lines", "Business": "businesses",
          "BU": "BUs"}
VERSIONS = ["Default (Actual vs PY and Budget)", "Actual", "Budget", "FC1", "FC2", "FC3", "Latest forecast",
            "Landing (current month)"]
VERSION_CODE = {"Actual": "Actual", "Budget": "Budget", "FC1": "FC1", "FC2": "FC2", "FC3": "FC3",
                "Latest forecast": "LatestFC", "Landing (current month)": "Landing"}
PERIOD_TYPES = ["Default (YTD)", "Month", "QTD", "YTD", "Rolling 12M", "Full year"]
PTYPE_CODE = {"Month": "MONTH", "QTD": "QTD", "YTD": "YTD", "Rolling 12M": "R12M", "Full year": "FY"}
FILTER_KEYS = [k for _, _, k in LEVELS] + ["flt_version", "flt_ptype", "flt_period"]


@st.dialog("Quick guide")
def quick_guide() -> None:
    st.markdown(QUICK_TIPS)
    st.button("Open the full User Guide", type="primary", key="qg_open_guide", on_click=C.queue_page, args=("guide",))


def clear_filters() -> None:
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def _persona_changed() -> None:
    """Callback: a new persona starts a new conversation with no filters (its data access differs)."""
    st.session_state.persona = st.session_state.persona_select
    C.new_conversation()
    clear_filters()


def _settings() -> dict:
    with st.expander("Settings", expanded=False):
        if "persona_select" not in st.session_state:
            st.session_state.persona_select = st.session_state.persona
        persona = st.selectbox("Persona", list(C.PERSONAS), key="persona_select", on_change=_persona_changed)
        user_id = C.PERSONAS[persona]
        st.markdown(f"<div class='rl-scope'>Data access: <b>{C.esc(scope_label(user_id))}</b></div>",
                    unsafe_allow_html=True)
        max_d = data_as_of_date()
        as_of = st.date_input("As-of date", value=max_d, min_value=date(2022, 2, 6), max_value=max_d,
                              help="Moves the point in time back: closed months and available forecasts follow.")
        choices = C.model_choices()
        if st.session_state.get("model_select") not in choices:   # first run: honour ?model= once
            wanted = st.session_state.get("model_param") or str(st.query_params.get("model", "")).strip().lower()
            st.session_state.model_select = next((c for c in choices if wanted and c.lower().startswith(wanted)),
                                                 choices[0])
        model = st.selectbox("Model (LiteLLM)", choices, key="model_select",
                             help="'rules (no LLM)' uses the deterministic router and templated text.")
        units = st.radio("Units", [f"{C.CUR} k", f"{C.CUR} M"], horizontal=True, index=0)
    return {"user_id": user_id, "as_of": as_of, "model": None if model.startswith("rules") else model,
            "model_label": model, "units": "M" if units.endswith("M") else "k"}


def _prune(key: str, options: list[str]) -> None:
    """Drop selections that are no longer valid after a parent filter changed (cascade)."""
    cur = st.session_state.get(key)
    if cur:
        st.session_state[key] = [v for v in cur if v in options]


def _filters(user_id: str, as_of: date) -> dict:
    org = dims().org
    org = org[org["bu_id"].isin(allowed_bus(user_id))]
    with st.expander("Scope filters", expanded=True):
        org_filter = {}
        scope = org
        for level, label, key in LEVELS:
            options = sorted(scope[level].unique().tolist())
            _prune(key, options)
            sel = st.multiselect(label, options, key=key, placeholder=f"All {PLURAL[label]} in your scope")
            if sel:
                org_filter[level] = sel
                scope = scope[scope[level].isin(sel)]
        version = st.selectbox("Version", VERSIONS, key="flt_version")
        last = ti.last_closed_month(as_of)
        open_key = ti.add_months(last, 1)
        period = None
        if version == "Landing (current month)":
            st.selectbox("Period", [ti.month_label(open_key)], disabled=True, key="flt_period_landing",
                         help="The landing exists for the open month only.")
            period = ti.Period("MONTH", open_key).to_dict()
        else:
            ptype = st.selectbox("Period type", PERIOD_TYPES, key="flt_ptype")
            if ptype != PERIOD_TYPES[0]:
                if ptype == "Full year":
                    years = list(range(ti.ym(last)[0], ti.data_bounds()[0] // 100 - 1, -1))
                    labels = [f"FY {y}" for y in years]
                    _prune_single("flt_period", labels)
                    pick = st.selectbox("Period", labels, key="flt_period")
                    period = ti.Period("FY", ti.mk(int(pick[3:]), 12)).to_dict()
                else:
                    months = ti.month_range(ti.data_bounds()[0], last)[::-1]
                    labels = [ti.month_label(k) for k in months]
                    _prune_single("flt_period", labels)
                    pick = st.selectbox("Period (closed months)", labels, key="flt_period")
                    period = ti.Period(PTYPE_CODE[ptype], months[labels.index(pick)]).to_dict()
        st.button("Clear filters", width="stretch", on_click=clear_filters, key="clear_filters")
    ui = {}
    if org_filter:
        ui["org_filter"] = org_filter
    if version != VERSIONS[0]:
        ui["version"] = VERSION_CODE[version]
    if period:
        ui["period"] = period
    return ui


def _prune_single(key: str, options: list[str]) -> None:
    if st.session_state.get(key) not in (None, *options):
        st.session_state.pop(key, None)


def filter_chips(ui: dict) -> list[str]:
    out = []
    labels = {lvl: lab for lvl, lab, _ in LEVELS}
    for lvl, vals in (ui.get("org_filter") or {}).items():
        out.append(f"{labels[lvl]}: {', '.join(vals)}")
    if ui.get("version"):
        out.append(f"Version: {next((k for k, v in VERSION_CODE.items() if v == ui['version']), ui['version'])}")
    if ui.get("period"):
        out.append(f"Period: {ui['period'].get('label')}")
    return out


def relative_time(ts: datetime) -> str:
    if ts is None:
        return ""
    secs = (datetime.now() - ts).total_seconds()
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    days = int(secs // 86400)
    return "yesterday" if days == 1 else f"{days} days ago"


def _conversations(user_key: str) -> None:
    st.markdown("**Conversations**")
    if st.button("➕ New conversation", width="stretch", key="new_conv"):
        C.new_conversation()
        st.rerun()
    store = C.history_store()
    if store is None:
        st.caption("Conversation history is not available (database not reachable).")
        return
    try:
        convs = store.list(user_key)
    except Exception as exc:  # noqa: BLE001
        st.caption(f"Conversation history is not available: {type(exc).__name__}.")
        return
    if not convs:
        st.caption("Your last 10 conversations will appear here.")
    active = st.session_state.get("active_cid")
    for c in convs:
        cols = st.columns([5, 1])
        mark = "📌 " if c.is_pinned else ""
        cur = "▸ " if c.conversation_id == active else ""
        label = f"{cur}{mark}{C.md_escape(c.title)} · {relative_time(c.updated_at)}"
        if cols[0].button(label, key=f"conv_{c.conversation_id}", width="stretch",
                          type="primary" if c.conversation_id == active else "secondary"):
            C.open_conversation(c.conversation_id)
            st.rerun()
        with cols[1].popover("⋯", help="Rename, pin or delete"):
            new = st.text_input("Rename", value=c.title, key=f"ren_{c.conversation_id}", max_chars=120)
            if st.button("Save name", key=f"ren_btn_{c.conversation_id}"):
                store.rename(user_key, c.conversation_id, new)
                st.rerun()
            if st.button("Unpin" if c.is_pinned else "Pin to top", key=f"pin_{c.conversation_id}"):
                store.pin(user_key, c.conversation_id, not c.is_pinned)
                st.rerun()
            confirm = st.checkbox("Yes, delete this conversation", key=f"delc_{c.conversation_id}")
            if st.button("Delete", key=f"del_{c.conversation_id}", disabled=not confirm):
                store.delete(user_key, c.conversation_id)
                if active == c.conversation_id:
                    C.new_conversation()
                st.rerun()
    st.caption("The last 10 are kept; pinned ones stay on top and count toward the 10.")


def render() -> dict:
    with st.sidebar:
        if st.button("❓ Quick guide", width="stretch"):
            quick_guide()
        who = st.session_state.get("auth_name")
        if who:
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            c1.caption(f"Signed in as **{C.md_escape(who)}**")
            c2.button("Sign out", key="sign_out", on_click=C.sign_out, width="stretch")
        cfg = _settings()
        cfg["ui_filters"] = _filters(cfg["user_id"], cfg["as_of"])
        st.divider()
        _conversations(st.session_state.get("auth_user") or "")
        st.divider()
        last = ti.last_closed_month(cfg["as_of"])
        st.caption(f"Backend: {backend()} · last closed month: {ti.month_label(last)} · {C.CUR} at "
                   f"{settings().get('fx_rate_label', 'constant budget rate')}")
        st.caption(B.footer_line())
    st.session_state["cfg"] = cfg
    return cfg
