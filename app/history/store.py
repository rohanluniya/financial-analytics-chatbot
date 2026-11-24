"""Conversation history (Phase 8): the last 10 conversations per user, resumable without the LLM.

* SQL Server: schema [app] (sql/app_tables.sql), written through the application login.
* DuckDB backend (or APP_HISTORY_BACKEND=sqlite): SQLite file APP_HISTORY_DB (default
  data/app_history.sqlite), created on first use.

Every read and write filters by user_id, so users can only see and change their own conversations.
Retention: creating an 11th conversation deletes the oldest unpinned one (messages and state included)
in the same transaction; pinned conversations count toward the 10; if all 10 are pinned the user must
unpin one first. Demo sign-in only; production would use SSO (Entra ID / Active Directory).
"""
from __future__ import annotations

import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, MetaData, Table, Unicode, UnicodeText,
                        create_engine, delete, event, func, insert, select, update)
from sqlalchemy.engine import Engine

from app.config import ROOT, backend, env

MAX_CONVERSATIONS = 10


class ConversationLimit(Exception):
    """All 10 conversations are pinned: the user must unpin one before starting another."""


@dataclass
class Conversation:
    conversation_id: str
    user_id: str
    persona: str
    title: str
    created_at: datetime
    updated_at: datetime
    is_pinned: bool


def normalize_user(display_name: str) -> str:
    """user_id from a display name: lower case, words joined by '_', only [a-z0-9_.-], max 80 chars."""
    s = re.sub(r"\s+", "_", (display_name or "").strip().lower())
    s = re.sub(r"[^a-z0-9_.\-]", "", s)
    return s[:80]


def check_access_code(code: str) -> bool:
    """Constant-time comparison with APP_ACCESS_CODE (.env). No code configured = sign-in disabled."""
    expected = env("APP_ACCESS_CODE")
    if not expected:
        return False
    return hmac.compare_digest(str(code or "").encode(), str(expected).encode())


def _tables(schema: str | None) -> tuple[MetaData, Table, Table, Table]:
    md = MetaData(schema=schema)
    conv = Table("app_conversation", md,
                 Column("conversation_id", Unicode(36), primary_key=True),
                 Column("user_id", Unicode(80), nullable=False, index=True),
                 Column("persona", Unicode(50), nullable=False),
                 Column("title", Unicode(120), nullable=False),
                 Column("created_at", DateTime, nullable=False),
                 Column("updated_at", DateTime, nullable=False),
                 Column("is_pinned", Boolean, nullable=False, default=False))
    fk = f"{schema}.app_conversation.conversation_id" if schema else "app_conversation.conversation_id"
    msg = Table("app_message", md,
                Column("message_id", Unicode(36), primary_key=True),
                Column("conversation_id", Unicode(36), ForeignKey(fk, ondelete="CASCADE"), nullable=False, index=True),
                Column("seq", Integer, nullable=False),
                Column("role", Unicode(10), nullable=False),
                Column("content_markdown", UnicodeText, nullable=False),
                Column("payload_json", UnicodeText, nullable=True),
                Column("created_at", DateTime, nullable=False))
    state = Table("app_conversation_state", md,
                  Column("conversation_id", Unicode(36), ForeignKey(fk, ondelete="CASCADE"), primary_key=True),
                  Column("agent_state_json", UnicodeText, nullable=False))
    return md, conv, msg, state


@lru_cache(maxsize=4)
def _sqlite_engine(path: str) -> Engine:
    eng = create_engine(f"sqlite:///{path}")

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _record):  # cascade deletes need foreign keys switched on in SQLite
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return eng


class ConversationStore:
    def __init__(self, engine: Engine | None = None, schema: str | None = None):
        if engine is None:
            # APP_HISTORY_BACKEND=sqlite forces the local file (tests, or SQL Server without the app schema)
            if backend() == "mssql" and (env("APP_HISTORY_BACKEND", "") or "").lower() != "sqlite":
                from app.db import get_engine  # noqa: WPS433

                engine, schema = get_engine("__history__"), "app"
            else:
                path = ROOT / (env("APP_HISTORY_DB", "data/app_history.sqlite") or "data/app_history.sqlite")
                path.parent.mkdir(parents=True, exist_ok=True)
                engine = _sqlite_engine(str(path))
        self.engine = engine
        self.md, self.conv, self.msg, self.state = _tables(schema)
        if engine.dialect.name == "sqlite":
            self.md.create_all(engine)

    # ---------------------------------------------------------------- reads (always scoped to the user)
    def list(self, user_id: str) -> list[Conversation]:
        c = self.conv
        stmt = (select(c).where(c.c.user_id == user_id)
                .order_by(c.c.is_pinned.desc(), c.c.updated_at.desc()).limit(MAX_CONVERSATIONS))
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_conv(r) for r in rows]

    def get(self, user_id: str, cid: str) -> Conversation | None:
        c = self.conv
        with self.engine.connect() as conn:
            r = conn.execute(select(c).where(c.c.user_id == user_id, c.c.conversation_id == cid)).mappings().first()
        return _conv(r) if r else None

    def load(self, user_id: str, cid: str) -> tuple[Conversation, list[dict], dict] | None:
        """(conversation, messages with decoded payloads, agent state) or None if not the user's."""
        conv = self.get(user_id, cid)
        if conv is None:
            return None
        m, s = self.msg, self.state
        with self.engine.connect() as conn:
            msgs = conn.execute(select(m).where(m.c.conversation_id == cid).order_by(m.c.seq)).mappings().all()
            st = conn.execute(select(s.c.agent_state_json).where(s.c.conversation_id == cid)).scalar()
        out = []
        for r in msgs:
            d = dict(r)
            d["payload"] = json.loads(d["payload_json"]) if d.get("payload_json") else None
            out.append(d)
        return conv, out, json.loads(st) if st else {}

    # ---------------------------------------------------------------- writes
    def create(self, user_id: str, persona: str, title: str) -> str:
        """New conversation; enforces the 10-per-user limit in the same transaction."""
        c, m, s = self.conv, self.msg, self.state
        now = datetime.now().replace(microsecond=0)
        cid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            rows = conn.execute(select(c.c.conversation_id, c.c.is_pinned, c.c.updated_at)
                                .where(c.c.user_id == user_id)).all()
            excess = len(rows) - (MAX_CONVERSATIONS - 1)
            if excess > 0:
                unpinned = sorted([r for r in rows if not r.is_pinned], key=lambda r: r.updated_at)
                if len(unpinned) < excess:
                    raise ConversationLimit("All 10 conversations are pinned. Unpin one to start a new conversation.")
                old = [r.conversation_id for r in unpinned[:excess]]
                conn.execute(delete(m).where(m.c.conversation_id.in_(old)))
                conn.execute(delete(s).where(s.c.conversation_id.in_(old)))
                conn.execute(delete(c).where(c.c.conversation_id.in_(old), c.c.user_id == user_id))
            conn.execute(insert(c).values(conversation_id=cid, user_id=user_id, persona=persona,
                                          title=(title or "New conversation")[:120], created_at=now, updated_at=now,
                                          is_pinned=False))
        return cid

    def add_message(self, user_id: str, cid: str, role: str, content: str, payload: dict | None = None) -> int:
        if self.get(user_id, cid) is None:
            raise PermissionError("conversation not found for this user")
        m, c = self.msg, self.conv
        now = datetime.now().replace(microsecond=0)
        with self.engine.begin() as conn:
            seq = (conn.execute(select(func.max(m.c.seq)).where(m.c.conversation_id == cid)).scalar() or 0) + 1
            conn.execute(insert(m).values(message_id=str(uuid.uuid4()), conversation_id=cid, seq=seq, role=role,
                                          content_markdown=content or "",
                                          payload_json=json.dumps(payload, default=str) if payload is not None else None,
                                          created_at=now))
            conn.execute(update(c).where(c.c.conversation_id == cid, c.c.user_id == user_id).values(updated_at=now))
        return seq

    def save_state(self, user_id: str, cid: str, state: dict) -> None:
        if self.get(user_id, cid) is None:
            raise PermissionError("conversation not found for this user")
        s = self.state
        blob = json.dumps(state or {}, default=str)
        with self.engine.begin() as conn:
            done = conn.execute(update(s).where(s.c.conversation_id == cid).values(agent_state_json=blob)).rowcount
            if not done:
                conn.execute(insert(s).values(conversation_id=cid, agent_state_json=blob))

    def rename(self, user_id: str, cid: str, title: str) -> bool:
        c = self.conv
        with self.engine.begin() as conn:
            return conn.execute(update(c).where(c.c.conversation_id == cid, c.c.user_id == user_id)
                                .values(title=(title or "").strip()[:120] or "Untitled")).rowcount == 1

    def pin(self, user_id: str, cid: str, pinned: bool) -> bool:
        c = self.conv
        with self.engine.begin() as conn:
            return conn.execute(update(c).where(c.c.conversation_id == cid, c.c.user_id == user_id)
                                .values(is_pinned=bool(pinned))).rowcount == 1

    def delete(self, user_id: str, cid: str) -> bool:
        c, m, s = self.conv, self.msg, self.state
        with self.engine.begin() as conn:
            if conn.execute(select(c.c.conversation_id).where(c.c.conversation_id == cid,
                                                              c.c.user_id == user_id)).first() is None:
                return False
            conn.execute(delete(m).where(m.c.conversation_id == cid))
            conn.execute(delete(s).where(s.c.conversation_id == cid))
            conn.execute(delete(c).where(c.c.conversation_id == cid, c.c.user_id == user_id))
        return True


def _conv(r) -> Conversation:
    d = dict(r)
    d["conversation_id"] = str(d["conversation_id"]).lower()     # SQL Server returns GUIDs in upper case
    d["is_pinned"] = bool(d["is_pinned"])
    return Conversation(**d)


def fallback_title(question: str) -> str:
    q = re.sub(r"\s+", " ", (question or "").strip())
    return (q[:50].rstrip() + ("..." if len(q) > 50 else "")) or "New conversation"


def make_title(question: str, model: str | None) -> str:
    """Short title (at most 6 words) from the LLM; the first 50 characters of the question as fallback."""
    if not model or model.lower().startswith("rules"):
        return fallback_title(question)
    try:
        from app.agent import llm  # noqa: WPS433

        r = llm.chat([{"role": "system", "content": "Write a title of at most 6 words for this finance question. "
                                                    "Reply with the title only, no quotes, no punctuation at the end."},
                      {"role": "user", "content": question}], model=model, max_tokens=20)
        t = re.sub(r"[\"'`*#]", "", (r.content or "").strip().splitlines()[0] if r.content else "").strip(" .:")
        words = t.split()
        if 1 <= len(words) <= 6:
            return t[:120]
    except Exception:  # noqa: BLE001
        pass
    return fallback_title(question)
