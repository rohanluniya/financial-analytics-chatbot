"""Chat page: the conversation with IRIS.

The sidebar filters are the default context of every question (words in the question win), the active
filters are shown as chips just above the chat input, and every answer is stored with its full payload so a
conversation can be reopened later without calling the LLM again.
"""
from __future__ import annotations

import time

import streamlit as st

from app.agent.graph import ask
from app.ui import branding as B
from app.ui import common as C
from app.ui import sidebar as S


def _has_history() -> bool:
    store, user = C.history_store(), st.session_state.get("auth_user")
    if store is None or not user:
        return False
    try:
        return bool(store.list(user))
    except Exception:  # noqa: BLE001
        return False


def welcome_card() -> None:
    """Shown on a user's first visit (no saved conversations yet) until dismissed."""
    if st.session_state.get("welcome_dismissed") or _has_history():
        return
    with st.container(border=True, key="welcome_card"):
        c1, c2 = st.columns([12, 1])
        c1.markdown(f"#### Welcome to {B.APP_NAME}. {B.TAGLINE}")
        if c2.button("✕", key="welcome_close", help="Dismiss"):
            st.session_state.welcome_dismissed = True
            st.rerun()
        st.markdown("Ask about the monthly P&L in plain English: a measure, a scope, a period and a comparison. "
                    "Every answer comes with a table, a chart and the filters it used. Three questions to start:")
        C.example_buttons(C.WELCOME_EXAMPLES, "wel", 3)
        st.button("📘 Open the User Guide", key="welcome_guide", on_click=C.queue_page, args=("guide",))


def landing() -> None:
    st.markdown("#### Try one of these")
    C.example_buttons(C.EXAMPLES, "ex")
    st.markdown("#### Workforce: fictional employee records")
    C.example_buttons(C.WORKFORCE_EXAMPLES, "exw")
    with st.expander("More examples (KPI cockpit and discovery)"):
        C.example_buttons(C.EXTRA_EXAMPLES, "exx", 1)


def process(question: str, cfg: dict) -> None:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(C.md_escape(question))
    warning = None
    with st.chat_message("assistant", avatar="📊"):
        with st.spinner("Analysing the data ..."):
            t0 = time.time()
            try:
                ans, mem = ask(question, user_id=cfg["user_id"], memory=st.session_state.memory,
                               model=cfg["model"] or "rules", as_of=cfg["as_of"], ui_filters=cfg.get("ui_filters"))
                payload = ans.model_dump()
                payload["diagnostics"]["question"] = question
                st.session_state.memory = mem
                warning = C.save_turn(question, payload, mem, cfg)
            except Exception as exc:  # noqa: BLE001
                payload = {"answer_markdown": f"Something went wrong: {type(exc).__name__}: {exc}", "status": "error",
                           "followups": [], "diagnostics": {"latency_s": round(time.time() - t0, 1),
                                                            "question": question}}
    st.session_state.messages.append({"role": "assistant", "answer": payload})
    if warning:
        st.session_state["history_warning"] = warning
    st.rerun()


def _bottom_chips(cfg: dict) -> None:
    """Active sidebar filters as chips, pinned just above the chat input."""
    chips = S.filter_chips(cfg.get("ui_filters") or {})
    target = getattr(st, "bottom", None)
    holder = target.container() if target is not None else st.container()
    with holder:
        if chips:
            C.chips(["Filters: " + chips[0]] + chips[1:], "filter")
        else:
            st.caption("No sidebar filters: questions use your whole scope unless they name a business or period.")


def render() -> None:
    cfg = st.session_state["cfg"]
    if st.session_state.get("history_warning"):
        st.warning(st.session_state.pop("history_warning"))
    if not st.session_state.messages and not st.session_state.pending:
        welcome_card()
        landing()
    for i, m in enumerate(st.session_state.messages):
        with st.chat_message(m["role"], avatar="🧑‍💼" if m["role"] == "user" else "📊"):
            if m["role"] == "user":
                st.markdown(C.md_escape(m["content"]))
            else:
                C.render_answer(m["answer"], i, cfg)
    _bottom_chips(cfg)
    typed = st.chat_input("Ask a question, e.g. 'How is operating profit YTD vs budget for Mexico?'")
    q = typed or st.session_state.pending
    if q:
        st.session_state.pending = None
        process(q, cfg)
