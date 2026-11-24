"""Walk through the IRIS demo script (docs/demo_script.md) in the real UI with a headless browser and check
every expected figure.

    pip install playwright && playwright install chromium     # or run in mcr.microsoft.com/playwright/python
    APP_ACCESS_CODE=... python scripts/ui_walkthrough.py http://localhost:8501 results/ui_walkthrough [rules,llm]

Rules mode runs the demo script: About, Data Catalog, a catalog question, a sidebar filter (and the question's
own words winning over it), a persona with restricted data access, both margins, the November landing, the BUs
that will miss budget, the YTD margin including the landing, a conversation with a follow-up, a pushback and
one of its change buttons, and reopening that conversation from the sidebar. LLM mode (the default model) runs
four of the questions and reads the tool-choice source and guardrail result from "How I got this". Expected
figures are for the synthetic data as of 2026-11-16. Writes one JSON line per step to walkthrough.jsonl and a
screenshot per answer.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "results/ui_walkthrough")
PARTS = (sys.argv[3] if len(sys.argv) > 3 else "rules,llm").split(",")
CODE = os.environ.get("APP_ACCESS_CODE", "")
USER = "UI walkthrough"
HEADER = ("IRIS", "Intelligent Reporting & Insight System", "See your business clearly.",
          "Developed and maintained by Rohan Luniya")
BANNED = re.compile(r"\bMAOP\b|\b\d[A-Z]\d\b|rl-finbot")     # customer KPI acronym, account codes, old name
MSG = "[data-testid='stChatMessage']"
RESULTS: list[dict] = []


def log(rec: dict) -> None:
    RESULTS.append(rec)
    print(json.dumps(rec), flush=True)


def chat_ready(page) -> None:
    page.locator("[data-testid='stChatInputTextArea']").wait_for(timeout=180_000)
    time.sleep(1.5)


def sign_in(page, url: str) -> None:
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("text=Sign in to", timeout=180_000)
    page.get_by_label("Your name").fill(USER)
    page.get_by_label("Access code").fill(CODE)
    page.get_by_role("button", name="Sign in").click()
    chat_ready(page)


def new_conversation(page) -> None:
    page.get_by_role("button", name=re.compile("New conversation")).click()
    chat_ready(page)


def sidebar(page):
    return page.locator("[data-testid='stSidebar']")


def set_persona(page, name: str, access: str) -> None:
    sb = sidebar(page)
    if not sb.get_by_text("Data access:").is_visible():
        sb.get_by_text("Settings", exact=True).click()
        time.sleep(1)
    box = page.locator("[data-testid='stSelectbox']").filter(has_text="Persona")
    box.get_by_role("button", name="Open").click()
    page.get_by_role("option", name=name, exact=True).click()
    sb.get_by_text(f"Data access: {access}").wait_for(timeout=60_000)
    chat_ready(page)


def ensure_rules(page) -> tuple[str, str]:
    """Rules part: the model selector must say 'rules (no LLM)' (selects it if needed).
    Returns the selector value before and after, so a reset after page switches is reported."""
    sb = sidebar(page)
    if not sb.get_by_text("Data access:").is_visible():
        sb.get_by_text("Settings", exact=True).click()
        time.sleep(1)
    box = page.locator("[data-testid='stSelectbox']").filter(has_text="Model (LiteLLM)")
    value = box.locator("input[role='combobox']")
    before = value.input_value()
    if "rules" not in before:
        box.get_by_role("button", name="Open").click()
        page.get_by_role("option", name="rules (no LLM)", exact=True).click()
        time.sleep(2)
    return before, value.input_value()


def set_country(page, country: str) -> None:
    box = sidebar(page).locator("[data-testid='stMultiSelect']").nth(1)        # Region, Country, ...
    box.click()
    page.keyboard.type(country)
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    time.sleep(3)


def wait_answer(page, before: int, timeout_s: int) -> float:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        msgs = page.locator(MSG)
        if msgs.count() >= before + 2:
            txt = msgs.last.inner_text()
            done = ("Follow-up questions" in txt or "Sorry, you don't have access" in txt
                    or "Something went wrong" in txt or "Which one do you mean" in txt
                    or "Which part should change" in txt)
            if done and "Analysing the data" not in txt:
                time.sleep(3)
                return time.time() - t0
        time.sleep(0.5)
    raise TimeoutError("answer did not render")


def submit(page, how: str, text: str, timeout_s: int) -> float:
    before = page.locator(MSG).count()
    if how == "button":
        page.get_by_role("button", name=text, exact=True).click()
    else:
        box = page.locator("[data-testid='stChatInputTextArea']")
        box.fill(text)
        box.press("Enter")
    return wait_answer(page, before, timeout_s)


def check(page, step, mode, how, question, expect, forbid=(), timeout_s=90, page_expect=(),
          open_details=False) -> dict:
    rec = {"step": step, "mode": mode, "question": question}
    try:
        secs = submit(page, how, question, timeout_s)
    except Exception as exc:  # noqa: BLE001
        rec.update(ok=False, error=str(exc)[:300])
        page.screenshot(path=str(OUT / f"{mode}_{step}_error.png"))
        log(rec)
        return rec
    last = page.locator(MSG).last
    text = last.inner_text()
    plots = last.locator(".js-plotly-plot")
    blob = text + " " + " ".join(plots.nth(i).text_content() or "" for i in range(plots.count()))
    missing = [e for e in expect if e not in blob]
    present_forbidden = [f for f in forbid if f in blob]
    banned = sorted({m.group(0) for m in BANNED.finditer(blob)})
    rec.update(seconds=round(secs, 1), missing=missing, forbidden=present_forbidden, banned=banned)
    if page_expect:
        body = page.inner_text("body")
        rec["page_missing"] = [s for s in page_expect if s not in body]
    last.screenshot(path=str(OUT / f"{mode}_{step}.png"))
    if open_details:
        last.locator("summary", has_text="How I got this").click()
        time.sleep(1.5)
        det = last.inner_text()
        m = re.search(r"chosen by:\s*`?([a-z_+]+)", det)
        g = re.search(r"Numeric guardrail: ([^·\n]+)· model: ([^·\n]+)· latency: ([0-9.]+)", det)
        rec["tool_choice"] = m.group(1) if m else None
        rec["guardrail"] = g.group(1).strip() if g else None
        rec["model"] = g.group(2).strip() if g else None
        rec["latency_s"] = float(g.group(3)) if g else None
    rec["ok"] = (not missing and not present_forbidden and not rec.get("page_missing")
                 and (mode != "rules" or not banned))
    rec["answer_head"] = " ".join(text.split())[:260]
    log(rec)
    return rec


def check_page(page, step: str, link: str, expect: list[str]) -> None:
    rec = {"step": step, "mode": "rules", "page": link}
    try:
        page.get_by_role("link", name=link).first.click()
        page.wait_for_selector(f"text={expect[0]}", timeout=120_000)
        time.sleep(4)
        main = page.locator("[data-testid='stMain']")
        body = main.inner_text() if main.count() else page.inner_text("body")
        rec["missing"] = [e for e in [*HEADER, *expect] if e not in body]
        rec["banned"] = sorted({m.group(0) for m in BANNED.finditer(body)})
        rec["ok"] = not rec["missing"] and not rec["banned"]
        page.screenshot(path=str(OUT / f"rules_{step}.png"))
    except Exception as exc:  # noqa: BLE001
        rec.update(ok=False, error=str(exc)[:300])
    log(rec)


def rules_walk(page) -> None:
    sign_in(page, f"{BASE}/?model=rules")
    body = page.inner_text("body")
    log({"step": "0_signed_in", "mode": "rules", "missing": [h for h in HEADER if h not in body],
         "ok": all(h in body for h in HEADER) and page.get_by_role("button", name="Deploy").count() == 0})
    check_page(page, "1_about", "About", ["How it works", "Last closed month: Oct 2026", "as of 2026-11-16"])
    check_page(page, "2_data_catalog", "Data Catalog", ["Coverage by country and product line", "106", "67"])
    page.get_by_role("link", name="Chat").first.click()
    chat_ready(page)
    before, after = ensure_rules(page)
    log({"step": "2b_rules_mode_kept_after_page_switches", "mode": "rules", "selector": before,
         "ok": "rules" in before and "rules" in after})
    new_conversation(page)
    check(page, "3_catalog_question", "rules", "typed", "Which countries are in scope?",
          ["11 countries", "Argentina", "Uruguay"])
    new_conversation(page)
    set_country(page, "Mexico")
    check(page, "4a_sidebar_filter", "rules", "typed", "How is operating profit YTD vs budget?",
          ["USD 11.4M", "Scope: Mexico (from the sidebar filters)"], page_expect=["Country: Mexico"])
    check(page, "4b_question_wins", "rules", "typed", "How is operating profit YTD vs budget for Canada?",
          ["USD 21.5M", "Scope: Canada (from your question)"])
    sidebar(page).get_by_role("button", name="Clear filters").click()
    time.sleep(3)
    set_persona(page, "United States Country Head", "United States")
    check(page, "5a_restricted_catalog", "rules", "typed", "Which countries are in scope?",
          ["1 country", "United States"], forbid=["Mexico", "Brazil", "Argentina"])
    check(page, "5b_refusal", "rules", "typed", "How is operating profit YTD for Brazil?",
          ["Sorry, you don't have access", "Brazil"])
    set_persona(page, "Group CFO", "RL Group")
    check(page, "6_both_margins", "rules", "typed", "What is our profit % YTD?",
          ["Operating margin on revenue", "14.9%", "Operating margin on production", "14.8%", "both"])
    new_conversation(page)
    check(page, "7_landing_us", "rules", "typed", "What's the November landing for the United States?",
          ["USD 35.2M", "USD 34.5M", "USD 36.7M", "USD 33.8M", "WIP is 0", "P10"])
    check(page, "8a_followup_keeps_us", "rules", "typed", "Which BUs are expected to miss budget this month?",
          ["7 of 16", "United States"])                   # same conversation: a follow-up keeps the scope
    new_conversation(page)
    check(page, "8b_bus_missing_budget", "rules", "typed", "Which BUs are expected to miss budget this month?",
          ["52 of 106", "CA-ENV-VAN-01"])
    check(page, "9_ytd_margin_with_landing", "rules", "typed",
          "What will YTD MAOP margin be through November including the landing?",
          ["14.8%", "14.7%", "0.8 pp", "Operating margin on production"])
    new_conversation(page)
    check(page, "10a_net_income_mexico", "rules", "typed", "What is the net income of Mexico this year?",
          ["Net income", "USD 7.1M"])
    check(page, "10b_followup_keeps_line", "rules", "typed", "now for Canada",
          ["Net income", "USD 13.2M", "Carried over: Net income · YTD Oct 2026"])
    check(page, "10c_pushback", "rules", "typed", "That's not right",
          ["Here is exactly what I used", "Net income", "Canada", "YTD Oct 2026", "Show operating profit instead",
           "Use last month instead", "Compare with Budget only"])
    check(page, "10d_change_button", "rules", "button", "Compare with Budget only", ["Net income", "Budget", "Canada"])
    new_conversation(page)
    rec = {"step": "11a_reopen_conversation", "mode": "rules"}
    try:
        sidebar(page).get_by_role("button", name=re.compile("net income of Mexico")).first.click()
        page.locator(MSG).nth(7).wait_for(timeout=60_000)              # 4 questions + 4 answers re-rendered
        body = page.inner_text("body")
        rec["missing"] = [s for s in ("USD 7.1M", "USD 13.2M", "Here is exactly what I used") if s not in body]
        rec["messages"] = page.locator(MSG).count()
        rec["ok"] = not rec["missing"]
        page.screenshot(path=str(OUT / "rules_11a_reopen_conversation.png"))
    except Exception as exc:  # noqa: BLE001
        rec.update(ok=False, error=str(exc)[:300])
    log(rec)
    check(page, "11b_followup_after_reopen", "rules", "typed", "and for the United States?",
          ["Net income", "United States", "Budget"])


def llm_walk(page) -> None:
    sign_in(page, BASE)
    new_conversation(page)
    check(page, "7_landing_us", "llm", "typed", "What's the November landing for the United States?",
          ["35.2", "P10"], timeout_s=600, open_details=True)
    new_conversation(page)
    check(page, "6_both_margins", "llm", "typed", "What is our profit % YTD?", ["14.9", "14.8"],
          timeout_s=600, open_details=True)
    new_conversation(page)
    check(page, "10a_net_income_mexico", "llm", "typed", "What is the net income of Mexico this year?", ["7.1"],
          timeout_s=600, open_details=True)
    check(page, "10b_followup_keeps_line", "llm", "typed", "now for Canada",
          ["13.2", "Carried over: Net income · YTD Oct 2026"], timeout_s=600, open_details=True)


if not CODE:
    sys.exit("Set APP_ACCESS_CODE (the demo sign-in code) first.")
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    for part in PARTS:
        page = browser.new_page(viewport={"width": 1440, "height": 3200})   # tall, so long answers render whole
        try:
            rules_walk(page) if part == "rules" else llm_walk(page)
        except Exception as exc:  # noqa: BLE001
            log({"part": part, "fatal": str(exc)[:400], "ok": False})
            page.screenshot(path=str(OUT / f"{part}_fatal.png"))
        page.close()
    browser.close()
(OUT / "walkthrough.jsonl").write_text("".join(json.dumps(r) + "\n" for r in RESULTS))
print(f"WALKTHROUGH_DONE {sum(1 for r in RESULTS if r.get('ok'))}/{len(RESULTS)} steps ok", flush=True)
