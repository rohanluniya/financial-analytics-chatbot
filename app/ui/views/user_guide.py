"""User Guide page: renders docs/user_guide.md (the single source, so the page and the file stay identical).

Gallery lines between the `gallery:start` / `gallery:end` markers become buttons that send the question to
Chat; image lines are rendered losslessly at native Retina HiDPI density from docs/img/.
"""
from __future__ import annotations

import base64
import html
import re
import struct
from pathlib import Path

import streamlit as st

from app.config import ROOT

GUIDE = ROOT / "docs" / "user_guide.md"
IMG_RX = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)\s*$")
GALLERY_RX = re.compile(r"^- \*\*(?P<intent>[^:*]+):\*\* (?P<q>.+)$")
CAPTURE_SCALE = 2.5


def _png_logical_width(path: Path) -> int:
    data = path.read_bytes()[:24]
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        w, _ = struct.unpack(">II", data[16:24])
        return max(320, int(round(w / CAPTURE_SCALE)))
    return 1100


def _render_lossless_png(path: Path, caption: str) -> None:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    lw = _png_logical_width(path)
    cap_html = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
    st.markdown(
        f"<figure class='ug-fig'>"
        f"<img src='data:image/png;base64,{b64}' alt='{html.escape(caption)}' "
        f"style='width: min(100%, {lw}px);'/>"
        f"{cap_html}</figure>",
        unsafe_allow_html=True,
    )


def gallery_items(text: str) -> list[tuple[str, str]]:
    block = text.split("<!-- gallery:start -->", 1)[-1].split("<!-- gallery:end -->", 1)[0]
    return [(m["intent"].strip(), m["q"].strip()) for m in map(GALLERY_RX.match, block.splitlines()) if m]


def _queue(question: str) -> None:
    st.session_state.pending = question
    st.session_state.nav_goto = "chat"


def _gallery(items: list[tuple[str, str]]) -> None:
    intents = list(dict.fromkeys(i for i, _ in items))
    cols = st.columns(2)
    for n, intent in enumerate(intents):
        with cols[n % 2]:
            st.markdown(f"**{intent}**")
            for j, (i, q) in enumerate(items):
                if i == intent:
                    st.button(q, key=f"guide_{j}", on_click=_queue, args=(q,), width="stretch")


def _flush(buf: list[str]) -> None:
    if any(line.strip() for line in buf):
        st.markdown("\n".join(buf))
    buf.clear()


def render() -> None:
    if not GUIDE.exists():
        st.warning("docs/user_guide.md is missing.")
        return
    text = GUIDE.read_text(encoding="utf-8")
    buf: list[str] = []
    in_gallery = False
    for line in text.splitlines():
        if line.strip() == "<!-- gallery:start -->":
            _flush(buf)
            in_gallery = True
            _gallery(gallery_items(text))
            continue
        if line.strip() == "<!-- gallery:end -->":
            in_gallery = False
            continue
        if in_gallery:
            continue
        m = IMG_RX.match(line.strip())
        if m:
            _flush(buf)
            path = (GUIDE.parent / m["src"]).resolve()
            if path.exists() and path.is_relative_to(GUIDE.parent):
                _render_lossless_png(path, m["alt"])
            continue
        buf.append(line)
    _flush(buf)
