"""Conversation history (app/history/store.py): last 10 per user, retention in one transaction, pinned
conversations, resume with payload and state, user isolation and titles. Runs on a temporary SQLite file
(the same code path as the DuckDB backend; SQL Server uses the [app] schema with identical queries)."""
from __future__ import annotations

import json
import time

import pytest

from app.history import store as H


@pytest.fixture()
def hs(tmp_path):
    from sqlalchemy import create_engine, event

    eng = create_engine(f"sqlite:///{tmp_path / 'history.sqlite'}")

    @event.listens_for(eng, "connect")
    def _fk(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return H.ConversationStore(engine=eng)


def _fill(hs, user: str, n: int, pin_first: int = 0) -> list[str]:
    ids = []
    for i in range(n):
        cid = hs.create(user, "Group CFO", f"conversation {i}")
        hs.add_message(user, cid, "user", f"question {i}")
        if i < pin_first:
            hs.pin(user, cid, True)
        ids.append(cid)
        time.sleep(1.05)                     # updated_at has second precision
    return ids


def test_eleventh_conversation_removes_the_oldest_unpinned_one(hs):
    ids = _fill(hs, "ada", 10, pin_first=1)          # the oldest is pinned, so the 2nd oldest goes
    new = hs.create("ada", "Group CFO", "eleventh")
    left = [c.conversation_id for c in hs.list("ada")]
    assert len(left) == 10 and new in left
    assert ids[0] in left and ids[1] not in left
    assert hs.load("ada", ids[1]) is None            # messages and state removed with it
    with hs.engine.connect() as conn:
        from sqlalchemy import func, select
        n_msg = conn.execute(select(func.count()).select_from(hs.msg).where(hs.msg.c.conversation_id == ids[1])).scalar()
    assert n_msg == 0


def test_all_ten_pinned_asks_to_unpin(hs):
    _fill(hs, "bob", 10, pin_first=10)
    with pytest.raises(H.ConversationLimit, match="Unpin"):
        hs.create("bob", "Group CFO", "one too many")
    assert len(hs.list("bob")) == 10


def test_pinned_conversations_are_listed_first(hs):
    ids = _fill(hs, "cy", 3)
    hs.pin("cy", ids[0], True)
    assert [c.conversation_id for c in hs.list("cy")][0] == ids[0]


def test_resume_returns_messages_payloads_and_state(hs):
    cid = hs.create("dee", "United States Country Head", "US operating profit")
    payload = {"answer_markdown": "**Operating profit YTD: USD 1.0M**", "status": "ok",
               "table_spec": {"columns": ["Version", "Value"]}, "chart_spec": {"type": "bar"},
               "filters_used": {"org": "United States", "landing_snapshot": "2026-11-16"},
               "followups": ["a", "b", "c"], "diagnostics": {"tool_calls": [{"name": "get_pnl"}]}}
    hs.add_message("dee", cid, "user", "How is operating profit YTD?")
    hs.add_message("dee", cid, "assistant", payload["answer_markdown"], payload)
    state = {"memory": {"org_filter": {"l3_country": ["United States"]}, "tool": "get_pnl"},
             "persona": "United States Country Head", "ui_widgets": {"flt_country": ["United States"]}}
    hs.save_state("dee", cid, state)
    conv, msgs, st = hs.load("dee", cid)
    assert conv.title == "US operating profit" and conv.persona == "United States Country Head"
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["payload"] == json.loads(json.dumps(payload))      # re-rendered from this, no LLM
    assert st == state


def test_users_cannot_see_or_change_each_others_conversations(hs):
    cid = hs.create("eve", "Group CFO", "private")
    hs.add_message("eve", cid, "user", "secret question")
    assert hs.list("mallory") == []
    assert hs.get("mallory", cid) is None and hs.load("mallory", cid) is None
    assert hs.rename("mallory", cid, "hacked") is False
    assert hs.pin("mallory", cid, True) is False
    assert hs.delete("mallory", cid) is False
    with pytest.raises(PermissionError):
        hs.add_message("mallory", cid, "user", "injected")
    with pytest.raises(PermissionError):
        hs.save_state("mallory", cid, {"memory": {}})
    assert hs.get("eve", cid).title == "private" and len(hs.load("eve", cid)[1]) == 1


def test_rename_and_delete(hs):
    cid = hs.create("fay", "Group CFO", "first title")
    assert hs.rename("fay", cid, "  Mexico margins  ") and hs.get("fay", cid).title == "Mexico margins"
    assert hs.delete("fay", cid) and hs.list("fay") == []


def test_titles_fall_back_to_the_first_50_characters():
    q = "How is operating profit YTD vs last year and budget for the United States?"
    t = H.make_title(q, None)
    assert t.startswith(q[:40]) and len(t) <= 53
    assert H.make_title("Short question", "rules") == "Short question"


def test_user_ids_are_normalised_and_codes_compared_safely(monkeypatch):
    assert H.normalize_user("  Ada  Lovelace ") == "ada_lovelace"
    assert H.normalize_user("<script>x</script>") == "scriptxscript"
    monkeypatch.setenv("APP_ACCESS_CODE", "s3cret-code")
    assert H.check_access_code("s3cret-code") and not H.check_access_code("wrong")
    monkeypatch.delenv("APP_ACCESS_CODE")
    assert not H.check_access_code("")                 # no code configured: nobody signs in
