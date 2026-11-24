"""Capture screenshots of the running IRIS UI: the sign-in page, the welcome card and one answer per question.

    pip install playwright && playwright install chromium     # or run in mcr.microsoft.com/playwright/python
    APP_ACCESS_CODE=... python scripts/ui_screenshots.py "http://localhost:8501/?model=rules" results/ui_screenshots/rules_mode

Signs in with APP_ACCESS_CODE (the demo sign-in code; `make k8s-access-code` prints it for the cluster setup).
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501/?model=rules"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "results/ui_screenshots/rules_mode")
CODE = os.environ.get("APP_ACCESS_CODE", "")
QUESTIONS = [
    "How is operating profit YTD vs last year and budget for the United States?",
    "What is our profit % YTD?",
    "What's the November landing for the United States?",
    "Which BUs are expected to miss budget this month?",
    "What will YTD MAOP margin be through November including the landing?",
    "Which countries are in scope?",
    "Why did Canada Environmental Lab Testing margin drop in 2026?",
    "Top 5 BUs by operating margin in US & Canada this year",
    "Compare Budget vs FC2 vs Actual for Chile Metals & Minerals",
    "Break down direct staff costs for US Elevators & Pressure Vessels in March 2025",
    "Show personnel cost as % of revenue trend for Environmental Lab Testing since 2023",
    "Attrition by role for Canada Environmental Lab Testing this year vs last year",
]
MSG = "[data-testid='stChatMessage']"


def wait_answer(page, before: int, timeout_s: int = 900) -> float:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        msgs = page.locator(MSG)
        if msgs.count() >= before + 2 and "Follow-up questions" in msgs.last.inner_text():
            time.sleep(4)
            return time.time() - t0
        time.sleep(1)
    raise TimeoutError("answer did not render")


if not CODE:
    sys.exit("Set APP_ACCESS_CODE (the demo sign-in code) first.")
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("text=Sign in to", timeout=180_000)
    time.sleep(2)
    page.screenshot(path=str(OUT / "00_sign_in.png"), full_page=True)
    page.get_by_label("Your name").fill(f"Screenshots {int(time.time())}")   # a new name: welcome card shows
    page.get_by_label("Access code").fill(CODE)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_selector("text=Try one of these", timeout=180_000)
    time.sleep(2)
    page.screenshot(path=str(OUT / "00_welcome.png"), full_page=True)
    print("signed in", flush=True)
    page.set_viewport_size({"width": 1440, "height": 2600})
    for i, q in enumerate(QUESTIONS, 1):
        if i > 1:
            page.get_by_role("button", name="New conversation").click()
            time.sleep(3)
        before = page.locator(MSG).count()
        box = page.locator("[data-testid='stChatInputTextArea']")
        box.fill(q)
        box.press("Enter")
        secs = wait_answer(page, before)
        page.screenshot(path=str(OUT / f"{i:02d}_answer.png"))
        text = " ".join(page.locator(MSG).last.inner_text().split())
        print(f"{i:02d} {secs:.0f}s {q}\n    {text[:400]}", flush=True)
    browser.close()
