"""Golden-question evaluation of the agent.

    uv run python tests/run_eval.py                                  # LLM_MODEL from .env
    uv run python tests/run_eval.py --models rules,ollama/qwen2.5-coder:14b,ollama/llama3.1:8b
    uv run python tests/run_eval.py --report-only                    # rebuild eval_report.md

For every question in tests/golden_questions.yaml the full agent runs (same `ask()` call as the UI)
and the run records:
  * status        ok / refusal / clarification as expected
  * tool choice   primary tool in the accepted list; separately, whether the LLM's own choice was
                  right (without the deterministic router fallback)
  * numbers       expected values come from tests/eval_dsl.py (raw SQL on the base tables,
                  independent of the semantic layer): all must be in the tool output ("data"),
                  and the headline value(s) must appear in the answer text ("text")
  * RLS           refusals return no table and no SQL; narrowed scopes return the scoped numbers;
                  `absent` names must not appear anywhere in the answer (e.g. other countries)
  * sidebar       `ui_filters` are passed like the UI's sidebar filters (the question's words win)
  * resume        `resume: true` stores the earlier turns in a conversation store, reloads them and asks
                  the last question with the restored memory (no LLM call for the stored answers)
  * guardrail     passed first time / passed after one rewrite / templated fallback
  * latency       end-to-end seconds per question (last turn)
Raw records: results/eval/<model>.jsonl (the run resumes where it stopped).
Report: eval_report.md and results/eval/summary.json.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.agent.guardrails import extract_numbers  # noqa: E402
from app.config import data_as_of_date, backend, env  # noqa: E402

AS_OF = data_as_of_date()          # the app's default as-of date (settings.yaml)
GOLDEN = ROOT / "tests" / "golden_questions.yaml"
OUT = ROOT / "results" / "eval"
TOL = {"eur": lambda v: max(1.0, abs(v) * 1e-6), "rate": lambda v: 1e-3, "pct": lambda v: 1e-6,
       "num": lambda v: 0.01}


def slug(model: str) -> str:
    return "rules" if model in ("rules", "none", "") else re.sub(r"[^A-Za-z0-9.]+", "-", model.split("/", 1)[-1])


# ------------------------------------------------------------------------------------------ matching
def _collect(obj, nums: list[float], strs: set[str]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if obj == obj:                                   # skip NaN
            nums.append(abs(float(obj)))
    elif isinstance(obj, str):
        strs.add(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, nums, strs)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, nums, strs)


def evidence(ans) -> tuple[list[float], set[str]]:
    nums: list[float] = []
    strs: set[str] = set()
    _collect(ans.table, nums, strs)
    _collect((ans.table_spec or {}).get("extra_tables", []), nums, strs)
    _collect((ans.diagnostics or {}).get("evidence", {}), nums, strs)
    return nums, strs


def in_data(exp: dict, nums: list[float], strs: set[str]) -> bool:
    v = exp["value"]
    if v is None:
        return False
    if exp.get("names") is not None:                 # catalog: every expected name is in the output
        return set(exp["names"]) <= strs
    tol = TOL[exp["fmt"]](v)
    ok = any(abs(a - abs(v)) <= tol for a in nums)
    if exp.get("name"):
        ok = ok and exp["name"] in strs
    return ok


def in_text(exp: dict, text: str) -> bool:
    v, fmt = exp["value"], exp["fmt"]
    if v is None:
        return False
    names = exp.get("names")
    if names and all(n.lower() in (text or "").lower() for n in names):
        return True                                  # list questions: naming every item is as good as the count
    if exp.get("name") and exp["name"].lower() not in (text or "").lower():
        return False
    target = abs(v)
    for t in extract_numbers(text or ""):
        if fmt == "pct" and t.unit != "%":
            continue
        if fmt != "pct" and t.unit in ("%", "pp"):
            continue
        half = 0.5 * 10 ** -t.decimals * t.scale
        if abs(t.value - target) <= half * 1.02 + 1e-12 or (target and abs(t.value - target) / target <= 0.005):
            return True
    return False


# ------------------------------------------------------------------------------------------ run
def run_question(item: dict, model: str) -> dict:
    from app.agent.graph import ask
    from eval_dsl import evaluate

    persona = item.get("persona", "group_cfo")
    ui = item.get("ui_filters") or None
    memory: dict = {}
    turns = []
    for turn in item.get("turns", []):
        prev, memory = ask(turn, user_id=persona, memory=memory, model=model, as_of=AS_OF, ui_filters=ui)
        turns.append((turn, prev.model_dump()))
    resume_ok = None
    if item.get("resume"):
        memory, resume_ok = _resume(persona, turns, memory)
    t0 = time.time()
    ans, new_mem = ask(item["q"], user_id=persona, memory=memory, model=model, as_of=AS_OF, ui_filters=ui)
    latency = time.time() - t0
    d = ans.diagnostics or {}
    exp_status = item.get("status", "ok")
    rec = {"id": item["id"], "category": item["category"], "persona": persona, "q": item["q"],
           "turns": item.get("turns", []), "model": model, "status": ans.status, "expected_status": exp_status,
           "status_ok": ans.status == exp_status, "latency": round(latency, 2),
           "tool_choice_source": d.get("tool_choice_source"), "tool_calls": d.get("tool_calls"),
           "errors": d.get("errors"), "answer": ans.answer_markdown,
           "llm_seconds": round(sum(c.get("latency", 0) for c in d.get("llm_calls", [])), 2)}
    if resume_ok is not None:
        rec["resume_ok"] = resume_ok
        rec["status_ok"] = rec["status_ok"] and resume_ok
    if exp_status == "clarification" and item.get("options_min"):
        rec["options"] = list(d.get("options") or [])          # pushback: one button per part to change
        rec["status_ok"] = rec["status_ok"] and len(rec["options"]) >= item["options_min"]
    # tool choice
    tools = item.get("tools")
    primary = new_mem.get("tool") if ans.status == "ok" else None
    rec["tool"] = primary
    rec["tool_ok"] = (primary in tools) if tools else None
    calls = d.get("tool_calls") or []
    src = str(d.get("tool_choice_source") or "")
    rec["llm_tool_ok"] = (bool(calls) and src.startswith("llm") and "router" not in src
                          and calls[0].get("name") in tools) if (tools and model != "rules") else None
    # numbers
    nums, strs = evidence(ans)
    exps = []
    for i, spec in enumerate(item.get("expect", []) or []):
        spec = dict(spec)
        text_check = spec.pop("text", i == 0)
        try:
            e = evaluate(spec)
        except Exception as exc:  # noqa: BLE001
            e = {"value": None, "fmt": "eur", "name": None, "error": f"{type(exc).__name__}: {exc}"}
        e.update({"text_check": text_check, "in_data": in_data(e, nums, strs),
                  "in_text": in_text(e, ans.answer_markdown) if text_check else None})
        exps.append(e)
    rec["expected"] = exps
    if exps:
        rec["data_ok"] = all(e["in_data"] for e in exps)
        tx = [e["in_text"] for e in exps if e["text_check"]]
        rec["text_ok"] = (any(tx) if item.get("text_mode") == "any" else all(tx)) if tx else None
    else:
        rec["data_ok"] = rec["text_ok"] = None
    # names that must not appear (e.g. countries outside the persona's access)
    absent = item.get("absent") or []
    if absent:
        blob = (ans.answer_markdown or "") + " " + " ".join(strs)
        rec["absent_ok"] = not any(a in blob for a in absent)
        rec["data_ok"] = bool(rec["data_ok"] if rec["data_ok"] is not None else True) and rec["absent_ok"]
    # RLS
    if item.get("rls"):
        if exp_status == "refusal":
            rec["rls_ok"] = ans.status == "refusal" and not ans.table and not ans.sql_used
        else:
            rec["rls_ok"] = ans.status == "ok" and bool(rec["data_ok"])
    else:
        rec["rls_ok"] = None
    # guardrail
    g = d.get("guardrail") or {}
    hist = g.get("history") or []
    if model == "rules" or not g:
        rec["guard"] = None
    elif g.get("template"):
        rec["guard"] = "template"
    elif g.get("redacted"):
        rec["guard"] = "redacted"
    elif len(hist) > 1:
        rec["guard"] = "retry"
    else:
        rec["guard"] = "first_pass"
    rec["guard_problems"] = [p for h in hist for p in (h.get("problems") or [])]
    rec["dropped_sentences"] = g.get("dropped") or []
    return rec


def _resume(persona: str, turns: list[tuple[str, dict]], memory: dict) -> tuple[dict, bool]:
    """Store the earlier turns like the UI does, reload them, and return (restored memory, payloads intact)."""
    import tempfile

    from sqlalchemy import create_engine

    from app.history.store import ConversationStore

    with tempfile.TemporaryDirectory() as tmp:
        store = ConversationStore(engine=create_engine(f"sqlite:///{tmp}/history.sqlite"))
        cid = store.create(persona, persona, turns[0][0] if turns else "resume")
        for q, payload in turns:
            store.add_message(persona, cid, "user", q)
            store.add_message(persona, cid, "assistant", payload.get("answer_markdown") or "", payload)
        store.save_state(persona, cid, {"memory": memory, "persona": persona})
        _conv, msgs, state = store.load(persona, cid)
        store.engine.dispose()
    stored = [m["payload"] for m in msgs if m["role"] == "assistant"]
    same = stored == [json.loads(json.dumps(p, default=str)) for _, p in turns]
    return state.get("memory") or {}, bool(same)


def run_model(model: str, items: list[dict], fresh: bool, limit: int | None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{slug(model)}.jsonl"
    done = set()
    if path.exists() and not fresh:
        done = {json.loads(ln)["id"] for ln in path.read_text().splitlines() if ln.strip()}
    elif path.exists():
        path.unlink()
    todo = [it for it in items if it["id"] not in done][: limit or None]
    print(f"== {model}: {len(done)} done, {len(todo)} to run", flush=True)
    for k, it in enumerate(todo, 1):
        try:
            rec = run_question(it, model)
        except Exception as exc:  # noqa: BLE001
            rec = {"id": it["id"], "category": it["category"], "q": it["q"], "model": model, "status": "crash",
                   "expected_status": it.get("status", "ok"), "status_ok": False, "error": f"{type(exc).__name__}: {exc}",
                   "latency": None, "tool_ok": False if it.get("tools") else None, "data_ok": False if it.get("expect") else None,
                   "text_ok": False if it.get("expect") else None, "rls_ok": False if it.get("rls") else None,
                   "llm_tool_ok": None, "guard": None}
        with path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        flag = "OK " if rec.get("status_ok") and rec.get("tool_ok") is not False and rec.get("data_ok") is not False else "ERR"
        print(f"[{k:02d}/{len(todo)}] {flag} {it['id']:36s} status={rec.get('status'):13s} tool={rec.get('tool')} "
              f"data={rec.get('data_ok')} text={rec.get('text_ok')} {rec.get('latency')} s", flush=True)


# ------------------------------------------------------------------------------------------ report
def _rate(recs: list[dict], key: str) -> tuple[float | None, int, int]:
    vals = [r.get(key) for r in recs if r.get(key) is not None]
    if not vals:
        return None, 0, 0
    return sum(1 for v in vals if v) / len(vals), sum(1 for v in vals if v), len(vals)


def _pct(x: tuple) -> str:
    rate, k, n = x
    return "n/a" if rate is None else f"{rate * 100:.0f}% ({k}/{n})"


def _quantile(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    vals = sorted(vals)
    i = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[i]


def summarize(recs: list[dict]) -> dict:
    lat = [r["latency"] for r in recs if r.get("latency") is not None and r.get("expected_status") == "ok"]
    guards = [r.get("guard") for r in recs if r.get("guard")]
    llm = [r for r in recs if r.get("guard")]

    def flagged(word: str) -> int:
        return sum(any(word in p for p in (r.get("guard_problems") or [])) for r in llm)
    return {
        "questions": len(recs),
        "status": _rate(recs, "status_ok"), "tool": _rate(recs, "tool_ok"), "llm_tool": _rate(recs, "llm_tool_ok"),
        "data": _rate(recs, "data_ok"), "text": _rate(recs, "text_ok"), "rls": _rate(recs, "rls_ok"),
        "guard_first": (sum(g == "first_pass" for g in guards) / len(guards)) if guards else None,
        "guard_retry": (sum(g == "retry" for g in guards) / len(guards)) if guards else None,
        "guard_redacted": (sum(g == "redacted" for g in guards) / len(guards)) if guards else None,
        "guard_template": (sum(g == "template" for g in guards) / len(guards)) if guards else None,
        "llm_answers": len(llm),
        "flag_numbers": flagged("numbers that are not in FACTS"), "flag_month": flagged("figure in FACTS"),
        "flag_scope": flagged("name the scope"), "flag_reasons": flagged("reasons that are not in FACTS"),
        "dropped_sentences": sum(len(r.get("dropped_sentences") or []) for r in llm),
        "dropped_answers": sum(bool(r.get("dropped_sentences")) for r in llm),
        "p50": _quantile(lat, 0.5), "p95": _quantile(lat, 0.95),
        "crashes": sum(1 for r in recs if r.get("status") == "crash"),
    }


def report(items: list[dict]) -> None:
    order = {it["id"]: i for i, it in enumerate(items)}
    models = {}
    for p in sorted(OUT.glob("*.jsonl")):
        recs = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
        recs = [r for r in recs if r["id"] in order]
        if recs:
            models[recs[0]["model"]] = sorted(recs, key=lambda r: order[r["id"]])
    if not models:
        print("no results yet")
        return
    summ = {m: summarize(r) for m, r in models.items()}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    default = env("LLM_MODEL", "ollama/qwen2.5-coder:14b")
    lines = ["# Evaluation report", "",
             f"{len(items)} golden questions (tests/golden_questions.yaml), backend `{backend()}`, as-of date "
             f"{AS_OF.isoformat()}. Expected numbers are computed by raw SQL on the base tables "
             "(tests/eval_dsl.py), independently of the semantic layer. Default model: "
             f"`{default}`. All local models ran on CPU (Ollama, no GPU).", "",
             "## Model comparison", "",
             "| Model | Questions | Status as expected | Tool choice (final) | Tool choice (LLM alone) | "
             "Numbers in tool output | Headline number in answer text | RLS pass rate | Guardrail first pass / "
             "rewrite / redacted / template | Latency p50 / p95 (s) |",
             "|:---|---:|---:|---:|---:|---:|---:|---:|:---|:---|"]
    for m, s in summ.items():
        g = ("n/a" if s["guard_first"] is None else
             f"{s['guard_first'] * 100:.0f}% / {s['guard_retry'] * 100:.0f}% / "
             f"{(s.get('guard_redacted') or 0) * 100:.0f}% / {s['guard_template'] * 100:.0f}%")
        lat = "n/a" if s["p50"] is None else f"{s['p50']:.1f} / {s['p95']:.1f}"
        name = f"`{m}`" + (" (no LLM, deterministic router + templated text)" if m == "rules" else "")
        lines.append(f"| {name} | {s['questions']} | {_pct(s['status'])} | {_pct(s['tool'])} | {_pct(s['llm_tool'])} | "
                     f"{_pct(s['data'])} | {_pct(s['text'])} | {_pct(s['rls'])} | {g} | {lat} |")
    lines += ["", "How to read the columns:", "",
              "- **Tool choice (final)**: the tool that produced the answer is in the accepted list. When the "
              "LLM returns no usable tool call (or its call fails), a deterministic router supplies one.",
              "- **Tool choice (LLM alone)**: the LLM's own first tool call was valid and accepted, without the router.",
              "- **Numbers in tool output**: every expected value (SQL ground truth) is present in the table / "
              "tool output, within 1 USD or 1e-6 for ratios.",
              "- **Headline number in answer text**: the headline value(s) appear in the written answer within "
              "display rounding (for example USD 54.4M or 17.0%).",
              "- **Guardrail**: share of LLM answers that passed the numeric check first time, passed after one "
              "rewrite, passed after dropping the sentences with unsupported numbers, or were replaced by the "
              "templated answer.", ""]
    lines += ["## Narrative checks", "",
              "Answers whose drafts the guard rejected, by reason (an answer can have several), and sentences "
              "dropped from accepted answers because they gave causes that the data does not contain.", "",
              "| Model | LLM answers | Number not in data | Number tied to the wrong month or leaver type | "
              "Scope named too broadly | Cause not in data (headline) | Sentences dropped (answers) |",
              "|:---|---:|---:|---:|---:|---:|---:|"]
    for m, s in summ.items():
        if not s.get("llm_answers"):
            continue
        lines.append(f"| `{m}` | {s['llm_answers']} | {s['flag_numbers']} | {s['flag_month']} | {s['flag_scope']} | "
                     f"{s['flag_reasons']} | {s['dropped_sentences']} ({s['dropped_answers']}) |")
    lines.append("")
    cats = list(dict.fromkeys(it["category"] for it in items))
    for m, recs in models.items():
        lines += [f"## Per category: `{m}`", "",
                  "| Category | Questions | Status | Tool | Numbers (data) | Numbers (text) | p50 latency (s) |",
                  "|:---|---:|---:|---:|---:|---:|---:|"]
        for c in cats:
            rc = [r for r in recs if r["category"] == c]
            if not rc:
                continue
            lat = [r["latency"] for r in rc if r.get("latency") is not None]
            lines.append(f"| {c} | {len(rc)} | {_pct(_rate(rc, 'status_ok'))} | {_pct(_rate(rc, 'tool_ok'))} | "
                         f"{_pct(_rate(rc, 'data_ok'))} | {_pct(_rate(rc, 'text_ok'))} | "
                         f"{(statistics.median(lat) if lat else 0):.1f} |")
        fails = [r for r in recs if not r.get("status_ok") or r.get("tool_ok") is False or r.get("data_ok") is False
                 or r.get("text_ok") is False or r.get("rls_ok") is False]
        lines += ["", f"Questions with at least one failed check: {len(fails)}", ""]
        if fails:
            lines += ["| id | status | tool | data | text | note |", "|:---|:---|:---|:---|:---|:---|"]
            for r in fails:
                note = r.get("error") or "; ".join(
                    f"expected {e.get('name') + ' ' if e.get('name') else ''}{e['value']:.4g} ({e['fmt']})"
                    + ("" if e.get("in_data") else " not in output")
                    + ("" if e.get("in_text") in (True, None) else " not in text")
                    for e in (r.get("expected") or []) if e.get("value") is not None
                    and (not e.get("in_data") or e.get("in_text") is False))
                lines.append(f"| {r['id']} | {r.get('status')} (exp. {r.get('expected_status')}) | {r.get('tool')} | "
                             f"{r.get('data_ok')} | {r.get('text_ok')} | {note[:180]} |")
        lines.append("")
    lines += _rls_section(models) + _landing_section(models)
    (ROOT / "eval_report.md").write_text("\n".join(lines) + "\n")
    print(f"wrote eval_report.md ({len(models)} models)")


def _rls_section(models: dict) -> list[str]:
    out = ["## Row-level security", "",
           "Questions asked by a restricted persona (United States Country Head or Environmental Lab Testing PL "
           "Leader): out-of-scope requests must be refused without a table or SQL; in-scope requests must return "
           "the scoped numbers, and other units' names must not appear.", "",
           "| Model | RLS questions | Passed | Refusals correct | Scoped answers correct |", "|:---|---:|---:|---:|---:|"]
    for m, recs in models.items():
        rr = [r for r in recs if r.get("rls_ok") is not None]
        ref = [r for r in rr if r.get("expected_status") == "refusal"]
        sco = [r for r in rr if r.get("expected_status") != "refusal"]
        out.append(f"| `{m}` | {len(rr)} | {_pct(_rate(rr, 'rls_ok'))} | {_pct(_rate(ref, 'rls_ok'))} | "
                   f"{_pct(_rate(sco, 'rls_ok'))} |")
    return out + [""]


def _landing_section(models: dict) -> list[str]:
    out = ["## Landing", "",
           "Tool choice on the landing questions (category `landing`) and the landing engine's measured backtest "
           "accuracy (`make backtest`, last 24 closed months; docs/landing_backtest_report.md).", "",
           "| Model | Landing questions | Tool choice (final) | Tool choice (LLM alone) | Numbers in tool output | "
           "Headline number in answer text |", "|:---|---:|---:|---:|---:|---:|"]
    for m, recs in models.items():
        lr = [r for r in recs if r.get("category") == "landing"]
        if lr:
            out.append(f"| `{m}` | {len(lr)} | {_pct(_rate(lr, 'tool_ok'))} | {_pct(_rate(lr, 'llm_tool_ok'))} | "
                       f"{_pct(_rate(lr, 'data_ok'))} | {_pct(_rate(lr, 'text_ok'))} |")
    out.append("")
    try:
        from app.db import get_engine
        from app.landing import engine as LE
        from app.landing.query import backtest_metrics
        bt = backtest_metrics(get_engine("group_cfo"))
    except Exception as exc:  # noqa: BLE001
        return out + [f"Backtest metrics not available ({type(exc).__name__})."]
    if bt.empty:
        return out + ["No backtest has been run yet (`make backtest`)."]
    g = bt[(bt.scope_type == "group") & (bt.metric == "wape")]
    out += [f"Backtest run {bt['run_date'].iloc[0]}: group-level WAPE by method (lower is better).", "",
            "| Method | Billing | Revenue | Operating profit (excl. WIP) | Operating profit (as booked) |",
            "|:---|---:|---:|---:|---:|"]
    for method in ("ensemble", LE.BASELINE, *LE.METHODS):
        row = g[g.method == method].set_index("measure")["value"]
        if row.empty:
            continue
        cell = lambda k: f"{100 * row[k]:.2f}%" if k in row.index else "n/a"  # noqa: E731
        out.append(f"| {LE.METHOD_LABEL.get(method, method)} | {cell('billing')} | {cell('revenue')} | "
                   f"{cell('maop_xw')} | {cell('maop')} |")
    cov = bt[(bt.scope_type == "org_level") & (bt.measure == "billing") & (bt.method == "ensemble")
             & bt.metric.str.startswith("coverage")]
    if not cov.empty:
        out += ["", "Share of actuals inside the P10-P90 range (billing, target 70-90%): " + "; ".join(
            f"{r.scope_value} {100 * r.value:.1f}%" for r in cov.itertuples()) + "."]
    return out + [""]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=env("LLM_MODEL", "ollama/qwen2.5-coder:14b"))
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fresh", action="store_true", help="discard previous results for these models")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    items = yaml.safe_load(GOLDEN.read_text())
    if args.only:
        keep = set(args.only.split(","))
        sel = [it for it in items if it["id"] in keep]
    else:
        sel = items
    if not args.report_only:
        for m in [x.strip() for x in args.models.split(",") if x.strip()]:
            run_model(m, sel, args.fresh, args.limit)
    report(items)


if __name__ == "__main__":
    main()
