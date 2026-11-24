"""Headless UI tests (Streamlit AppTest, no LLM): sign-in gate, header and footer on every page, quick guide,
examples rendering text + table + chart + follow-ups, sidebar filters (RLS options, "Filters used", question
wins), row-level-security refusal, and conversation history (resume re-renders without calling the agent)."""
from __future__ import annotations

import html

import pytest

from app.config import ROOT
from app.ui import branding as B

st_testing = pytest.importorskip("streamlit.testing.v1")
APP = str(ROOT / "app" / "ui" / "streamlit_app.py")
EXAMPLE_KEYS = [f"ex_{i}" for i in range(8)] + [f"exw_{i}" for i in range(4)]
PAGES = ("chat", "catalog", "guide", "about")


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_MODEL", "rules")
    monkeypatch.setenv("LLM_MODEL_CHOICES", "")
    monkeypatch.setenv("APP_ACCESS_CODE", "demo-code-123")
    monkeypatch.setenv("APP_HISTORY_BACKEND", "sqlite")
    monkeypatch.setenv("APP_HISTORY_DB", str(tmp_path / "history.sqlite"))


def _app(user: str | None = "ui_tester", persona: str | None = None, goto: str | None = None):
    at = st_testing.AppTest.from_file(APP, default_timeout=300)
    if user:
        at.session_state["auth_user"] = user
        at.session_state["auth_name"] = user
    if persona:
        at.session_state["persona"] = persona
    if goto:
        at.session_state["nav_goto"] = goto
    at.run()
    assert not at.exception, at.exception
    return at


def _md(at) -> list[str]:
    return [m.value for m in at.markdown]


def _ask(at, question: str):
    at.chat_input[0].set_value(question).run()
    assert not at.exception, at.exception
    return at


def _filters_used(at) -> str:
    return " | ".join(c.value for c in at.caption if c.value.startswith("Filters used:"))


# ------------------------------------------------------------------------------------------ sign-in
def test_sign_in_is_required_and_checks_the_code():
    at = _app(user=None)
    assert any("Sign in to" in v for v in _md(at))
    assert not at.chat_input                                    # no chat before signing in
    at.text_input[0].input("Ada Lovelace")
    at.text_input[1].input("wrong")
    at.button[0].click().run()
    assert any("not correct" in e.value for e in at.error)
    at.text_input[1].input("demo-code-123")
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["auth_user"] == "ada_lovelace"
    assert at.chat_input                                        # the chat page is open


# ------------------------------------------------------------------------------------------ branding
@pytest.mark.parametrize("page", PAGES)
def test_every_page_shows_header_footer_and_no_old_name(page):
    at = _app(goto=page)
    md = html.unescape(" ".join(_md(at)))
    for s in (B.APP_NAME, B.APP_FULL_NAME, B.TAGLINE, B.AUTHOR_LINE, "Synthetic data"):
        assert s in md, (page, s)
    assert any(B.footer_line() in c.value for c in at.sidebar.caption), page
    text = (md + " ".join(c.value for c in at.caption)).lower()
    assert "rl-finbot" not in text and "finbot" not in text


def test_quick_guide_dialog_opens():
    at = _app()
    next(b for b in at.sidebar.button if "Quick guide" in b.label).click().run()
    assert not at.exception, at.exception
    md = " ".join(_md(at))
    assert "Ask about the current month" in md and "User Guide" in " ".join(b.label for b in at.button)


# ------------------------------------------------------------------------------------------ answers
@pytest.mark.parametrize("key", EXAMPLE_KEYS)
def test_example_renders_text_table_chart_followups(key):
    at = _app()
    at.button(key=key).click().run()
    assert not at.exception, at.exception
    md = _md(at)
    assert any("fin-table" in v for v in md), "finance table missing"
    assert len(at.get("plotly_chart")) >= 1, "chart missing"
    answer_texts = [v for v in md if len(v) > 60 and "fin-table" not in v and "<div" not in v and "<style" not in v]
    assert answer_texts, "insight text missing"
    followups = [b for b in at.button if b.key and b.key.startswith("fu_")]
    assert len(followups) == 3, [b.key for b in at.button]
    chips = [v for v in md if "<span class='rl-chip'>" in v]
    assert chips and "USD" in chips[0], "filters / currency chips missing"
    assert _filters_used(at), "'Filters used' line missing"


def test_followup_button_runs_second_turn():
    at = _app()
    at.button(key="ex_0").click().run()
    fu = [b for b in at.button if b.key and b.key.startswith("fu_")][0]
    fu.click().run()
    assert not at.exception, at.exception
    assert len(at.chat_message) == 4                     # two questions, two answers


# ------------------------------------------------------------------------------------------ filters
def test_filter_options_follow_row_level_security():
    at = _app(persona="United States Country Head")
    assert at.multiselect(key="flt_country").options == ["United States"]
    assert at.multiselect(key="flt_region").options == ["US & Canada"]
    at = _app(persona="Group CFO")
    assert len(at.multiselect(key="flt_country").options) > 5


def test_cascading_filters_narrow_children():
    at = _app()
    at.multiselect(key="flt_country").select("Mexico").run()
    bus = at.multiselect(key="flt_bu").options
    assert bus and all(b.startswith("MX-") for b in bus), bus[:5]
    assert at.multiselect(key="flt_region").options          # parents stay selectable


def test_sidebar_filter_is_the_default_and_shows_in_filters_used():
    at = _app()
    at.multiselect(key="flt_country").select("Mexico").run()
    assert any("Country: Mexico" in v for v in _md(at))      # chip above the chat input
    _ask(at, "How is operating profit YTD vs budget?")
    used = _filters_used(at)
    assert "Mexico" in used and "sidebar" in used, used


def test_question_wins_over_the_sidebar_filter():
    at = _app()
    at.multiselect(key="flt_country").select("Mexico").run()
    _ask(at, "How is operating profit YTD vs budget for Canada?")
    used = _filters_used(at)
    assert "Canada" in used and "from your question" in used and "Mexico" not in used, used


def test_restricted_persona_gets_refusal():
    at = _app(persona="United States Country Head")
    _ask(at, "How is operating profit YTD for Brazil?")
    assert any("don't have access" in e.value and "Brazil" in e.value for e in at.error), [e.value for e in at.error]


def test_model_from_url_survives_page_switches(monkeypatch):
    """?model=rules on the first load stays selected after the top navigation drops the URL parameter."""
    monkeypatch.setenv("LLM_MODEL", "ollama/qwen2.5-coder:14b")
    monkeypatch.setenv("LLM_MODEL_CHOICES", "ollama/qwen2.5-coder:14b,ollama/gpt-oss:20b")
    at = st_testing.AppTest.from_file(APP, default_timeout=300)
    at.query_params["model"] = "rules"
    at.session_state["auth_user"] = at.session_state["auth_name"] = "ui_tester"
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["model_select"] == "rules (no LLM)"
    at.query_params.pop("model", None)
    for page in ("about", "chat"):
        at.session_state["nav_goto"] = page
        at.run()
        assert not at.exception, at.exception
    assert at.session_state["model_select"] == "rules (no LLM)"


def test_page_starts_below_the_top_bar():
    """Streamlit's top bar (3.75rem) overlays the page; the IRIS header must start below it, not under it."""
    import re

    from app.ui import common as C
    m = re.search(r"stMainBlockContainer[^{]*\{[^}]*padding-top:\s*([\d.]+)rem", C.CSS)
    assert m and float(m.group(1)) >= 3.5, "the IRIS header would be hidden under the top bar"


# ------------------------------------------------------------------------------------------ history
def test_conversation_is_saved_and_resumes_without_the_agent(monkeypatch):
    at = _app(user="resume_tester")
    _ask(at, "How is operating profit YTD vs last year for Mexico?")
    first_answer = [m for m in _md(at) if "Operating profit" in m or "operating profit" in m]
    assert first_answer
    next(b for b in at.sidebar.button if "New conversation" in b.label).click().run()
    assert len(at.chat_message) == 0

    def _no_agent(*_a, **_k):
        raise AssertionError("resuming a conversation must not call the agent")
    import app.ui.views.chat as chat_page
    monkeypatch.setattr(chat_page, "ask", _no_agent)
    conv = [b for b in at.sidebar.button if b.key and b.key.startswith("conv_")]
    assert len(conv) == 1
    conv[0].click().run()
    assert not at.exception, at.exception
    assert len(at.chat_message) == 2
    assert any("fin-table" in v for v in _md(at)) and len(at.get("plotly_chart")) >= 1
