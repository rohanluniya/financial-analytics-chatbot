"""Run demo questions through the agent (the same `ask()` call the Streamlit UI makes) and save every
response to results/demo_responses/<model>/:

    NN_<slug>.md          insight text, finance table, chart type, filters / version / period,
                          follow-up questions, tool calls, guardrail result, latency and the SQL
    NN_<slug>.json        the full validated answer object
    NN_<slug>_chart.html  the Plotly chart that the UI shows
    index.md              one-line summary per question

Usage:
    uv run python scripts/run_demo_questions.py                  # LLM_MODEL from .env
    uv run python scripts/run_demo_questions.py --model rules    # deterministic router, no LLM
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent.graph import ask  # noqa: E402
from app.config import as_of_date, backend, env  # noqa: E402
from app.viz.charts import figure  # noqa: E402
from app.viz.tables import render_markdown  # noqa: E402

PERSONA_LABEL = {"group_cfo": "Group CFO", "us_country_head": "United States Country Head",
                 "env_pl_leader": "Environmental Lab Testing PL Leader"}

# (persona, [questions]) - questions inside one session share conversation memory (follow-ups).
SESSIONS: list[tuple[str, list[str]]] = [
    ("group_cfo", ["How is operating profit YTD vs last year and budget for the United States?", "now for Canada"]),
    ("group_cfo", ["Show personnel cost as % of revenue trend for Environmental Lab Testing since 2023"]),
    ("group_cfo", ["Why did Canada Environmental Lab Testing margin drop in 2026?"]),
    ("group_cfo", ["Top 5 BUs by operating margin in US & Canada this year"]),
    ("group_cfo", ["Compare Budget vs FC2 vs Actual for Chile Metals & Minerals"]),
    ("group_cfo", ["Break down direct staff costs for US Elevators & Pressure Vessels in March 2025"]),
    ("group_cfo", ["What happened to WIP in Mexico Buildings & Infrastructure this year?"]),
    ("group_cfo", ["Subcontracting cost by product line YTD vs PY"]),
    ("group_cfo", ["Show the operational profitability cockpit for Canada"]),
    ("group_cfo", ["What is the utilization rate in Mexico vs budget?"]),
    ("group_cfo", ["How has the operating margin of Canada Power & Utilities developed since 2022?"]),
    ("group_cfo", ["Which countries have the lowest operating margin this year?", "why is the first one so low?"]),
    ("group_cfo", ["Headcount, hires and leavers by month for Canada Environmental Lab Testing this year"]),
    ("group_cfo", ["Attrition by role for Canada Environmental Lab Testing this year vs last year",
                   "now for the United States"]),
    ("group_cfo", ["Utilization rate by grade in the United States this year"]),
    ("group_cfo", ["Which BUs have the highest attrition this year?"]),
    ("us_country_head", ["How is operating profit YTD for Brazil?"]),
    ("us_country_head", ["How is the whole group doing this year vs budget?"]),
    ("env_pl_leader", ["Rank countries by operating margin this year"]),
    ("group_cfo", ["What's the November landing for the United States?"]),
    ("group_cfo", ["Which BUs are expected to miss budget this month?"]),
    ("group_cfo", ["Explain the landing for CA-ENV-VAN-01"]),
    ("group_cfo", ["What will YTD MAOP margin be through November including the landing?"]),
    ("group_cfo", ["What is our profit % YTD?"]),
    ("group_cfo", ["Which countries are in scope?"]),
    ("us_country_head", ["Which countries are in scope?"]),
]


def slug(text: str, n: int = 48) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:n].rstrip("_")


def model_slug(model: str) -> str:
    return "rules" if model in ("rules", "none", "") else re.sub(r"[^A-Za-z0-9.]+", "-", model.split("/", 1)[-1])


def write_answer(out_dir: Path, i: int, persona: str, q: str, ans, model: str) -> dict:
    d = ans.diagnostics
    base = f"{i:02d}_{slug(q)}"
    fig = figure(ans.chart_spec.model_dump(), "M")
    if fig is not None:
        fig.write_html(out_dir / f"{base}_chart.html", include_plotlyjs="cdn", full_html=True)
    (out_dir / f"{base}.json").write_text(json.dumps(ans.model_dump(), indent=2, default=str))
    f = ans.filters_used
    g = d.get("guardrail") or {}
    guard = ("passed after removing unsupported sentences" if g.get("redacted") else
             "passed" if g.get("ok") and not g.get("template") else
             ("templated fallback" if g.get("template") else ("n/a" if not g else "failed")))
    if model_slug(model) == "rules":
        guard = "n/a (no LLM)" if g else "n/a"
    calls = d.get("tool_calls") or []
    md = [f"# {q}", "",
          f"- **Persona:** {PERSONA_LABEL.get(persona, persona)}",
          f"- **Model:** `{model}` · **status:** {ans.status} · **latency:** {d.get('latency_s')} s",
          f"- **Tool:** `{calls[0]['name'] if calls else '-'}` (chosen by `{d.get('tool_choice_source')}`)"
          f" · **numeric guardrail:** {guard}", "",
          "## Answer", "", ans.answer_markdown or "_(empty)_", ""]
    table = render_markdown(ans.table_spec, "k") if ans.table_spec else ""
    if table:
        md += ["## Table", "", table, ""]
        for extra in ans.table_spec.get("extra_tables", []):
            cap = extra.get("caption", "Detail")
            body = render_markdown(extra, "k")
            if body.endswith(f"_{cap}_"):                 # caption already shown as the header
                body = body[: -len(f"_{cap}_")].rstrip()
            md += [f"**{cap}**", "", body, ""]
    if ans.chart_spec.type != "none":
        md += ["## Chart", "", f"`{ans.chart_spec.type}` - {ans.chart_spec.title} "
               f"([interactive chart]({base}_chart.html))", ""]
    if ans.status == "ok":
        md += ["## Filters, version and period used", "",
               f"- Scope: {f.get('org', '-')}",
               f"- Period: {f.get('period', '-')} ({f.get('months', '')})",
               f"- Versions: {', '.join(f.get('versions', [])) or '-'}",
               f"- Currency: {f.get('currency', '-')} at {f.get('fx_rate', '-')}",
               f"- As-of date: {f.get('as_of_date', '-')} · row-level security: {f.get('rls', '-')}"]
        md += [f"- Note: {n}" for n in f.get("notes", []) or []]
        md += ["", "## Follow-up questions", ""] + [f"{k}. {x}" for k, x in enumerate(ans.followups, 1)] + [""]
    md += ["## Diagnostics", "", "```json",
           json.dumps({"tool_calls": calls, "llm_calls": [{k: v for k, v in c.items() if k != "raw_calls"}
                                                          for c in d.get("llm_calls", [])],
                       "guardrail": g, "errors": d.get("errors"), "timings": d.get("timings")}, indent=2, default=str),
           "```", ""]
    for sql in ans.sql_used[:3]:
        md += ["```sql", sql, "```", ""]
    if len(ans.sql_used) > 3:
        md += [f"_{len(ans.sql_used) - 3} more SQL statements in the JSON file._", ""]
    (out_dir / f"{base}.md").write_text("\n".join(md))
    return {"n": i, "file": f"{base}.md", "persona": PERSONA_LABEL.get(persona, persona), "question": q,
            "status": ans.status, "tool": calls[0]["name"] if calls else "-", "source": d.get("tool_choice_source"),
            "chart": ans.chart_spec.type, "table_rows": len(ans.table), "guard": guard,
            "latency": d.get("latency_s")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=env("LLM_MODEL", "ollama/qwen2.5-coder:14b"))
    ap.add_argument("--out", default=str(ROOT / "results" / "demo_responses"))
    args = ap.parse_args()
    out_dir = Path(args.out) / model_slug(args.model)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in [*out_dir.glob("[0-9][0-9]_*"), out_dir / "index.md"]:   # the folder matches this run only
        old.unlink(missing_ok=True)
    rows, i, t0 = [], 0, time.time()
    for persona, questions in SESSIONS:
        memory: dict = {}
        for q in questions:
            i += 1
            ans, memory = ask(q, user_id=persona, memory=memory, model=args.model)
            rows.append(write_answer(out_dir, i, persona, q, ans, args.model))
            print(f"[{i:02d}] {ans.status:13s} {rows[-1]['tool']:18s} {rows[-1]['chart']:12s} "
                  f"{rows[-1]['latency']:>6} s  {q}", flush=True)
    lat = sorted(r["latency"] for r in rows if r["status"] == "ok")
    idx = ["# Demo responses", "",
           f"Model `{args.model}` · backend `{backend()}` · as-of date {as_of_date().isoformat()} · "
           f"{len(rows)} questions in {time.time() - t0:.0f} s"
           + (f" · median latency {lat[len(lat) // 2]:.1f} s" if lat else ""), "",
           "Each file contains the insight text, the finance table, the chart, the filters / version / period "
           "used, three follow-up questions and the SQL that produced the numbers.", "",
           "| # | Persona | Question | Status | Tool | Chart | Guardrail | Latency (s) |",
           "|---:|:---|:---|:---|:---|:---|:---|---:|"]
    for r in rows:
        idx.append(f"| {r['n']} | {r['persona']} | [{r['question']}]({r['file']}) | {r['status']} | `{r['tool']}` | "
                   f"{r['chart']} | {r['guard']} | {r['latency']} |")
    (out_dir / "index.md").write_text("\n".join(idx) + "\n")
    print(f"wrote {len(rows)} responses to {out_dir}")


if __name__ == "__main__":
    main()
