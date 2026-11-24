"""LangGraph agent.

    preprocess -> plan -> act -> write -> guard -> finalize
       |                    |               |
       +-- refuse/clarify --+-- tool error -+--> finalize  (guard may loop back to write once)

* preprocess: deterministic entity resolution, conversation memory merge (follow-ups such as
  "now for Canada", "split direct staff costs by BU", "same vs FC2", or "how does that compare with last
  year?"; corrections such as "no, I meant Mexico" or "not YTD, full year 2025"), pushback without details
  ("that's not right": what the previous answer used, with options to change each part), access check
  (polite refusal, never data).
* plan:       the LLM chooses the tool and arguments (native tool calling via LiteLLM), seeing the last few
              questions of the conversation. If the model produces no usable call, a deterministic router
              supplies one (tracked as a fallback).
* act:        tools run SQLAlchemy Core queries; the LLM never does arithmetic.
* write:      the LLM writes the insight from pre-formatted FACTS only.
* guard:      numeric guardrail plus narrative checks (month binding, scope, reasons that are not in
              the data); regenerate once, then fall back to a templated answer.
* finalize:   validated output contract (text, finance table, deterministic chart, filters, SQL,
              exactly three follow-up questions) + updated memory.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agent import guardrails, llm
from app.agent.prompts import PLANNER_SYSTEM, PLANNER_USER, WRITER_RETRY, WRITER_SYSTEM, WRITER_USER
from app.agent.tools import DATA_TOOLS, TOOLS, ToolContext, ToolOutput, openai_tools, run_tool, wf_focus_from
from app.config import as_of_date, env, settings
from app.semantic import time_intel as ti
from app.semantic.access import check_access, child_level, default_org, level_label, scope_label
from app.semantic.dims import dims
from app.semantic.entity_resolver import LEVEL_LABEL, ORG_LEVELS, Resolution, org_label, resolve
from app.semantic.query_builder import WF_METRICS
from app.semantic.registry import registry
from app.viz import format as F
from app.viz.charts import chart_spec
from app.viz.tables import build_table


# ------------------------------------------------------------------------------------------
# Output contract
# ------------------------------------------------------------------------------------------
class ChartSpec(BaseModel):
    type: str = "none"
    title: str = ""
    fmt: str = "eur"
    x: str | None = None
    y: list[str] = Field(default_factory=list)
    data: list[dict] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class FinalAnswer(BaseModel):
    answer_markdown: str
    table: list[dict] = Field(default_factory=list)
    table_spec: dict = Field(default_factory=dict)
    chart_spec: ChartSpec = Field(default_factory=ChartSpec)
    filters_used: dict = Field(default_factory=dict)
    sql_used: list[str] = Field(default_factory=list)
    followups: list[str] = Field(min_length=3, max_length=3)
    status: Literal["ok", "refusal", "clarification", "error"] = "ok"
    diagnostics: dict = Field(default_factory=dict)


class AgentState(TypedDict, total=False):
    question: str
    user_id: str
    as_of: str
    model: str
    memory: dict
    merged: dict
    route: str
    message: str
    options: list
    suggested: dict
    calls: list
    tool_choice_source: str
    outputs: list
    answer: str
    attempts: int
    retry: bool
    guard: dict
    final: dict
    new_memory: dict
    timings: dict
    llm_calls: list
    errors: list
    ui_filters: dict


FOLLOWUP_RX = re.compile(r"^\s*(now|and|what about|how about|same|also|ok|okay|then|split|break|drill|"
                         r"show me the same|vs\.?|versus|compare that|for|instead|only)\b", re.I)
# Corrections of the previous answer: "no, I meant Mexico", "not YTD, full year 2025", "use Q3 instead"
CORRECTION_RX = re.compile(r"^\s*(?:no|nope|nah|wrong|actually|sorry|oops|correction|rather|instead|not|use|make it|"
                           r"change (?:it|that|this) to|switch to)\b"
                           r"|\b(?:i meant|i mean|i wanted|i was asking|i asked for|instead|rather than)\b", re.I)
# Words that point back to the previous answer, anywhere in the question ("how does that compare ...")
REF_RX = re.compile(r"\b(?:that|it|its|this(?!\s+(?:year|month|quarter|period|fy|ytd))|those|these|them|same|"
                    r"there|again|above|previous|earlier)\b", re.I)
# Pushback without saying what is wrong: answered with what was used and options to change it
DISPUTE_RX = re.compile(
    r"\b(?:that'?s|that is|this is|it'?s|it is|these are|those are|the (?:numbers?|figures?|answer) (?:is|are))\s+"
    r"(?:not (?:right|correct|accurate|what i (?:asked|meant|wanted))|wrong|incorrect|inaccurate|off)\b"
    r"|\bare you sure\b|\b(?:doesn'?t|does not|don'?t|do not) (?:look|seem|sound) (?:right|correct)\b"
    r"|\b(?:looks|seems|sounds) (?:wrong|off|incorrect|too (?:high|low))\b|\bcan'?t be (?:right|correct)\b"
    r"|\bi (?:don'?t|do not) (?:think|believe) (?:that'?s|that is|this is|it'?s|it is) (?:right|correct)\b"
    r"|\b(?:that|this|it) (?:doesn'?t|does not) (?:match|add up)\b"
    r"|^\s*(?:no[,.!]?\s+)?(?:wrong|incorrect|not right|not correct|really)\s*[?!.]*\s*$", re.I)
# "Canada as a whole", "all of Canada", "total Canada": replace the scope instead of narrowing the previous one
SCOPE_RESET_RX = re.compile(r"\b(?:as a whole|all of|the whole of|whole|total|entire|overall)\b", re.I)


def _use_llm(model: str | None) -> bool:
    return (model or "").strip().lower() not in ("", "none", "rules", "off")


# ------------------------------------------------------------------------------------------
# Deterministic helpers
# ------------------------------------------------------------------------------------------
def is_followup(q: str, res: Resolution, mem: dict) -> bool:
    if not mem:
        return False
    if FOLLOWUP_RX.search(q) or CORRECTION_RX.search(q) or DISPUTE_RX.search(q):
        return True
    has_metric = bool(res.metric)
    has_org = bool(res.org_filter)
    if REF_RX.search(q) and not (has_metric and has_org):
        return True
    return len(q.split()) <= 7 and not (has_metric and has_org)


def is_dispute(q: str, res: Resolution, mem: dict) -> bool:
    """'That's not right' / 'are you sure?' after an answer, with nothing new to change."""
    if not (mem or {}).get("last_used") or not DISPUTE_RX.search(q):
        return False
    return not (res.org_filter or res.metric or res.period or res.versions or res.comparisons or res.level_hint
                or set(res.intents) - {"pnl"})


ORDINAL_RX = re.compile(
    r"\b(?:the\s+)?(first|1st|second|2nd|third|3rd|last|top|bottom|worst|best|lowest|highest|weakest|strongest)"
    r"\s+(?:one|bu|business unit|country|business|region|product line|sector|entity|unit)\b"
    r"|\bnumber\s+(one|two|three|1|2|3)\b|#\s?([123])\b", re.I)
ORDINAL_INDEX = {"first": 0, "1st": 0, "top": 0, "one": 0, "1": 0, "second": 1, "2nd": 1, "two": 1, "2": 1,
                 "third": 2, "3rd": 2, "three": 2, "3": 2, "last": -1, "bottom": -1}


def ordinal_reference(q: str, res: Resolution, mem: dict) -> dict | None:
    """'why is the first one so low?' after a ranking -> org filter of that entity."""
    ents, level = mem.get("entities") or [], mem.get("entities_level")
    if not ents or not level or res.org_filter:
        return None
    m = ORDINAL_RX.search(q)
    if not m:
        return None
    word = (m.group(1) or m.group(2) or m.group(3) or "").lower()
    if word in ("worst", "lowest", "weakest"):
        idx = 0 if mem.get("entities_ascending") else -1
    elif word in ("best", "highest", "strongest"):
        idx = -1 if mem.get("entities_ascending") else 0
    else:
        idx = ORDINAL_INDEX.get(word, 0)
    try:
        return {level: [ents[idx]]}
    except IndexError:
        return None


def merge_context(res: Resolution, mem: dict, followup: bool) -> dict:
    m = {"org_filter": dict(res.org_filter), "metric": res.metric, "ratio": res.ratio, "metrics": res.metrics,
         "period": res.period, "period_is_range": res.period_is_range, "versions": list(res.versions),
         "comparisons": list(res.comparisons), "level_hint": res.level_hint, "top_n": res.top_n,
         "ascending": res.ascending, "intents": list(res.intents), "tool": None, "followup": followup,
         "both_margins": res.both_margins}
    if not followup:
        return m
    if res.org_filter and SCOPE_RESET_RX.search(res.clean_text or res.text or ""):
        m["org_filter"] = dict(res.org_filter)
    elif res.org_filter:
        org = dict(mem.get("org_filter") or {})
        changed_levels = set(res.org_filter)
        if changed_levels & {"l1_group", "l2_region", "l3_country", "l4_product_line"}:
            org.pop("l5_business", None)
            org.pop("l6_bu", None)
        if "l2_region" in changed_levels:
            org.pop("l3_country", None)
        if "l1_group" in changed_levels:
            org = {}
        org.update(res.org_filter)
        if "l1_group" in org and len(org) > 1:
            org.pop("l1_group")
        m["org_filter"] = org
    else:
        m["org_filter"] = dict(mem.get("org_filter") or {})
    if not res.metric:
        m["metric"], m["ratio"] = mem.get("metric"), mem.get("ratio")
        m["both_margins"] = bool(mem.get("both_margins"))
        if m["metric"] and m["metric"] != m["ratio"] and registry().get_metric(m["metric"]) is not None:
            m["metrics"] = [m["metric"]]        # the tools read `metrics`: keeps the P&L line asked about earlier
    if not res.period:
        m["period"], m["period_is_range"] = mem.get("period"), mem.get("period_is_range", False)
    if not res.versions and not res.comparisons:
        m["versions"], m["comparisons"] = list(mem.get("versions") or []), list(mem.get("comparisons") or [])
    if not res.intents:
        m["intents"] = list(mem.get("intents") or [])
        if not res.level_hint:
            m["tool"] = mem.get("tool")
    if not res.level_hint and "rank" in m["intents"] and not res.intents:
        m["level_hint"], m["top_n"], m["ascending"] = mem.get("level_hint"), mem.get("top_n"), mem.get("ascending")
    return m


def _period_text(p: dict | None) -> str:
    if not p:
        return ""
    if p["type"] == "RANGE":
        return f"{p['start'] // 100}-{p['start'] % 100:02d} to {p['end'] // 100}-{p['end'] % 100:02d}"
    if p["type"] == "MONTH":
        return f"{p['end'] // 100}-{p['end'] % 100:02d}"
    return p["label"]


YTD_LANDING_RX = re.compile(r"\b(ytd|year[- ]to[- ]date|qtd|quarter[- ]to[- ]date|through|thru|till|until|up to|"
                            r"including (the )?landing|incl\.? (the )?landing|with (the )?landing|full[- ]year|fy|"
                            r"year[- ]end|outlook|so far)\b", re.I)
MISS_RX = re.compile(r"\b(miss|missing|beat|exceed|short|shortfall|below|above|behind|ahead|rank|top|bottom|worst|best|"
                     r"which (bus?|business units?|businesses|countries|product lines|regions))\b", re.I)
EXPLAIN_RX = re.compile(r"\b(why|explain|how (is|was|did|does) .{0,30}(calculat|comput|built|work|estimat)|method|"
                        r"methodology|drivers?|how do you (calculate|compute|estimate))\b", re.I)


def route_landing(mg: dict, q: str) -> dict:
    org_txt = org_label(mg["org_filter"]) if mg.get("org_filter") else ""
    metric = mg.get("ratio") or mg.get("metric")
    both = bool(mg.get("both_margins"))
    p = mg.get("period") or {}
    if YTD_LANDING_RX.search(q) or p.get("type") in ("YTD", "QTD", "FY"):
        ptype = "FY" if re.search(r"\b(full[- ]year|fy|year[- ]end|outlook)\b", q, re.I) else \
            ("QTD" if re.search(r"\b(qtd|quarter[- ]to[- ]date)\b", q, re.I) else "YTD")
        return {"name": "get_ytd_with_landing", "arguments": {
            "metric_or_ratio": "operating_margins" if both else (metric or "revenue"), "org": org_txt,
            "through_month": "", "period_type": ptype, "comparisons": ["PY", "Budget", "LatestFC"]}}
    if MISS_RX.search(q) or "rank" in (mg.get("intents") or []) or mg.get("level_hint"):
        level = mg.get("level_hint") or "l6_bu"
        return {"name": "rank_landing", "arguments": {
            "metric": metric if metric and not both else "billing", "org_level": level, "parent_filter": org_txt,
            "top_n": mg.get("top_n") or 10,
            "sort_by": "gap_vs_forecast" if re.search(r"\bforecast\b", q, re.I) else "gap_vs_budget"}}
    if EXPLAIN_RX.search(q):
        return {"name": "explain_landing", "arguments": {"org": org_txt}}
    month = ""
    if p.get("type") == "MONTH":
        month = f"{p['end'] // 100}-{p['end'] % 100:02d}"
    measures = ["profit %"] if both else ([metric] if metric else [])
    return {"name": "get_landing", "arguments": {"org": org_txt, "measures": measures, "month": month}}


def route_deterministic(mg: dict) -> dict:
    """Rule-based tool choice used as safety net when the LLM does not return a usable call."""
    intents = set(mg.get("intents") or [])
    q = mg.get("question") or ""
    if "catalog" in intents:
        from app.semantic.catalog import kind_from_text  # noqa: WPS433

        parent = org_label(mg["org_filter"]) if mg.get("org_filter") and not mg.get("org_from_sidebar") else ""
        return {"name": "describe_catalog", "arguments": {"kind": kind_from_text(q), "parent_filter": parent}}
    if "landing" in intents or (mg.get("tool") in ("get_landing", "get_ytd_with_landing", "rank_landing",
                                                   "explain_landing") and not intents):
        return route_landing(mg, q)
    metric = mg.get("ratio") or mg.get("metric")
    org_txt = org_label(mg["org_filter"]) if mg.get("org_filter") else ""
    p = mg.get("period")
    ptxt = _period_text(p)
    versions = [v for v in (mg.get("versions") or [])]
    comps = list(mg.get("comparisons") or []) + [v for v in versions if v != "Actual"]
    level = mg.get("level_hint")
    if mg.get("both_margins") and not intents & {"rank", "trend", "why", "breakdown", "versions", "pnl", "cockpit",
                                                 "workforce"} and not level:
        return {"name": "get_ratio", "arguments": {"ratio_name": "operating_margins", "org": org_txt, "period": ptxt,
                                                   "comparison": ",".join(comps or ["PY", "Budget"])}}
    if "cockpit" in intents:
        return {"name": "get_kpi_cockpit", "arguments": {"org": org_txt, "month": ptxt if p and p["type"] == "MONTH" else ""}}
    if "workforce" in intents or (mg.get("tool") == "get_workforce" and not intents):
        return {"name": "get_workforce", "arguments": {"org": org_txt, "period": ptxt, "group_by": "", "metric": "",
                                                       "top_n": mg.get("top_n") or 0}}
    if mg.get("tool") and not intents and mg["tool"] in TOOLS:
        tool = mg["tool"]
        intents = {"get_trend": {"trend"}, "variance_drivers": {"why"}, "rank_entities": {"rank"},
                   "compare_versions": {"versions"}, "get_kpi_cockpit": {"cockpit"}}.get(tool, set())
        if tool == "get_kpi_cockpit":
            return {"name": tool, "arguments": {"org": org_txt}}
        if tool == "get_ratio" and mg.get("ratio"):
            return {"name": tool, "arguments": {"ratio_name": mg["ratio"], "org": org_txt, "period": ptxt,
                                                "comparison": ",".join(comps or ["PY", "Budget"])}}
        if tool == "get_pnl":
            return {"name": tool, "arguments": {"org": org_txt, "period": ptxt,
                                                "versions": ["Actual"] + (comps or ["PY", "Budget"])}}
    fc_versions = [v for v in versions if v in ("Budget", "FC1", "FC2", "FC3", "LatestFC")]
    if "rank" in intents or (level and "trend" not in intents):
        top = mg.get("top_n")
        return {"name": "rank_entities", "arguments": {
            "metric_or_ratio": metric or "maop", "org_level": level or "l6_bu", "parent_filter": org_txt,
            "period": ptxt, "top_n": top if top is not None else (5 if "rank" in intents else 0),
            "ascending": bool(mg.get("ascending"))}}
    if "why" in intents:
        return {"name": "variance_drivers", "arguments": {"metric": metric or "maop", "org": org_txt, "period": ptxt,
                                                          "comparison": comps[0] if comps else "PY", "depth": 1}}
    if "breakdown" in intents and metric:
        return {"name": "variance_drivers", "arguments": {"metric": metric, "org": org_txt, "period": ptxt,
                                                          "comparison": comps[0] if comps else "PY", "depth": 2}}
    forecasty = any(v.startswith("FC") or v == "LatestFC" for v in fc_versions)
    if "versions" in intents or len(fc_versions) >= 2 or (forecasty and not metric) or \
            (forecasty and p and p["type"] == "FY"):
        return {"name": "compare_versions", "arguments": {
            "org": org_txt, "period": ptxt, "versions": ["Actual"] + [v for v in versions if v != "Actual"]
            if versions else ["Actual", "Budget", "FC1", "FC2", "FC3"]}}
    if "trend" in intents or mg.get("period_is_range"):
        start = ""
        if p and (p["type"] == "RANGE" or mg.get("period_is_range")):
            start = f"{p['start'] // 100}-{p['start'] % 100:02d}"
        elif p and p["type"] in ("YTD", "FY"):
            start = f"{p['end'] // 100}-01"
        return {"name": "get_trend", "arguments": {"metric_or_ratio": metric or "maop", "org": org_txt,
                                                   "start": start, "end": "",
                                                   "versions": ["Actual"] + (comps or ["PY", "Budget"])}}
    if mg.get("ratio"):
        return {"name": "get_ratio", "arguments": {"ratio_name": mg["ratio"], "org": org_txt, "period": ptxt,
                                                   "comparison": ",".join(comps or ["PY", "Budget"])}}
    m = registry().get_metric(metric) if metric else None
    if m is not None and m.kind in ("leaf", "group", "computed") and not intents & {"pnl", "cockpit"}:
        return {"name": "variance_drivers", "arguments": {"metric": metric, "org": org_txt, "period": ptxt,
                                                          "comparison": comps[0] if comps else "PY", "depth": 1}}
    return {"name": "get_pnl", "arguments": {"org": org_txt, "period": ptxt,
                                             "versions": ["Actual"] + (comps or ["PY", "Budget"]), "account_depth": 1}}


def _resolution_from(mg: dict, q: str) -> Resolution:
    return Resolution(text=q, org_filter=mg.get("org_filter") or {}, metrics=mg.get("metrics") or [],
                      ratio=mg.get("ratio"), period=mg.get("period"), period_is_range=mg.get("period_is_range", False),
                      versions=mg.get("versions") or [], comparisons=mg.get("comparisons") or [],
                      level_hint=mg.get("level_hint"), top_n=mg.get("top_n"), ascending=mg.get("ascending"),
                      intents=mg.get("intents") or [], both_margins=bool(mg.get("both_margins")))


def _compact(mg: dict) -> dict:
    d = {"org": org_label(mg["org_filter"]) if mg.get("org_filter") else "(user default scope)",
         "metric_or_ratio": mg.get("ratio") or mg.get("metric") or "(not specified)",
         "period": (mg.get("period") or {}).get("label") or "(default: YTD)",
         "versions": mg.get("versions") or [], "comparisons": mg.get("comparisons") or [],
         "intents": mg.get("intents") or []}
    if mg.get("level_hint"):
        d["rank_by_level"] = mg["level_hint"]
    if mg.get("top_n") is not None:
        d["top_n"] = mg["top_n"]
    if mg.get("ascending"):
        d["ascending"] = True
    return d


def template_answer(outputs: list[ToolOutput]) -> str:
    """Deterministic answer text (no LLM, or LLM text rejected by the guardrail)."""
    o = outputs[0]
    facts = [f for f in (o.facts or []) if not f.startswith("Scope ")]
    if not facts:
        return "Here are the figures you asked for."
    head = facts[0].rstrip(".")
    body = facts[1].rstrip(".") if len(facts) > 1 and o.kind not in ("ranking", "cockpit", "trend") else ""
    if body and body in o.bullets:
        body = ""
    return f"**{head}.**" + (f"\n\n{body}." if body else "")


def assemble_answer(core: str, outputs: list[ToolOutput]) -> str:
    """Narrative (LLM or template) + deterministic key-figure bullets + scope notes."""
    text = (core or "").rstrip()
    bullets = [b for b in outputs[0].bullets if b and b not in text]
    if bullets:
        text += "\n\n" + "\n".join(f"- {b}" for b in bullets)
    notes = [n for n in dict.fromkeys(n for o in outputs for n in o.notes) if n.rstrip(".") not in text][:2]
    if notes:
        text += "\n\n_" + " ".join(notes) + "_"
    return text


def clean_answer(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", t)
    out = []
    for ln in t.splitlines():
        if re.match(r"^\s*\|", ln) or re.match(r"^\s*#{1,6}\s", ln):
            continue
        if re.match(r"^\s*(\*\*)?\s*(follow[- ]?up|suggested questions|next questions|key figures)", ln, re.I):
            break
        if re.match(r"^\s*([-*•]|\d+[.)])\s+", ln):        # bullets are added deterministically
            continue
        out.append(ln)
    return guardrails.canonical_terms(re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip())


def make_followups(primary: ToolOutput | None, mg: dict, user_id: str) -> list[str]:
    if primary is not None and len(primary.meta.get("followups") or []) >= 3:
        return list(primary.meta["followups"])[:3]
    org_f = (primary.filters_used.get("org_filter") if primary else None) or mg.get("org_filter") or default_org(user_id)
    org = org_label(org_f)
    lvl = child_level(org_f) or "l6_bu"
    child = LEVEL_LABEL.get(lvl, "BU").lower()
    children = F.plural(child) if child != "bu" else "BUs"
    reg = registry()
    kind = primary.kind if primary else ""
    meta = primary.meta if primary else {}
    op = reg.metrics["maop"].name.lower()                    # "operating profit"
    mname = meta.get("name") or reg.metrics["maop"].name
    year = ti.ym(ti.last_closed_month())[0]
    if kind == "pnl":
        return [f"What are the main drivers of the {op} variance vs budget for {org}?",
                f"Show the monthly {op} trend for {org} vs last year",
                f"Which {children} in {org} have the lowest operating margin this year?"]
    if kind == "trend":
        return [f"Why did {mname} change vs last year for {org}?",
                f"Rank {children} in {org} by {mname} this year",
                f"Compare Budget vs FC3 vs Actual for {org}"]
    if kind == "ratio":
        return [f"Show the {mname} trend for {org} since {year - 2}",
                f"Rank {children} in {org} by {mname} this year",
                f"What drives the change in {mname} vs last year for {org}?"]
    if kind == "drivers":
        top = (primary.data[0]["Driver"] if primary.data else None) or "personnel costs"
        top = re.sub(r" as % of .*", "", str(top))
        return [f"Show the monthly trend of {mname} for {org} since {year - 1}",
                f"Show the {top} trend for {org} vs budget",
                f"Compare Budget vs FC3 vs Actual for {org}"]
    if kind == "ranking":
        lvl_lbl = meta.get("level_label", "BU")
        first = primary.data[0][lvl_lbl] if primary.data else org
        other = "bottom" if not meta.get("ascending") else "top"
        return [f"Why is {first} where it is on {mname}?",
                f"Show the {mname} trend for {first} since {year - 1}",
                f"Show the {other} 5 {F.plural(lvl_lbl)} by {mname} in {org} instead"]
    if kind == "versions":
        return [f"Why is Actual different from Budget for {org} this year?",
                f"Show the {op} trend vs Budget for {org} this year",
                f"What does the latest forecast say for the full year {year} for {org}?"]
    if kind == "cockpit":
        return [f"Why did direct margin change vs last year for {org}?",
                f"Show the utilization rate trend for {org} since {year - 1}",
                f"Rank {children} in {org} by direct margin this year"]
    if kind == "workforce":
        group = meta.get("group")
        opts = [("role", f"Show attrition by role for {org} this year"),
                ("grade", f"Show utilization by grade for {org} this year"),
                ("month", f"Show headcount, hires and leavers by month for {org} this year"),
                (lvl, f"Which {children} in {org} have the highest attrition this year?"),
                ("pnl", f"How is the {op} of {org} YTD vs last year and budget?")]
        return [q for g, q in opts if g != group][:3]
    scope = scope_label(user_id)
    return [f"How is {op} YTD vs last year and budget for {scope}?",
            f"Show the operational profitability cockpit for {scope}",
            f"Show the operating margin trend for {scope} since {year - 1}"]


# ------------------------------------------------------------------------------------------
# Conversation: what each answer used, what a follow-up carried over, replies to pushback
# ------------------------------------------------------------------------------------------
COMPARISON_TEXT = {"PY": "prior year (PY)", "LatestFC": "latest forecast"}
NO_COMPARISON_OPTION = ("rank_entities", "get_kpi_cockpit", "get_workforce")


def _and(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _measure_label(primary: ToolOutput, mg: dict) -> str:
    reg = registry()
    if primary.tool == "get_workforce":
        focus = primary.meta.get("focus") or "headcount"
        return WF_METRICS.get(focus, (None, focus.replace("_", " ").capitalize()))[1]
    if primary.tool == "get_kpi_cockpit":
        return "Operational KPI cockpit"
    args = primary.meta.get("args", {}) or {}
    mid = args.get("ratio_name") or args.get("metric_or_ratio") or args.get("metric") or mg.get("ratio") or mg.get("metric")
    r = reg.get_ratio(mid) if mid else None
    if r is not None:
        return r.name
    m = reg.get_metric(mid) if mid else None
    return m.name if m is not None else reg.metrics["maop"].name


def used_record(primary: ToolOutput, mg: dict, filters: dict) -> dict:
    """What an answer used, for the pushback reply, the "Carried over" line and the planner's history."""
    labels = []
    for v in filters.get("versions") or []:
        lbl = str(v).split(" (")[0].strip()
        if lbl and lbl not in labels:
            labels.append(lbl)
    comps = [v for v in labels if v != "Actual"]
    wf = primary.tool == "get_workforce"
    if wf and not comps:
        comps = ["PY"]
    measure = _measure_label(primary, mg)
    scope = filters.get("org") or org_label(mg.get("org_filter") or {})
    period = filters.get("period") or ""
    source = ("fictional employee records, closed months" if wf else
              f"general ledger (GL) management P&L and statistics, closed months, {filters.get('currency', 'USD')} "
              f"at {settings().get('fx_rate_label', 'constant budget rate')}")
    vs = ("vs " + _and(comps)) if comps else ""
    return {"measure": measure, "scope": scope, "period": period, "months": filters.get("months") or "",
            "period_type": (mg.get("period") or {}).get("type") or "YTD", "comparisons": comps,
            "comparison_text": _and([COMPARISON_TEXT.get(c, c) for c in comps]) or "no comparison",
            "source": source, "tool": primary.tool,
            "text": " · ".join(x for x in (measure, scope, period, vs) if x) + f" ({primary.tool})"}


def carried_labels(used: dict, mg: dict) -> list[str]:
    """What a follow-up took from earlier turns (e.g. ["Net income", "YTD Oct 2026"]), shown under the answer."""
    if not mg.get("followup"):
        return []
    asked, had = mg.get("asked") or {}, mg.get("had") or {}
    out = []
    if had.get("metric") and not asked.get("metric") and used["tool"] != "get_kpi_cockpit":
        out.append(used["measure"])
    if had.get("org") and not asked.get("org"):
        out.append(used["scope"])
    if had.get("period") and not asked.get("period") and used["period"]:
        out.append(used["period"])
    if had.get("versions") and not asked.get("versions") and used["comparisons"]:
        out.append("vs " + _and(used["comparisons"]))
    return out


def history_text(mem: dict | None) -> str:
    hist = (mem or {}).get("history") or []
    if not hist:
        return "none (first question of the conversation)"
    return "\n".join(f'{i}. "{h.get("q", "")}" -> used: {h.get("used", "")}' for i, h in enumerate(hist[-4:], 1))


def _alt_measure(used: dict, mem: dict) -> str | None:
    if used.get("tool") == "get_workforce":
        return "headcount" if str(mem.get("wf_focus") or "").endswith("attrition") else "attrition"
    if used.get("tool") == "get_kpi_cockpit":
        return None
    if mem.get("ratio"):
        return "direct margin" if mem["ratio"] == "maop_margin_revenue" else "operating margin"
    return "revenue" if (mem.get("metric") or "maop") == "maop" else registry().metrics["maop"].name.lower()


def _parent_scope(org_filter: dict, user_id: str) -> str | None:
    """'Canada as a whole' for Canada · Environmental Lab Testing; 'the whole RL Group' for a country."""
    levels = [lvl for lvl in ORG_LEVELS if lvl in (org_filter or {}) and lvl != "l1_group"]
    if not levels:
        return None
    parent = {k: v for k, v in org_filter.items() if k not in (levels[-1], "l1_group")}
    if check_access(user_id, parent).status != "ok":
        return None
    return f"{org_label(parent)} as a whole" if parent else "the whole RL Group"


def change_options(mem: dict, user_id: str) -> list[str]:
    """One button per part of the previous answer (measure, scope, period, comparison). Each is a complete
    follow-up question that the correction handling understands."""
    used = mem.get("last_used") or {}
    opts = []
    alt = _alt_measure(used, mem)
    if alt:
        opts.append(f"Show {alt} instead")
    parent = _parent_scope(mem.get("org_filter") or {}, user_id)
    if parent:
        opts.append(f"Show {parent} instead")
    opts.append("Use this year to date instead" if used.get("period_type") == "MONTH" else "Use last month instead")
    comps = used.get("comparisons") or []
    if used.get("tool") not in NO_COMPARISON_OPTION:
        if "PY" in comps and "Budget" in comps:
            opts.append("Compare with Budget only")
        elif comps == ["Budget"]:
            opts.append("Compare with last year instead")
        else:
            opts.append("Compare with Budget instead")
    return opts


def dispute_reply(mem: dict, user_id: str) -> tuple[str, list[str]]:
    """Answer to 'that's not right' / 'are you sure?': exactly what was used, and what can be changed."""
    u = mem["last_used"]
    period = u["period"] + (f" ({u['months']})" if u.get("months") else "")
    other = "Mexico" if "Canada" in u["scope"] else "Canada"
    msg = ("Here is exactly what I used for the previous answer:\n\n"
           f"- **Measure:** {u['measure']}\n"
           f"- **Scope:** {u['scope']}\n"
           f"- **Period:** {period}\n"
           f"- **Compared with:** {u['comparison_text']}\n"
           f"- **Source:** {u['source']}\n\n"
           "Every figure comes straight from the database; the SQL is under \"How I got this\" in the previous "
           f"answer. Which part should change? Pick one below, or type it, for example \"No, I meant {other}\" or "
           "\"use Q3 2026 instead\".")
    return msg, change_options(mem, user_id)


# ------------------------------------------------------------------------------------------
# Graph nodes
# ------------------------------------------------------------------------------------------
def node_preprocess(state: AgentState) -> AgentState:
    t0 = time.time()
    q = state["question"].strip()
    user = state["user_id"]
    as_of = date.fromisoformat(state["as_of"]) if state.get("as_of") else as_of_date()
    mem = state.get("memory") or {}
    res = resolve(q, dims().org, as_of)
    ref = ordinal_reference(q, res, mem)
    if ref:
        res.org_filter = ref
        res.intents = [i for i in res.intents if i != "rank"] or ["pnl"]
        res.level_hint, res.top_n, res.ascending = None, None, None
    follow = is_followup(q, res, mem) or bool(ref)
    mg = merge_context(res, mem, follow)
    # what the question named itself vs what the conversation already had (for the "Carried over" line)
    mg["asked"] = {"org": bool(res.org_filter) and not ref, "metric": bool(res.metric or wf_focus_from(res.clean_text)),
                   "period": bool(res.period), "versions": bool(res.versions or res.comparisons)}
    mg["had"] = {"metric": bool(mem.get("metric") or mem.get("ratio") or mem.get("wf_focus")),
                 "org": bool(mem.get("org_filter")) or bool(ref), "period": bool(mem.get("period")),
                 "versions": bool(mem.get("versions") or mem.get("comparisons"))}
    mg["question"] = res.clean_text or q          # without corrected-away phrases ("not YTD")
    if res.negated:
        mg["negated"] = list(res.negated)
    apply_ui_filters(mg, res, mem, state.get("ui_filters") or {}, follow, as_of)
    route, message, options = "plan", "", []
    if is_dispute(q, res, mem):
        route = "clarify"
        message, options = dispute_reply(mem, user)
        mg["options_mode"] = "question"           # each option is a complete follow-up question
    elif res.ambiguous:
        amb = res.ambiguous[0]
        route = "clarify"
        options = amb["options"]
        message = (f"'{amb['text']}' matches several businesses: " + ", ".join(amb["options"]) +
                   ". Which one do you mean?")
    else:
        org_f = mg["org_filter"] or default_org(user)
        decision = check_access(user, org_f)
        if decision.status in ("denied", "empty"):
            route, message = "refuse", decision.message or "No access."
    suggested = route_deterministic(mg)
    return {"merged": mg, "route": route, "message": message, "options": options, "suggested": suggested,
            "timings": {"preprocess": round(time.time() - t0, 3)}, "llm_calls": [], "errors": [],
            "attempts": 0, "outputs": [], "calls": []}


def ui_signature(ui: dict | None) -> str:
    return json.dumps(ui or {}, sort_keys=True, default=str)


def apply_ui_filters(mg: dict, res: Resolution, mem: dict, ui: dict, follow: bool, as_of: date) -> None:
    """Sidebar filters (scope, version, period) as the default context; records the source of each slot.

    Priority: the question's own words > the conversation (follow-ups) > the sidebar > the default scope.
    When the sidebar changed since the previous answer, it replaces what the conversation carried."""
    changed = bool(ui) and ui_signature(ui) != (mem.get("ui_sig") or ui_signature({}))
    src = {}
    ui_org = {k: list(v) for k, v in (ui.get("org_filter") or {}).items() if v}
    if res.org_filter:
        src["org"] = "question"
    elif ui_org and (changed or not follow or not mg.get("org_filter")):
        mg["org_filter"] = ui_org
        mg["org_from_sidebar"] = True
        src["org"] = "sidebar"
    else:
        src["org"] = "conversation" if mg.get("org_filter") else "default"
    ui_period = ui.get("period")
    if res.period:
        src["period"] = "question"
    elif ui_period and (changed or not follow or not mg.get("period")):
        mg["period"], mg["period_is_range"] = dict(ui_period), False
        src["period"] = "sidebar"
    else:
        src["period"] = "conversation" if mg.get("period") else "default"
    v = ui.get("version")
    if res.versions or res.comparisons or "landing" in res.intents:
        src["version"] = "question"
    elif v and v != "Actual" and (changed or not follow or not (mg.get("versions") or mg.get("comparisons"))):
        if v == "Landing":
            if "landing" not in mg["intents"] and not set(mg["intents"]) & {"catalog", "workforce", "cockpit"}:
                mg["intents"] = list(mg["intents"]) + ["landing"]
                if mg.get("period") and src.get("period") != "question":
                    mg["period"] = ti.Period("MONTH", ti.open_month(as_of)).to_dict()
        else:
            mg["versions"] = ["Actual", v]
        src["version"] = "sidebar"
    else:
        src["version"] = "conversation" if (mg.get("versions") or mg.get("comparisons")) and follow else "default"
    mg["sources"] = src
    mg["ui_sig"] = ui_signature(ui)


def node_plan(state: AgentState) -> AgentState:
    t0 = time.time()
    model = state.get("model") or env("LLM_MODEL", "ollama/qwen2.5-coder:14b")
    mg, suggested = state["merged"], state["suggested"]
    calls, source, llm_calls, errors = [], "router_fallback", list(state.get("llm_calls", [])), list(state.get("errors", []))
    if _use_llm(model):
        hint = f"{suggested['name']} {json.dumps(suggested['arguments'])}" if env("AGENT_SUGGEST_TOOL", "0") == "1" else "(choose yourself)"
        msgs = [{"role": "system", "content": PLANNER_SYSTEM.format(last_closed=ti.month_label(ti.last_closed_month()))},
                {"role": "user", "content": PLANNER_USER.format(
                    question=state["question"], resolved=json.dumps(_compact(mg)),
                    history=history_text(state.get("memory")), suggested=hint)}]
        try:
            r = llm.chat(msgs, tools=openai_tools(DATA_TOOLS), model=model)
            llm_calls.append({"step": "plan", "latency": round(r.latency, 2), "usage": r.usage,
                              "native_tool_call": r.native_tool_call, "raw_calls": r.tool_calls[:3]})
            calls = [c for c in r.tool_calls if c["name"] in DATA_TOOLS][:2]
            if calls:
                source = "llm" if r.native_tool_call else "llm_text"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"planner LLM error: {type(exc).__name__}: {str(exc)[:300]}")
    if calls and mg.get("followup") and mg.get("tool") and calls[0]["name"] != mg["tool"] \
            and suggested.get("name") == mg["tool"]:
        # "now for Canada": the same analysis as the previous turn on a new scope, so keep its tool
        calls, source = [suggested], source + "+router_followup"
    if not calls:
        calls = [suggested]
    intents = set(mg.get("intents") or [])
    landing_tools = ("get_landing", "get_ytd_with_landing", "rank_landing", "explain_landing")
    if "catalog" in intents and calls[0]["name"] != "describe_catalog":
        calls, source = [suggested], source + "+router_catalog"
    elif "landing" in intents and "catalog" not in intents and calls[0]["name"] not in landing_tools:
        calls, source = [suggested], source + "+router_landing"
    elif calls[0]["name"] in landing_tools and "landing" not in intents and suggested.get("name") not in landing_tools:
        # a landing tool needs landing wording ("landing", "land", "month-end", "outlook", "will ... miss budget");
        # "latest forecast for the full year" is a forecast question, not the landing
        calls, source = [suggested], source + "+router_not_landing"
    calls = respect_corrections(calls, mg, date.fromisoformat(state["as_of"]) if state.get("as_of") else as_of_date())
    timings = dict(state.get("timings", {}))
    timings["plan"] = round(time.time() - t0, 3)
    return {"calls": calls, "tool_choice_source": source, "llm_calls": llm_calls, "errors": errors,
            "timings": timings}


def respect_corrections(calls: list[dict], mg: dict, as_of: date) -> list[dict]:
    """The LLM sometimes copies the corrected-away value into its arguments (period "YTD" after "not YTD, full
    year 2025"). Drop such a period so the tool uses the resolved one, and swap a negated measure for the
    corrected measure."""
    neg = mg.get("negated") or []
    if not neg:
        return calls
    neg_periods, neg_measures = set(), set()
    for phrase in neg:
        p = ti.parse_period_text(phrase, as_of).period
        if p is not None:
            neg_periods.add((p.period_type, p.end_key))
        _kind, obj = registry().resolve(phrase)
        if obj is not None:
            neg_measures.add(obj.id)
    replacement = mg.get("ratio") or mg.get("metric")
    out = []
    for c in calls:
        args = dict(c.get("arguments") or {})
        per = args.get("period")
        if isinstance(per, str) and per.strip():
            p = ti.parse_period_text(per, as_of).period
            if p is not None and (p.period_type, p.end_key) in neg_periods:
                args["period"] = ""
        for key in ("metric", "metric_or_ratio", "ratio_name"):
            if args.get(key) in neg_measures and replacement and replacement not in neg_measures:
                args[key] = replacement
        out.append({**c, "arguments": args})
    return out


def node_act(state: AgentState) -> AgentState:
    t0 = time.time()
    as_of = date.fromisoformat(state["as_of"]) if state.get("as_of") else as_of_date()
    ctx = ToolContext(user_id=state["user_id"], as_of=as_of, question=state["merged"].get("question") or state["question"],
                      resolution=_resolution_from(state["merged"], state["question"]),
                      memory=state.get("memory") or {})
    outputs = [run_tool(c["name"], c.get("arguments") or {}, ctx) for c in state["calls"]]
    source = state.get("tool_choice_source", "")
    calls = list(state["calls"])
    if not any(o.ok for o in outputs) and source.startswith("llm") and not any(o.kind in ("refusal", "clarify") for o in outputs):
        sug = state["suggested"]
        outputs.append(run_tool(sug["name"], sug["arguments"], ctx))
        calls.append(sug)
        source = source + "+router_retry"
    timings = dict(state.get("timings", {}))
    timings["act"] = round(time.time() - t0, 3)
    return {"outputs": [o.model_dump() for o in outputs], "calls": calls, "tool_choice_source": source,
            "timings": timings}


def node_write(state: AgentState) -> AgentState:
    t0 = time.time()
    model = state.get("model") or env("LLM_MODEL", "ollama/qwen2.5-coder:14b")
    outs = [ToolOutput(**o) for o in state["outputs"] if o.get("ok")]
    llm_calls, errors = list(state.get("llm_calls", [])), list(state.get("errors", []))
    answer = ""
    if _use_llm(model) and outs:
        facts = "\n".join(f"- {f}" for o in outs for f in o.facts)
        notes = "\n".join(f"- {n}" for o in outs for n in o.notes) or "- none"
        msgs = [{"role": "system", "content": WRITER_SYSTEM},
                {"role": "user", "content": WRITER_USER.format(question=state["question"], facts=facts, notes=notes)}]
        if state.get("attempts", 0) > 0 and state.get("answer"):
            g = state.get("guard") or {}
            problems = g.get("problems") or [f"numbers that are not in FACTS: {', '.join(g.get('unsupported', []))}"]
            msgs += [{"role": "assistant", "content": state["answer"]},
                     {"role": "user", "content": WRITER_RETRY.format(problems="; ".join(problems))}]
        try:
            r = llm.chat(msgs, model=model, max_tokens=300)
            llm_calls.append({"step": f"write#{state.get('attempts', 0) + 1}", "latency": round(r.latency, 2),
                              "usage": r.usage})
            answer = clean_answer(r.content)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"writer LLM error: {type(exc).__name__}: {str(exc)[:300]}")
    timings = dict(state.get("timings", {}))
    timings[f"write#{state.get('attempts', 0) + 1}"] = round(time.time() - t0, 3)
    return {"answer": answer, "llm_calls": llm_calls, "errors": errors, "timings": timings}


def node_guard(state: AgentState) -> AgentState:
    outs = [ToolOutput(**o) for o in state["outputs"] if o.get("ok")]
    answer = state.get("answer") or ""
    attempts = state.get("attempts", 0)
    q = state["question"]
    g = (guardrails.check_answer(answer, outs, q) if answer
         else guardrails.GuardResult(False, ["<empty>"], problems=["the answer was empty"]))
    if answer and len(answer) < 40:
        g = guardrails.GuardResult(False, ["<too short>"], g.checked, problems=["the answer was too short"])
    history = list((state.get("guard") or {}).get("history", []))
    history.append({"attempt": attempts + 1, "ok": g.ok, "unsupported": g.unsupported, "checked": g.checked,
                    **({} if g.ok else {"problems": g.problems, "draft": answer[:700]})})
    if g.ok:
        text, dropped = guardrails.drop_ungrounded(answer, outs)
        return {"answer": text, "retry": False,
                "guard": {"ok": True, "template": False, "history": history, "unsupported": [], "dropped": dropped}}
    if attempts < 1 and answer and _use_llm(state.get("model") or env("LLM_MODEL", "")):
        return {"guard": {"ok": False, "template": False, "history": history, "unsupported": g.unsupported,
                          "problems": g.problems},
                "retry": True, "attempts": attempts + 1}
    # Last resort before the template: keep the LLM text minus the sentences with unsupported numbers.
    red = redact_sentences(answer, g.unsupported) if answer and outs else ""
    if red and len(red) >= 60 and guardrails.check_answer(red, outs, q).ok:
        red, dropped = guardrails.drop_ungrounded(red, outs)
        return {"answer": red, "retry": False,
                "guard": {"ok": True, "template": False, "redacted": True, "history": history,
                          "unsupported": g.unsupported, "dropped": dropped}}
    return {"answer": template_answer(outs) if outs else answer,
            "guard": {"ok": True, "template": True, "history": history, "unsupported": g.unsupported},
            "retry": False}


def redact_sentences(text: str, unsupported: list[str]) -> str:
    """Drop every sentence that contains one of the unsupported number tokens.

    Returns "" (use the template) when the first sentence would be dropped: the headline is gone and
    the remaining sentences refer back to it ("This improvement is driven by ...").
    """
    bad = [u.strip("()+-−, ") for u in unsupported if u and not u.startswith("<")]
    if not bad:
        return ""
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z*_])", text.strip())
    keep = [s for s in sents if not any(b and b in s for b in bad)]
    if not keep or keep[0] != sents[0]:
        return ""
    return " ".join(keep).strip()


def node_finalize(state: AgentState) -> AgentState:
    mg = state.get("merged") or {}
    user = state["user_id"]
    route = state.get("route", "plan")
    outs = [ToolOutput(**o) for o in state.get("outputs", [])]
    ok_outs = [o for o in outs if o.ok]
    primary = ok_outs[0] if ok_outs else None
    status = "ok"
    if route == "refuse":
        status, answer = "refusal", state.get("message", "")
    elif route == "clarify":
        status, answer = "clarification", state.get("message", "")
    elif not primary:
        bad = next((o for o in outs if not o.ok), None)
        if bad and bad.kind == "refusal":
            status, answer = "refusal", bad.error or "No access."
        elif bad and bad.kind == "clarify":
            status, answer = "clarification", bad.error or ""
        else:
            status = "error"
            answer = ("I could not compute that from the data model. " + (bad.error if bad and bad.error else "")
                      + " Try rephrasing with an org unit, a metric and a period.")
    else:
        answer = assemble_answer(state.get("answer") or template_answer(ok_outs), ok_outs)
    table_spec = build_table(primary.model_dump()) if primary else {}
    chart = chart_spec(primary.model_dump(), mg.get("intents")) if primary else {"type": "none"}
    filters = dict(primary.filters_used) if primary else {"org": org_label(mg.get("org_filter") or {})}
    notes = [n for o in ok_outs for n in o.notes]
    if notes:
        filters["notes"] = notes
    sql = [s for o in ok_outs for s in o.sql]
    followups = make_followups(primary, mg, user)
    new_mem = dict(state.get("memory") or {})
    if primary:
        args = primary.meta.get("args", {})
        wf = primary.tool == "get_workforce"         # its "metric" (attrition, hires) is not a P&L metric
        new_mem = {"org_filter": filters.get("org_filter") or mg.get("org_filter") or {},
                   "metric": mg.get("metric") or (None if wf else args.get("metric")) or args.get("metric_or_ratio"),
                   "ratio": mg.get("ratio") or args.get("ratio_name"),
                   "period": mg.get("period"), "period_is_range": mg.get("period_is_range", False),
                   "versions": mg.get("versions") or [], "comparisons": mg.get("comparisons") or [],
                   "intents": mg.get("intents") or [], "tool": primary.tool, "level_hint": mg.get("level_hint"),
                   "top_n": mg.get("top_n"), "ascending": mg.get("ascending"),
                   "both_margins": bool(mg.get("both_margins") or primary.kind == "ratio_pair")}
        if primary.kind in ("ranking", "landing_rank") and primary.data:
            lbl = primary.meta.get("level_label")
            new_mem.update({"entities": [str(r.get(lbl)) for r in primary.data][:25],
                            "entities_level": primary.meta.get("level"),
                            "entities_ascending": bool(primary.meta.get("ascending"))})
        elif primary.kind == "workforce":
            new_mem.update({"wf_group": primary.meta.get("group"), "wf_focus": primary.meta.get("focus")})
            if primary.meta.get("level") and primary.data:
                lbl = primary.meta.get("level_label")
                new_mem.update({"entities": [str(r.get(lbl)) for r in primary.data if r.get("_kind") != "subtotal"][:25],
                                "entities_level": primary.meta.get("level"),
                                "entities_ascending": bool(primary.meta.get("ascending"))})
        elif primary.kind == "drivers" and (primary.extra or {}).get("org") and primary.meta.get("org_level"):
            rows = primary.extra["org"]
            lbl = [k for k in rows[0] if k not in (primary.meta.get("current"), primary.meta.get("comparison"),
                                                   "Impact", "_fav")][0]
            new_mem.update({"entities": [str(r.get(lbl)) for r in rows][:25],
                            "entities_level": primary.meta.get("org_level"), "entities_ascending": False})
    new_mem["ui_sig"] = mg.get("ui_sig") or ui_signature(state.get("ui_filters") or {})
    if mg.get("sources"):
        filters["applied"] = applied_filters(mg, filters)
    if primary and status == "ok":
        used = used_record(primary, mg, filters)
        carried = carried_labels(used, mg)
        if carried:
            filters["carried_over"] = carried
        history = list((state.get("memory") or {}).get("history") or [])[-4:]
        new_mem["history"] = history + [{"q": state["question"], "used": used["text"]}]
        new_mem["last_used"] = used
    timings = dict(state.get("timings", {}))
    diag = {"tool_calls": state.get("calls", []), "tool_choice_source": state.get("tool_choice_source", "none"),
            "suggested": state.get("suggested"), "guardrail": state.get("guard"), "llm_calls": state.get("llm_calls", []),
            "errors": state.get("errors", []) + [o.error for o in outs if o.error],
            "options_mode": mg.get("options_mode"), "negated": mg.get("negated", []),
            "model": state.get("model"), "timings": timings, "resolved": _compact(mg) if mg else {},
            "followup": mg.get("followup", False), "options": state.get("options", []),
            "facts": [f for o in ok_outs for f in o.facts],
            "evidence": {"extra": primary.extra if primary else {},
                         "totals": {k: v for k, v in (primary.meta if primary else {}).items() if k.startswith("total")}}}
    final = FinalAnswer(answer_markdown=answer, table=primary.data if primary else [], table_spec=table_spec,
                        chart_spec=ChartSpec(**chart), filters_used=filters, sql_used=sql, followups=followups,
                        status=status, diagnostics=diag)
    return {"final": final.model_dump(), "new_memory": new_mem}


SOURCE_TEXT = {"question": "from your question", "conversation": "carried over from the conversation",
               "sidebar": "from the sidebar filters", "default": "default"}


def applied_filters(mg: dict, filters: dict) -> list[str]:
    """Human-readable list of the filters an answer used and where each came from."""
    src = mg.get("sources") or {}
    out = []
    org = filters.get("org") or org_label(mg.get("org_filter") or {})
    out.append(f"Scope: {org} ({SOURCE_TEXT.get(src.get('org', 'default'), 'default')})")
    period = filters.get("period") or (mg.get("period") or {}).get("label") or ""
    if period and period != "catalog":
        out.append(f"Period: {period} ({SOURCE_TEXT.get(src.get('period', 'default'), 'default')})")
    vers = [str(v).split(" (")[0] for v in (filters.get("versions") or [])]
    if vers:
        out.append(f"Versions: {', '.join(dict.fromkeys(vers))} ({SOURCE_TEXT.get(src.get('version', 'default'), 'default')})")
    return out


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("preprocess", node_preprocess)
    g.add_node("plan", node_plan)
    g.add_node("act", node_act)
    g.add_node("write", node_write)
    g.add_node("guard", node_guard)
    g.add_node("finalize", node_finalize)
    g.add_edge(START, "preprocess")
    g.add_conditional_edges("preprocess", lambda s: "plan" if s["route"] == "plan" else "finalize",
                            {"plan": "plan", "finalize": "finalize"})
    g.add_edge("plan", "act")
    g.add_conditional_edges("act", lambda s: "write" if any(o.get("ok") for o in s["outputs"]) else "finalize",
                            {"write": "write", "finalize": "finalize"})
    g.add_edge("write", "guard")
    g.add_conditional_edges("guard", lambda s: "write" if s.get("retry") else "finalize",
                            {"write": "write", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile()


_GRAPH = None


def ask(question: str, user_id: str = "group_cfo", memory: dict | None = None, model: str | None = None,
        as_of: date | None = None, ui_filters: dict | None = None) -> tuple[FinalAnswer, dict]:
    """Run the agent for one question. Returns (validated answer, new conversation memory).

    `ui_filters` = the sidebar's default context: {"org_filter": {level: [values]}, "version": "Budget",
    "period": {"type": "YTD", "end": 202610, ...}}. Words in the question always win."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    t0 = time.time()
    state = _GRAPH.invoke({"question": question, "user_id": user_id, "memory": memory or {},
                           "model": model or env("LLM_MODEL", "ollama/qwen2.5-coder:14b"),
                           "as_of": (as_of or as_of_date()).isoformat(), "ui_filters": ui_filters or {}})
    final = FinalAnswer(**state["final"])
    final.diagnostics["latency_s"] = round(time.time() - t0, 2)
    return final, state.get("new_memory") or {}
