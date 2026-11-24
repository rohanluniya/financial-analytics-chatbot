"""Shared UI pieces for every IRIS page: theme CSS, header, session state, sign-in, conversation history and
answer rendering.

Only branding constants and data values are ever passed through HTML; user and LLM text is rendered with
Streamlit Markdown without `unsafe_allow_html` (user text is additionally Markdown-escaped).
"""
from __future__ import annotations

import html
import json
import re

import streamlit as st

from app.config import env, settings
from app.ui import branding as B
from app.viz.charts import figure
from app.viz.tables import TABLE_CSS, render_html, to_csv_bytes, to_excel_bytes

COMPANY = settings().get("company_long", "RL Certification & Inspection")
CUR = settings().get("currency", "USD")
PERSONAS = {
    "Group CFO": "group_cfo",
    "United States Country Head": "us_country_head",
    "Environmental Lab Testing PL Leader": "env_pl_leader",
}
EXAMPLES = [
    "How is operating profit YTD vs last year and budget for the United States?",
    "What's the November landing for the United States?",
    "What is our profit % YTD?",
    "Why did Canada Environmental Lab Testing margin drop in 2026?",
    "Top 5 BUs by operating margin on revenue in US & Canada this year",
    "Compare Budget vs FC2 vs Actual for Chile Metals & Minerals",
    "Which BUs are expected to miss budget this month?",
    "What will YTD MAOP margin be through November including the landing?",
]
WORKFORCE_EXAMPLES = [
    "Headcount, hires and leavers by month for Canada Environmental Lab Testing this year",
    "Attrition by role for Canada Environmental Lab Testing this year vs last year",
    "Utilization rate by grade in the United States this year",
    "Which BUs have the highest attrition this year?",
]
EXTRA_EXAMPLES = [
    "Show the operational profitability cockpit for Canada",
    "What is the utilization rate in Mexico vs budget?",
    "Break down direct staff costs for US Elevators & Pressure Vessels in March 2025",
    "What happened to WIP in Mexico Buildings & Infrastructure this year?",
    "Which countries are in scope?",
    "What ratios do you support?",
]
WELCOME_EXAMPLES = [
    "How is operating profit YTD vs last year and budget for the United States?",
    "What's the November landing for the United States?",
    "Which countries are in scope?",
]
LANDING_TOOLS = ("get_landing", "get_ytd_with_landing", "rank_landing", "explain_landing")

CSS = """
<style>
/* Streamlit's top bar (logo, top navigation) is 3.75rem high and overlays the page: start the page below it */
[data-testid="stMainBlockContainer"], .block-container {padding-top: 3.5rem; max-width: 1350px;}
.iris-head {display:flex; align-items:center; gap:14px; padding: 10px 16px; border-radius: 12px;
            background: linear-gradient(90deg, #0F766E 0%, #3730A3 100%); color:#fff; margin-bottom: 8px;}
.iris-head img {width: 52px; height: 52px; background:#fff; border-radius: 50%; padding: 3px;}
.iris-head .name {font-size: 1.55rem; font-weight: 800; letter-spacing: 0.06em; margin: 0;}
.iris-head .full {font-size: 1.0rem; font-weight: 500; opacity: 0.95; margin-left: 8px;}
.iris-head .tag {font-size: 0.92rem; opacity: 0.92; margin-top: 1px;}
.iris-head .author {font-size: 0.75rem; opacity: 0.75; margin-top: 2px;}
.rl-banner {background: #FFF4E5; border: 1px solid #F5B041; color: #7E5109; padding: 6px 12px; border-radius: 8px;
            font-size: 0.85rem; margin-bottom: 10px;}
.rl-scope {font-size: 0.8rem; color: #5D6D7E;}
.rl-chip {display:inline-block; background:#E6F4F1; color:#0F766E; border-radius:12px; padding:2px 10px;
          margin:2px 4px 2px 0; font-size:0.78rem;}
.rl-chip.filter {background:#EEF0FB; color:#3730A3;}
div[data-testid="stChatMessage"] {background: #FFFFFF;}
.stButton>button {border-radius: 8px; border: 1px solid #D6DBDF; text-align: left; white-space: normal;
                  height: auto; padding: 0.45rem 0.7rem; font-size: 0.86rem;}
.stButton>button:hover {border-color: #0F766E; color: #0F766E;}
.iris-card {border:1px solid #E2E8F0; border-radius:10px; padding:10px 12px; background:#F8FAFC;}
.iris-card .v {font-size:1.35rem; font-weight:700; color:#0B1F3A;}
.iris-card .l {font-size:0.78rem; color:#475569;}
.ug-fig {margin: 14px 0 22px; padding: 0;}
.ug-fig img {display: block; height: auto; border-radius: 10px; border: 1px solid #CBD5E1;
             box-shadow: 0 4px 16px rgba(11, 31, 58, 0.08);}
.ug-fig figcaption {font-size: 0.82rem; color: #475569; margin-top: 6px; font-style: italic;}
</style>
"""
MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|>~<])")


def esc(text) -> str:
    return html.escape("" if text is None else str(text))


def md_escape(text) -> str:
    """Escape Markdown so user-provided text (titles, names) is shown literally."""
    return MD_SPECIAL.sub(r"\\\1", "" if text is None else str(text))


def logo_data_uri() -> str:
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(B.LOGO_PATH.read_bytes()).decode()


def apply_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header() -> None:
    """Logo, product name, full name, tagline and author line on every page (branding constants only)."""
    st.markdown(
        f"<div class='iris-head'><img src='{logo_data_uri()}' alt='{esc(B.APP_NAME)} logo'/>"
        f"<div><div><span class='name'>{esc(B.APP_NAME)}</span><span class='full'>{esc(B.APP_FULL_NAME)}</span></div>"
        f"<div class='tag'>{esc(B.TAGLINE)}</div><div class='author'>{esc(B.AUTHOR_LINE)}</div></div></div>",
        unsafe_allow_html=True)
    st.markdown("<div class='rl-banner'>⚠️ <b>Synthetic data – prototype for demonstration only.</b> "
                "Fictional company, people and figures.</div>", unsafe_allow_html=True)


def init_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("memory", {})
    st.session_state.setdefault("pending", None)
    st.session_state.setdefault("persona", "Group CFO")
    st.session_state.setdefault("active_cid", None)
    st.session_state.setdefault("welcome_dismissed", False)
    # ?model=... (e.g. rules) from the first page load; page switches drop URL parameters
    st.session_state.setdefault("model_param", str(st.query_params.get("model", "")).strip().lower())


def model_choices() -> list[str]:
    current = env("LLM_MODEL", "ollama/qwen2.5-coder:14b")
    raw = env("LLM_MODEL_CHOICES", "") or ""
    choices = [current] + [m.strip() for m in raw.split(",") if m.strip() and m.strip() != current]
    return choices + ["rules (no LLM)"]


# ------------------------------------------------------------------------------------------
# Sign-in (demo only: display name + shared access code; production would use SSO)
# ------------------------------------------------------------------------------------------
def signed_in() -> bool:
    return bool(st.session_state.get("auth_user"))


def sign_in(display_name: str, code: str) -> str | None:
    """Returns an error message, or None when signed in."""
    from app.history.store import check_access_code, normalize_user  # noqa: WPS433

    uid = normalize_user(display_name)
    if not uid:
        return "Please enter your name."
    if not env("APP_ACCESS_CODE"):
        return "Sign-in is not configured: set APP_ACCESS_CODE in .env (or the Kubernetes Secret)."
    if not check_access_code(code):
        return "The access code is not correct."
    st.session_state["auth_user"], st.session_state["auth_name"] = uid, display_name.strip()[:80]
    return None


def sign_out() -> None:
    for k in ("auth_user", "auth_name", "active_cid", "welcome_dismissed"):
        st.session_state.pop(k, None)
    st.session_state.messages, st.session_state.memory = [], {}


def login_page() -> None:
    header()
    st.markdown(f"### Sign in to {B.APP_NAME}")
    with st.form("login", clear_on_submit=False):
        name = st.text_input("Your name", max_chars=80)
        code = st.text_input("Access code", type="password")
        ok = st.form_submit_button("Sign in", type="primary")
    if ok:
        err = sign_in(name, code)
        if err:
            st.error(err)
        else:
            st.rerun()
    st.caption("Demo sign-in only: your name keeps your conversation history separate from other users. "
               "A production deployment would use single sign-on (Microsoft Entra ID / Active Directory).")
    st.caption(B.footer_line())


# ------------------------------------------------------------------------------------------
# Conversation history
# ------------------------------------------------------------------------------------------
def history_store():
    """The user's conversation store (cheap to build: engines are cached), or None if unavailable."""
    try:
        from app.history.store import ConversationStore  # noqa: WPS433

        return ConversationStore()
    except Exception:  # noqa: BLE001 - the chat still works without history
        return None


def new_conversation() -> None:
    st.session_state.messages, st.session_state.memory = [], {}
    st.session_state.active_cid = None


def open_conversation(cid: str) -> None:
    """Resume a stored conversation: answers re-render from their saved payloads (no LLM, no queries); the
    conversation memory, persona and sidebar filters are restored (filters on the next run, before widgets)."""
    store = history_store()
    user = st.session_state.get("auth_user")
    if store is None or not user:
        return
    loaded = store.load(user, cid)
    if loaded is None:
        return
    conv, msgs, state = loaded
    out = []
    for m in msgs:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content_markdown"]})
        else:
            payload = m.get("payload") or {"answer_markdown": m["content_markdown"], "status": "ok", "followups": []}
            payload.setdefault("diagnostics", {})["resumed"] = True
            out.append({"role": "assistant", "answer": payload})
    st.session_state.messages = out
    st.session_state.memory = state.get("memory") or {}
    st.session_state.active_cid = conv.conversation_id
    if state.get("persona") in PERSONAS:
        st.session_state["restore_persona"] = state["persona"]
    st.session_state["restore_filters"] = state.get("ui_widgets") or {}


def apply_restored_filters() -> None:
    """Called at the top of a run, before the sidebar widgets exist."""
    persona = st.session_state.pop("restore_persona", None)
    if persona in PERSONAS:
        st.session_state.persona = persona
        st.session_state["persona_select"] = persona
    pending = st.session_state.pop("restore_filters", None)
    if pending is None:
        return
    from app.ui.sidebar import FILTER_KEYS, clear_filters  # noqa: WPS433

    clear_filters()
    for k in FILTER_KEYS:
        if pending.get(k) not in (None, [], ""):
            st.session_state[k] = pending[k]


def save_turn(question: str, payload: dict, memory: dict, cfg: dict) -> str | None:
    """Store one question and answer (with the full payload) and the conversation state. Returns a warning."""
    from app.history.store import ConversationLimit, make_title  # noqa: WPS433
    from app.ui.sidebar import FILTER_KEYS  # noqa: WPS433

    store = history_store()
    user = st.session_state.get("auth_user")
    if store is None or not user:
        return None
    try:
        cid = st.session_state.get("active_cid")
        if not cid or store.get(user, cid) is None:
            cid = store.create(user, st.session_state.persona, make_title(question, cfg.get("model")))
            st.session_state.active_cid = cid
        store.add_message(user, cid, "user", question)
        store.add_message(user, cid, "assistant", payload.get("answer_markdown") or "", payload)
        store.save_state(user, cid, {"memory": memory, "persona": st.session_state.persona,
                                     "ui_filters": cfg.get("ui_filters") or {},
                                     "ui_widgets": {k: st.session_state.get(k) for k in FILTER_KEYS}})
    except ConversationLimit as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return f"This answer could not be saved to your history ({type(exc).__name__})."
    return None


def current_landing_snapshot(cfg: dict) -> str | None:
    try:
        from app.landing.query import latest_snapshot  # noqa: WPS433
        from app.semantic.query_builder import SemanticLayer  # noqa: WPS433

        snap = latest_snapshot(SemanticLayer(cfg["user_id"], cfg["as_of"]).engine, cfg["as_of"])
        return snap.snapshot_date.isoformat() if snap else None
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------------------------------
def chips(values: list[str], kind: str = "") -> None:
    vals = [v for v in values if v]
    if vals:
        cls = f"rl-chip {kind}".strip()
        st.markdown("".join(f"<span class='{cls}'>{esc(v)}</span>" for v in vals), unsafe_allow_html=True)


def queue_page(name: str, question: str | None = None) -> None:
    """Button callback: open another page on the next run (optionally with a question for Chat)."""
    if question:
        st.session_state.pending = question
    st.session_state.nav_goto = name


def ask_button(label: str, question: str, key: str) -> None:
    """'Ask IRIS' button: sends a prefilled question to the Chat page."""
    st.button(label, key=key, help=question, on_click=queue_page, args=("chat", question))


def example_buttons(questions: list[str], prefix: str, ncols: int = 2) -> None:
    cols = st.columns(ncols)
    for i, q in enumerate(questions):
        if cols[i % ncols].button(q, key=f"{prefix}_{i}", width="stretch"):
            st.session_state.pending = q
            st.rerun()


def _is_landing(ans: dict) -> bool:
    calls = (ans.get("diagnostics") or {}).get("tool_calls") or []
    return any(c.get("name") in LANDING_TOOLS for c in calls)


def render_answer(ans: dict, idx: int, cfg: dict) -> None:
    """Text, filters, table, chart, downloads, 'How I got this' and follow-ups of one answer.

    Works from the stored payload only, so resumed conversations re-render without calling the LLM.
    """
    status = ans.get("status", "ok")
    d = ans.get("diagnostics", {}) or {}
    f = ans.get("filters_used") or {}
    if _is_landing(ans) and f.get("landing_snapshot") and d.get("resumed"):
        cur = current_landing_snapshot(cfg)
        if cur and cur != f.get("landing_snapshot"):
            c1, c2 = st.columns([3, 2])
            c1.caption(f"Landing as of {f['landing_snapshot']} (a newer landing exists: {cur})")
            if c2.button("Refresh with latest landing", key=f"refresh_{idx}"):
                st.session_state.pending = d.get("question") or ""
                st.rerun()
    if status == "refusal":
        st.error("🔒 " + (ans.get("answer_markdown") or ""))
    elif status == "clarification":
        st.info(ans.get("answer_markdown") or "")
        as_question = d.get("options_mode") == "question"     # "Show revenue instead", "Use last month instead"
        for j, opt in enumerate(d.get("options", [])[:6]):
            if st.button(opt, key=f"opt_{idx}_{j}"):
                st.session_state.pending = opt if as_question else f"{opt}: {d.get('question', '')}".strip(": ")
                st.rerun()
    else:
        st.markdown(ans.get("answer_markdown") or "")
    if status == "ok":
        chips([f.get("org"), f.get("period"), ", ".join(f.get("versions", [])[:4]) if f.get("versions") else None,
               f.get("currency")])
        if f.get("applied"):
            st.caption("Filters used: " + " · ".join(f["applied"]))
        if f.get("carried_over"):
            st.caption("↪ Carried over: " + " · ".join(f["carried_over"]))
    tspec = ans.get("table_spec") or {}
    if tspec.get("columns"):
        st.markdown(TABLE_CSS + render_html(tspec, cfg.get("units", "k")), unsafe_allow_html=True)
        for extra in tspec.get("extra_tables", []):
            with st.expander(extra.get("caption", "Detail")):
                st.markdown(TABLE_CSS + render_html(extra, cfg.get("units", "k")), unsafe_allow_html=True)
    fig = figure(ans.get("chart_spec") or {}, cfg.get("units", "k"))
    if fig is not None:
        st.plotly_chart(fig, width="stretch", key=f"chart_{idx}")
    if tspec.get("columns"):
        c1, c2, _ = st.columns([1, 1, 4])
        c1.download_button("⬇️ CSV", to_csv_bytes(tspec), file_name=f"iris_answer_{idx}.csv", mime="text/csv",
                           key=f"csv_{idx}")
        c2.download_button("⬇️ Excel", to_excel_bytes(tspec), file_name=f"iris_answer_{idx}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xls_{idx}")
    if status in ("ok", "refusal"):
        with st.expander("🔍 How I got this"):
            st.markdown(f"**Scope:** {f.get('org', '-')}  \n**Period:** {f.get('period', '-')} "
                        f"({f.get('months', '')})  \n**Versions:** {', '.join(f.get('versions', [])) or '-'}  \n"
                        f"**Currency:** {f.get('currency', CUR)} · **As-of:** {f.get('as_of_date', '-')} · "
                        f"**Row-level security:** {f.get('rls', '-')}")
            for n in f.get("notes", []) or []:
                st.caption(f"Note: {n}")
            calls = d.get("tool_calls") or []
            if calls:
                st.markdown("**Tool calls** (chosen by: `" + str(d.get("tool_choice_source")) + "`)")
                st.json(calls, expanded=False)
            g = d.get("guardrail") or {}
            if g:
                st.caption(f"Numeric guardrail: {'passed' if g.get('ok') and not g.get('template') else ('templated answer used' if g.get('template') else 'failed')} "
                           f"· model: {d.get('model') or 'rules'} · latency: {d.get('latency_s', '-')} s")
            for sql in ans.get("sql_used") or []:
                st.code(sql, language="sql")
    fu = ans.get("followups") or []
    if fu and status == "ok":
        st.markdown("**Follow-up questions**")
        cols = st.columns(3)
        for j, q in enumerate(fu[:3]):
            if cols[j].button(q, key=f"fu_{idx}_{j}", width="stretch"):
                st.session_state.pending = q
                st.rerun()


def to_json(obj) -> str:
    return json.dumps(obj, default=str)
