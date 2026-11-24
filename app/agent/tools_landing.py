"""Tools for the Data Catalog, the current-month landing and the two operating margins.

Every number comes from app.landing (deterministic engine output stored by `make landing`) or the semantic
layer; tools return pre-formatted facts, a table spec and a chart spec. All reads run under the user's
row-level security.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator

from app.ui import branding as B
from app.agent.tools import (CUR, ToolContext, ToolOutput, _as_int, _as_list, _ok, _records, _refusal, _val,
                             cmp_phrase, norm_versions, resolve_org, resolve_period)
from app.landing import engine as E
from app.landing.query import (DATA_NOTE, HEADLINE, WIP_NOTE, LandingQuery, accuracy_note, in_scope,
                               measure_label, measure_target)
from app.semantic import catalog as C
from app.semantic import time_intel as ti
from app.semantic.entity_resolver import LEVEL_LABEL, ORG_LEVELS, org_label
from app.semantic.query_builder import NA_DENOMINATOR_NOTE
from app.semantic.registry import registry
from app.viz import format as F

LANDING_TOOLS = ("get_landing", "get_ytd_with_landing", "explain_landing", "rank_landing")
MARGINS = ("maop_margin_revenue", "maop_margin_production")
# Shown under every get_ratio answer that returns both margins, so LLM answers say why as well.
MARGIN_PAIR_NOTE = "No margin base was named, so both operating margins are shown."
LEVEL_WORDS = {"bu": "l6_bu", "bus": "l6_bu", "business unit": "l6_bu", "business units": "l6_bu",
               "business": "l5_business", "businesses": "l5_business", "product line": "l4_product_line",
               "product lines": "l4_product_line", "country": "l3_country", "countries": "l3_country",
               "region": "l2_region", "regions": "l2_region"}


# ------------------------------------------------------------------------------------------
# Arguments
# ------------------------------------------------------------------------------------------
class DescribeCatalogArgs(BaseModel):
    kind: str = Field("capabilities", description="regions, countries, product_lines, businesses, business_units, "
                                                  "accounts, metrics, ratios, versions, periods, billing_patterns, "
                                                  "capabilities or example_questions")
    parent_filter: str = Field("", description="Optional org to list within, e.g. 'Canada' (businesses in Canada)")


class GetLandingArgs(BaseModel):
    org: str = Field("", description="Org in plain words, e.g. 'United States'. Empty = user's default scope")
    measures: list[str] = Field(default_factory=list, description="Optional: billing, revenue, production, operating "
                                                                  "profit, profit % (both margins). Empty = all")
    month: str = Field("", description="Optional month; empty = the open month (the landing month)")

    @field_validator("measures", mode="before")
    @classmethod
    def coerce_measures(cls, v):
        return _as_list(v)


class GetYtdWithLandingArgs(BaseModel):
    metric_or_ratio: str = Field("revenue", description="Metric or ratio, e.g. 'revenue', 'operating profit', "
                                                       "'MAOP margin' / 'profit %' (both margins)")
    org: str = Field("", description="Org in plain words")
    through_month: str = Field("", description="Last month, normally the landing month (empty = landing month)")
    period_type: str = Field("YTD", description="YTD, QTD or FY (full-year outlook = actuals + landing + latest forecast)")
    comparisons: list[str] = Field(default_factory=lambda: ["PY", "Budget", "LatestFC"],
                                   description="PY, Budget, LatestFC")

    @field_validator("comparisons", mode="before")
    @classmethod
    def coerce_cmp(cls, v):
        return _as_list(v) or ["PY", "Budget", "LatestFC"]


class ExplainLandingArgs(BaseModel):
    org: str = Field("", description="Org in plain words (a BU gives the method-by-method detail)")


class RankLandingArgs(BaseModel):
    metric: str = Field("billing", description="billing, revenue, operating profit or a margin")
    org_level: str = Field("l6_bu", description="l2_region, l3_country, l4_product_line, l5_business or l6_bu")
    parent_filter: str = Field("", description="Org to rank within, e.g. 'United States'")
    top_n: int = Field(10, description="Number of entities, 0 = all")
    sort_by: str = Field("gap_vs_budget", description="gap_vs_budget, gap_vs_forecast or landing")

    @field_validator("top_n", mode="before")
    @classmethod
    def coerce_top(cls, v):
        return _as_int(v, 10)


# ------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------
def _fmt(kind: str, obj) -> str:
    return obj.fmt if kind == "ratio" else ("num" if obj.kind == "stat" else "eur")


def _rng(lo, hi, fmt) -> str:
    if not (_ok(lo) and _ok(hi)):
        return "range not available"
    return f"P10-P90 {_val(lo, fmt)} - {_val(hi, fmt)}"


def _diff(a, b, fmt):
    if not (_ok(a) and _ok(b)):
        return None, None
    d = a - b
    rel = (d / abs(b)) if (fmt != "pct" and b) else None
    return d, rel


def _fav(diff, favorable: str):
    return ti.is_favorable(diff, favorable)


def _measures_for(ctx: ToolContext, requested: list[str]) -> tuple[list[str], bool]:
    """Landing measures named in the args or the question; generic margin wording means both margins."""
    reg = registry()
    out, both = [], bool(ctx.resolution and ctx.resolution.both_margins)
    for m in requested:
        if reg.pair_for(m):
            both = True
            continue
        kind, obj = reg.resolve(m)
        if obj is not None and obj.id not in out and in_scope(kind, obj):
            out.append(obj.id)
    if ctx.resolution and ctx.resolution.metric and not out:
        kind, obj = reg.resolve(ctx.resolution.metric)
        if obj is not None and in_scope(kind, obj):
            out.append(obj.id)
    if both:
        out = [m for m in out if m not in MARGINS] + list(MARGINS)
    return out, both


def _no_landing(tool: str, q: LandingQuery) -> ToolOutput:
    return _refusal(tool, f"No landing has been computed yet for {ti.month_label(q.month)}. "
                          "Run `make landing` to compute it.", "error")


def _cmp_cols(q: LandingQuery, org, months: list[int], wanted: list[str]) -> list[tuple[str, pd.DataFrame]]:
    out = []
    for c in wanted:
        r = q.comparison_wide(org, c, months)
        if r is not None:
            out.append(r)
    return out


def _table(columns, rows, col_fmt, caption, row_fmt=None, fav_cols=None) -> dict:
    row_meta = []
    for r in rows:
        fav = {c: r.get(f"_fav_{c}") for c in (fav_cols or [])}
        row_meta.append({"kind": r.get("_kind", "line"), "level": 0, "fmt": (row_fmt or {}).get(r.get("_key")) or
                         r.get("_fmt"), "fav": fav})
    return {"columns": columns, "rows": rows, "col_fmt": col_fmt, "row_meta": row_meta, "caption": caption,
            "extra_tables": []}


def _month_series(q: LandingQuery, org, kind, obj, months: list[int], version: str) -> dict[int, float]:
    out = {}
    if not months:
        return out
    s = ti.Series(version, version, ti.Period("RANGE", months[-1], months[0]), tuple(months))
    w = q.sl.frame([s], org, ["month_key"]).set_index("month_key")
    for k in months:
        if k in w.index:
            out[k] = float(np.asarray(q.sl.value(w.loc[[k]], kind, obj)).ravel()[0])
    return out


# ------------------------------------------------------------------------------------------
# describe_catalog
# ------------------------------------------------------------------------------------------
def tool_describe_catalog(args: DescribeCatalogArgs, ctx: ToolContext) -> ToolOutput:
    kind = (args.kind or "").strip().lower().replace(" ", "_")
    if kind not in C.KINDS:
        kind = C.kind_from_text(args.kind or ctx.question)
    parent = {}
    if args.parent_filter and args.parent_filter.strip():
        filt, refusal, _ = resolve_org(ctx, args.parent_filter, "describe_catalog")
        if refusal:
            return refusal
        parent = filt or {}
    elif ctx.resolution and ctx.resolution.org_filter and kind in ("countries", "product_lines", "businesses",
                                                                    "business_units", "regions"):
        parent = {k: v for k, v in ctx.resolution.org_filter.items() if k != "l1_group"}
    res = C.describe(kind, ctx.user_id, parent, ctx.as_of, engine=ctx.sl.engine)
    df = res.df
    facts = [res.description]
    if not df.empty:
        first = df.columns[0]
        items = [str(v) for v in df[first].tolist()]
        facts.append(f"{res.title} ({len(items)}): " + "; ".join(items[:25]) + (" ..." if len(items) > 25 else "") + ".")
    facts.append("The Data Catalog page has the full, live list with definitions.")
    col_fmt = {c: "int" for c in df.columns if pd.api.types.is_integer_dtype(df[c])}
    table = _table(list(df.columns), _records(df), col_fmt,
                   f"{res.title} in your scope (live from the database, row-level security applied). "
                   "See the Data Catalog page for details.")
    meta = {"table_spec": table, "chart_spec": res.chart or {"type": "none"}, "followups": res.followups,
            "catalog_kind": kind, "name": res.title}
    return ToolOutput(tool="describe_catalog", kind="catalog", data=_records(df), facts=facts,
                      filters_used={"org": org_label(parent) if parent else "your scope", "period": "catalog",
                                    "org_filter": parent, "as_of_date": ctx.as_of.isoformat(), "currency": CUR,
                                    "source": "data catalog (database + metrics.yaml)"},
                      notes=[], meta=meta, bullets=[])


# ------------------------------------------------------------------------------------------
# get_landing
# ------------------------------------------------------------------------------------------
def tool_get_landing(args: GetLandingArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "get_landing")
    if refusal:
        return refusal
    q = LandingQuery(ctx.sl)
    open_key = ti.open_month(ctx.as_of)
    month = open_key
    if args.month and args.month.strip():
        p = ti.parse_period_text(args.month, ctx.as_of).period
        if p is not None:
            month = p.end_key
            if p.period_type == "MONTH" and not re.search(r"20\d\d", args.month):
                month = ti.mk(open_key // 100, p.end_key % 100)
    elif ctx.resolution and ctx.resolution.period and ctx.resolution.period.get("type") == "MONTH":
        month = ctx.resolution.period["end"]
    measures, both = _measures_for(ctx, args.measures)
    if month != open_key:
        return _closed_or_future(ctx, q, filt, month, open_key, measures, notes)
    if not q.available:
        return _no_landing("get_landing", q)
    w50, wD, info = q.landing_wide(filt)
    if info["n_bus"] == 0:
        return _refusal("get_landing", "No business units in your scope match this request.", "refusal")
    show = list(dict.fromkeys([*HEADLINE, *[m for m in measures if m not in HEADLINE]]))
    focus = measures[0] if measures else "billing"
    month_l = ti.month_label(month)
    cmps = _cmp_cols(q, filt, [month], ["Budget", "LatestFC", "PY"])
    last_closed = ti.add_months(month, -1)
    last_w = q.actual_wide(filt, "Actual", [last_closed])
    rows, facts = [], []
    scope = org_label(filt)
    facts.append(f"Landing for {scope}, {month_l} (open month; as of {ctx.as_of.isoformat()}, computed "
                 f"{q.snap.snapshot_date.isoformat()}): P50 is the expected month-end, P10-P90 the range.")
    for mid in show:
        kind, obj = measure_target(mid)
        fmt = _fmt(kind, obj)
        p50, lo, hi = q.value_and_range(kind, obj, w50, wD)
        row = {"Measure": obj.name, "_key": mid, "_fmt": fmt, "Landing (P50)": p50, "P10": lo, "P90": hi}
        parts = [f"{obj.name}: P50 {_val(p50, fmt)} ({_rng(lo, hi, fmt)})"]
        for lab, cw in cmps:
            ref = float(np.asarray(q.sl.value(cw, kind, obj)).ravel()[0])
            d, rel = _diff(p50, ref, fmt)
            row[lab] = ref
            row[f"vs {lab}"] = d
            row[f"_fav_vs {lab}"] = _fav(d, obj.favorable)
            parts.append(cmp_phrase(d, ref, f"{lab} {month_l}" if lab != "PY" else f"PY ({ti.month_label(ti.add_months(month, -12))})",
                                    fmt, _fav(d, obj.favorable), getattr(obj, "is_cost", False), rel))
        lc = float(np.asarray(q.sl.value(last_w, kind, obj)).ravel()[0])
        row[f"Actual {ti.month_label(last_closed)}"] = lc
        rows.append(row)
        facts.append("; ".join(parts) + ".")
    if both:
        facts.append("No margin base was named, so both operating margins are shown: on revenue and on production.")
    facts.append(WIP_NOTE)
    facts.append(DATA_NOTE)
    acc = accuracy_note(ctx.sl.engine)
    if acc:
        facts.append(acc)
    if any(not _ok(r["Landing (P50)"]) for r in rows):
        notes.append(NA_DENOMINATOR_NOTE)
    cmp_labels = [lab for lab, _ in cmps]
    columns = ["Measure", "Landing (P50)", "P10", "P90"] + [c for lab in cmp_labels for c in (lab, f"vs {lab}")] + \
        [f"Actual {ti.month_label(last_closed)}"]
    col_fmt = {c: "eur" for c in columns if c != "Measure"}
    table = _table(columns, rows, col_fmt,
                   f"Landing = expected month-end of {month_l}. {WIP_NOTE} Margins in %, variances in pp. "
                   "Green / red = favourable / unfavourable vs the comparison.",
                   fav_cols=[f"vs {lab}" for lab in cmp_labels])
    compare_q = bool(re.search(r"\b(vs\.?|versus|against|compare[sd]?|comparison|budget|forecast|fc[123]|last year|"
                               r"prior year|py|beat|miss|plan)\b", ctx.question or "", re.I))
    chart = (landing_bars_chart(rows, focus, month_l, scope, cmp_labels, f"Actual {ti.month_label(last_closed)}")
             if compare_q else landing_trend_chart(q, filt, focus, month, w50, wD, scope))
    out = ToolOutput(tool="get_landing", kind="landing", data=_strip(rows), facts=facts,
                     filters_used=_filters(ctx, q, filt, month_l, f"{month_l} (landing, open month)"),
                     notes=_landing_notes(ctx, notes),
                     meta={"table_spec": table, "chart_spec": chart, "focus": focus, "both_margins": both,
                           "landing_month": month, "snapshot": q.snap.snapshot_date.isoformat(), "name": "Landing",
                           "followups": [f"Which BUs in {scope} are expected to miss budget this month?",
                                         f"What will YTD operating margin be through {ti.MONTH_NAMES[month % 100 - 1]} "
                                         f"including the landing for {scope}?",
                                         f"Explain the landing for {scope}"]})
    return out


def _landing_notes(ctx: ToolContext, notes: list[str]) -> list[str]:
    """Every landing answer: the WIP rule, monthly data only, and the measured backtest accuracy."""
    acc = accuracy_note(ctx.sl.engine)
    return list(dict.fromkeys([f"{WIP_NOTE} {DATA_NOTE}"] + ([acc] if acc else []) + notes))


def _strip(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("_") or k.startswith("_fav")} for r in rows]


def _filters(ctx, q: LandingQuery, filt, period_label: str, months: str) -> dict:
    d = ctx.sl._filters(filt, None)
    d.update({"period": period_label, "months": months, "versions": ["Landing (P50, P10-P90)"],
              "landing_snapshot": q.snap.snapshot_date.isoformat() if q.snap else None,
              "landing_month": ti.month_label(q.month), "source": "landing engine (monthly history; WIP = 0)"})
    d["sql"] = None
    return d


def _closed_or_future(ctx, q: LandingQuery, filt, month: int, open_key: int, measures, notes) -> ToolOutput:
    month_l = ti.month_label(month)
    show = list(dict.fromkeys([*HEADLINE, *[m for m in measures if m not in HEADLINE]]))
    scope = org_label(filt)
    if month < open_key:
        w = q.actual_wide(filt, "Actual", [month])
        rows, facts = [], [f"{month_l} is a closed month, so there is no landing: these are the actuals for {scope}."]
        for mid in show:
            kind, obj = measure_target(mid)
            fmt = _fmt(kind, obj)
            v = float(np.asarray(ctx.sl.value(w, kind, obj)).ravel()[0])
            rows.append({"Measure": obj.name, "_key": mid, "_fmt": fmt, f"Actual {month_l}": v})
            facts.append(f"{obj.name} actual {month_l}: {_val(v, fmt)}.")
        cols = ["Measure", f"Actual {month_l}"]
        table = _table(cols, rows, {cols[1]: "eur"}, f"{month_l} is closed: actuals, not a landing.")
        return ToolOutput(tool="get_landing", kind="landing", data=_strip(rows), facts=facts,
                          filters_used={**ctx.sl._filters(filt, ti.Period("MONTH", month)), "versions": ["Actual"]},
                          notes=notes + [f"The landing exists for {ti.month_label(open_key)} only (the open month)."],
                          meta={"table_spec": table, "chart_spec": {"type": "none"}, "name": "Actuals",
                                "followups": [f"What's the {ti.MONTH_NAMES[open_key % 100 - 1]} landing for {scope}?",
                                              f"How is {scope} doing YTD vs budget?",
                                              f"Why did operating profit change vs last year for {scope}?"]})
    fc = ti.latest_forecast(month // 100, ctx.as_of) or "Budget"
    w = q.actual_wide(filt, fc, [month])
    rows, facts = [], [f"{month_l} is in the future: a landing exists only for the open month "
                       f"({ti.month_label(open_key)}). The latest forecast ({fc}) for {month_l} is shown instead."]
    for mid in show:
        kind, obj = measure_target(mid)
        fmt = _fmt(kind, obj)
        v = float(np.asarray(ctx.sl.value(w, kind, obj)).ravel()[0])
        rows.append({"Measure": obj.name, "_key": mid, "_fmt": fmt, f"{fc} {month_l}": v})
        facts.append(f"{obj.name} {fc} {month_l}: {_val(v, fmt)}.")
    cols = ["Measure", f"{fc} {month_l}"]
    table = _table(cols, rows, {cols[1]: "eur"}, f"{month_l} is in the future: latest forecast, not a landing.")
    return ToolOutput(tool="get_landing", kind="landing", data=_strip(rows), facts=facts,
                      filters_used={**ctx.sl._filters(filt, ti.Period("MONTH", month)), "versions": [fc]},
                      notes=notes, meta={"table_spec": table, "chart_spec": {"type": "none"}, "name": "Forecast",
                                         "followups": [f"What's the {ti.MONTH_NAMES[open_key % 100 - 1]} landing for {scope}?",
                                                       f"What is the full-year outlook for {scope}?",
                                                       f"Compare budget, FC2 and FC3 for {scope}"]})


def landing_bars_chart(rows: list[dict], focus: str, month_l: str, scope: str, cmp_labels: list[str],
                       last_col: str) -> dict:
    """Bars: the landing P50 (with its P10-P90 bar) next to Budget, the latest forecast, PY and the last closed
    month, for the measure the question is about."""
    row = next((r for r in rows if r.get("_key") == focus), rows[0])
    fmt = row.get("_fmt", "eur")
    data = [{"label": "Landing (P50)", "value": row["Landing (P50)"], "lo": row.get("P10"), "hi": row.get("P90"),
             "kind": "landing"}]
    for lab in cmp_labels:
        data.append({"label": lab, "value": row.get(lab), "kind": lab})
    data.append({"label": last_col, "value": row.get(last_col), "kind": "actual"})
    return {"type": "landing_bars", "title": f"{row['Measure']} {month_l}: landing vs plan and last year - {scope}",
            "fmt": fmt, "x": "label", "y": ["value"], "data": data, "meta": {}}


def landing_trend_chart(q: LandingQuery, filt, focus: str, month: int, w50, wD, scope: str) -> dict:
    """Current-year monthly actuals, the landing point with its P10-P90 bar, PY and Budget lines."""
    kind, obj = measure_target(focus)
    fmt = _fmt(kind, obj)
    y = month // 100
    months = ti.month_range(ti.mk(y, 1), ti.add_months(month, -1))
    act = _month_series(q, filt, kind, obj, months, "Actual")
    bud = _month_series(q, filt, kind, obj, months + [month], "Budget")
    py = _month_series(q, filt, kind, obj, [ti.add_months(k, -12) for k in months + [month]], "Actual")
    p50, lo, hi = q.value_and_range(kind, obj, w50, wD)
    rows = []
    for k in months + [month]:
        r = {"Month": ti.month_label(k), "PY": py.get(ti.add_months(k, -12)), "Budget": bud.get(k)}
        if k == month:
            r.update({"Landing": p50, "P10": lo, "P90": hi})
        else:
            r["Actual"] = act.get(k)
        rows.append(r)
    return {"type": "landing_trend", "title": f"{obj.name} {y}: actuals, {ti.month_label(month)} landing (P10-P90), "
                                              f"PY and Budget - {scope}",
            "fmt": fmt, "x": "Month", "y": ["Actual", "Landing", "PY", "Budget"], "data": rows, "meta": {}}


# ------------------------------------------------------------------------------------------
# get_ytd_with_landing
# ------------------------------------------------------------------------------------------
def tool_get_ytd_with_landing(args: GetYtdWithLandingArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "get_ytd_with_landing")
    if refusal:
        return refusal
    q = LandingQuery(ctx.sl)
    if not q.available:
        return _no_landing("get_ytd_with_landing", q)
    reg = registry()
    month = q.month
    ptype = (args.period_type or "YTD").strip().upper()
    qtext = (ctx.question or "").lower()
    if re.search(r"\b(full[- ]year|fy|year[- ]end|outlook)\b", qtext) or ptype in ("FY", "FULL_YEAR", "OUTLOOK"):
        ptype = "FY"
    elif re.search(r"\b(qtd|quarter[- ]to[- ]date)\b", qtext) or ptype == "QTD":
        ptype = "QTD"
    else:
        ptype = "YTD"
    y, mo = ti.ym(month)
    start = ti.mk(y, 1) if ptype in ("YTD", "FY") else ti.mk(y, (mo - 1) // 3 * 3 + 1)
    closed = ti.month_range(start, ti.add_months(month, -1)) if start <= ti.add_months(month, -1) else []
    after = ti.month_range(ti.add_months(month, 1), ti.mk(y, 12)) if ptype == "FY" and mo < 12 else []
    all_months = closed + [month] + after
    pair = reg.pair_for(args.metric_or_ratio) or (reg.pairs.get("operating_margins")
                                                  if ctx.resolution and ctx.resolution.both_margins else None)
    if pair is not None:
        targets = list(pair.members)
    else:
        kind, obj = reg.resolve(args.metric_or_ratio or (ctx.resolution.metric if ctx.resolution else None) or "revenue")
        if obj is None:
            return _refusal("get_ytd_with_landing", f"Unknown metric {args.metric_or_ratio!r}.", "error")
        if kind == "ratio" and obj.id in MARGINS and ctx.resolution and ctx.resolution.both_margins:
            targets = list(MARGINS)
        else:
            targets = [obj.id]
    for t in targets:
        kind, obj = reg.resolve(t)
        if not in_scope(kind, obj):
            return _refusal("get_ytd_with_landing", f"{obj.name} is outside the landing scope (billing to operating "
                                                    "profit and both operating margins).", "error")
    w50, wD, info = q.landing_wide(filt)
    if info["n_bus"] == 0:
        return _refusal("get_ytd_with_landing", "No business units in your scope match this request.", "refusal")
    base = q.actual_wide(filt, "Actual", closed)
    fc = ti.latest_forecast(y, ctx.as_of) or "Budget"
    if after:
        base_after = q.actual_wide(filt, fc, after)
        cols = [c for c in base.columns if c in base_after.columns]
        base = base[cols] + base_after[cols].iloc[0]
    label = {"YTD": f"YTD {ti.MONTH_NAMES[mo - 1]} {y} incl. landing",
             "QTD": f"QTD {ti.MONTH_NAMES[mo - 1]} {y} incl. landing",
             "FY": f"FY {y} outlook (actuals + landing + {fc})"}[ptype]
    cmps = _cmp_cols(q, filt, all_months, [c for c in norm_versions(args.comparisons) or ["PY", "Budget", "LatestFC"]
                                           if c in ("PY", "Budget", "LatestFC", "FC1", "FC2", "FC3")])
    last_closed_lbl = f"{ptype if ptype != 'FY' else 'YTD'} to {ti.month_label(ti.add_months(month, -1))} (Actual)"
    rows, facts = [], []
    scope = org_label(filt)
    facts.append(f"{label} for {scope}: closed months {ti.month_label(closed[0]) if closed else '-'} to "
                 f"{ti.month_label(closed[-1]) if closed else '-'} are actuals, {ti.month_label(month)} is the landing "
                 f"(P50, computed {q.snap.snapshot_date.isoformat()})" + (f", {ti.month_label(after[0])}"
                 f"{'-' + ti.month_label(after[-1]) if len(after) > 1 else ''} from {fc}" if after else "") + ".")
    for t in targets:
        kind, obj = reg.resolve(t)
        fmt = _fmt(kind, obj)
        p50, lo, hi = q.value_and_range(kind, obj, w50, wD, base=base)
        closed_v = float(np.asarray(ctx.sl.value(base, kind, obj)).ravel()[0]) if closed else None
        land_v = float(np.asarray(ctx.sl.value(w50, kind, obj)).ravel()[0])
        row = {"Measure": obj.name, "_key": t, "_fmt": fmt, label: p50, "P10": lo, "P90": hi,
               last_closed_lbl: closed_v if ptype != "FY" else float(np.asarray(ctx.sl.value(
                   q.actual_wide(filt, "Actual", closed), kind, obj)).ravel()[0]) if closed else None,
               f"{ti.month_label(month)} landing (P50)": land_v}
        parts = [f"{obj.name} {label}: {_val(p50, fmt)} ({_rng(lo, hi, fmt)})"]
        for lab, cw in cmps:
            ref = float(np.asarray(ctx.sl.value(cw, kind, obj)).ravel()[0])
            d, rel = _diff(p50, ref, fmt)
            row[lab] = ref
            row[f"vs {lab}"] = d
            row[f"_fav_vs {lab}"] = _fav(d, obj.favorable)
            lab_txt = (f"PY (FY {y - 1})" if ptype == "FY" else f"PY ({ptype} {ti.MONTH_NAMES[mo - 1]} {y - 1})") \
                if lab == "PY" else f"{lab} (same months)"
            parts.append(cmp_phrase(d, ref, lab_txt, fmt, _fav(d, obj.favorable), getattr(obj, "is_cost", False), rel))
        rows.append(row)
        facts.append("; ".join(parts) + ".")
    if len(targets) == 2 and pair is not None or (len(targets) == 2 and ctx.resolution and ctx.resolution.both_margins):
        facts.append("No margin base was named, so both operating margins are shown: on revenue and on production. "
                     "Aggregates are ratios of sums.")
    facts.append(WIP_NOTE)
    acc = accuracy_note(ctx.sl.engine)
    if acc:
        facts.append(acc)
    cmp_labels = [lab for lab, _ in cmps]
    columns = ["Measure", label, "P10", "P90", last_closed_lbl, f"{ti.month_label(month)} landing (P50)"] + \
        [c for lab in cmp_labels for c in (lab, f"vs {lab}")]
    col_fmt = {c: "eur" for c in columns if c != "Measure"}
    table = _table(columns, rows, col_fmt,
                   f"{label}: closed-month actuals plus the {ti.month_label(month)} landing (P50, P10-P90). "
                   f"{WIP_NOTE} Margins in %, variances in pp.", fav_cols=[f"vs {lab}" for lab in cmp_labels])
    chart = ytd_chart(q, filt, targets[0], closed, month, after, fc, w50, wD, scope, label)
    if any(not _ok(r[label]) for r in rows):
        notes.append(NA_DENOMINATOR_NOTE)
    return ToolOutput(tool="get_ytd_with_landing", kind="landing_ytd", data=_strip(rows), facts=facts,
                      filters_used=_filters(ctx, q, filt, label, f"{ti.month_label(all_months[0])} - "
                                                                 f"{ti.month_label(all_months[-1])}"),
                      notes=_landing_notes(ctx, notes),
                      meta={"table_spec": table, "chart_spec": chart, "targets": targets, "period_type": ptype,
                            "name": label, "landing_month": month,
                            "followups": [f"What's the {ti.MONTH_NAMES[mo - 1]} landing for {scope}?",
                                          f"Which BUs in {scope} are expected to miss budget this month?",
                                          f"What is the full-year outlook for {scope}?" if ptype != "FY" else
                                          f"Revenue YTD till {ti.MONTH_NAMES[mo - 1]} with landing vs budget for {scope}"]})


def ytd_chart(q: LandingQuery, filt, target: str, closed, month, after, fc, w50, wD, scope, label) -> dict:
    """Monthly bars: actuals, the landing month lighter / hatched (with P10-P90), forecast months outlined."""
    kind, obj = registry().resolve(target)
    fmt = _fmt(kind, obj)
    act = _month_series(q, filt, kind, obj, closed, "Actual")
    fcs = _month_series(q, filt, kind, obj, after, fc) if after else {}
    bud = _month_series(q, filt, kind, obj, closed + [month] + after, "Budget")
    p50, lo, hi = q.value_and_range(kind, obj, w50, wD)
    rows = [{"Month": ti.month_label(k), "value": act.get(k), "kind": "actual", "Budget": bud.get(k)} for k in closed]
    rows.append({"Month": ti.month_label(month), "value": p50, "kind": "landing", "lo": lo, "hi": hi,
                 "Budget": bud.get(month)})
    rows += [{"Month": ti.month_label(k), "value": fcs.get(k), "kind": "forecast", "Budget": bud.get(k)} for k in after]
    return {"type": "ytd_bars", "title": f"{obj.name} by month: {label} - {scope}", "fmt": fmt, "x": "Month",
            "y": ["value"], "data": rows, "meta": {"forecast": fc}}


# ------------------------------------------------------------------------------------------
# rank_landing
# ------------------------------------------------------------------------------------------
def tool_rank_landing(args: RankLandingArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.parent_filter, "rank_landing")
    if refusal:
        return refusal
    q = LandingQuery(ctx.sl)
    if not q.available:
        return _no_landing("rank_landing", q)
    reg = registry()
    lvl = (args.org_level or "l6_bu").strip().lower()
    lvl = lvl if lvl in ORG_LEVELS else LEVEL_WORDS.get(lvl, LEVEL_WORDS.get(lvl.rstrip("s"), "l6_bu"))
    if ctx.resolution and ctx.resolution.level_hint and not args.org_level.strip().startswith("l"):
        lvl = ctx.resolution.level_hint
    kind, obj = reg.resolve(args.metric or "billing")
    if obj is None or not in_scope(kind, obj):
        kind, obj = reg.resolve("billing")
    fmt = _fmt(kind, obj)
    month = q.month
    bu = q.bu_measures(filt)
    if bu.empty:
        return _refusal("rank_landing", "No business units in your scope match this request.", "refusal")
    leaf_ids, codes, L = q.leaf_matrix(filt)
    R = q.residuals(leaf_ids)
    b50 = L[:, [i for i, c in enumerate(codes) if ctx.sl.line_of[c] == 1]].sum(axis=1)
    draws = E.simulate(b50, R, q.draws, q.seed)
    with np.errstate(divide="ignore", invalid="ignore"):
        S = np.where(np.abs(b50) > 1e-9, draws / np.where(np.abs(b50) > 1e-9, b50, 1.0), 1.0)
    scaled = np.array([ctx.sl.line_of[c] in (1, 4, 5, 8, 9) for c in codes])
    org_rows = ctx.sl.d.org.set_index("bu_id").loc[leaf_ids]
    groups = org_rows[lvl].to_numpy()
    budget = ctx.sl.frame([ti.Series("Budget", "Budget", ti.Period("MONTH", month), (month,))], filt, [lvl])
    fcv = ti.latest_forecast(month // 100, ctx.as_of) or "Budget"
    fcw = ctx.sl.frame([ti.Series(fcv, fcv, ti.Period("MONTH", month), (month,))], filt, [lvl])
    rows = []
    pats = dict(zip(bu["l6_bu"], bu["pattern_class"]))
    for g in sorted(set(groups)):
        idx = np.where(groups == g)[0]
        w50 = q._wide_from_codes(L[idx].sum(axis=0, keepdims=True), codes)
        aggD = np.repeat(L[idx].sum(axis=0, keepdims=True), q.draws, axis=0)
        aggD[:, scaled] = S[:, idx] @ L[idx][:, scaled]
        wD = q._wide_from_codes(aggD, codes)
        p50, lo, hi = q.value_and_range(kind, obj, w50, wD)
        b = budget[budget[lvl] == g]
        f_ = fcw[fcw[lvl] == g]
        bv = float(np.asarray(ctx.sl.value(b, kind, obj)).ravel()[0]) if not b.empty else np.nan
        fv = float(np.asarray(ctx.sl.value(f_, kind, obj)).ravel()[0]) if not f_.empty else np.nan
        gb, gbr = _diff(p50, bv, fmt)
        gf, gfr = _diff(p50, fv, fmt)
        row = {LEVEL_LABEL[lvl]: g, "Landing (P50)": p50, "P10": lo, "P90": hi, "Budget": bv,
               "Gap vs budget": gb, "Gap % vs budget": gbr, fcv: fv, f"Gap vs {fcv}": gf,
               "_fav_Gap vs budget": _fav(gb, obj.favorable), f"_fav_Gap vs {fcv}": _fav(gf, obj.favorable)}
        if lvl == "l6_bu":
            row["Billing pattern"] = C.PATTERN_LABELS.get(pats.get(g, ""), "-")
        rows.append(row)
    sort_by = (args.sort_by or "gap_vs_budget").lower()
    key = {"gap_vs_budget": "Gap vs budget", "gap_vs_forecast": f"Gap vs {fcv}", "landing": "Landing (P50)"}.get(
        sort_by, "Gap vs budget")
    miss_q = bool(re.search(r"\b(miss|below|short|shortfall|under|fall short|worst|behind)\b", ctx.question or "", re.I))
    beat_q = bool(re.search(r"\b(beat|exceed|above|ahead|best|over)\b", ctx.question or "", re.I))
    up = obj.favorable != "down"
    asc = (miss_q or not beat_q) if key != "Landing (P50)" else False
    asc = asc if up else not asc
    rows.sort(key=lambda r: (r[key] if _ok(r[key]) else (np.inf if asc else -np.inf)), reverse=not asc)
    n_below = sum(1 for r in rows if _ok(r["Gap vs budget"]) and ((r["Gap vs budget"] < 0) == up) and r["Gap vs budget"] != 0)
    shown = rows
    if miss_q and key == "Gap vs budget":
        shown = [r for r in rows if _ok(r["Gap vs budget"]) and ((r["Gap vs budget"] < 0) == up)]
    top_n = args.top_n if args.top_n and args.top_n > 0 else len(shown)
    shown = shown[:top_n]
    lbl = LEVEL_LABEL[lvl]
    plural = "BUs" if lvl == "l6_bu" else F.plural(lbl.lower())
    scope = org_label(filt)
    facts = [f"{obj.name} landing for {ti.month_label(month)} by {lbl if lbl.isupper() else lbl.lower()} in {scope}: {n_below} of {len(rows)} "
             f"{plural} land {'below' if up else 'above'} budget at P50 (computed {q.snap.snapshot_date.isoformat()})."]
    items = []
    for i, r in enumerate(shown[:10], 1):
        items.append(f"{i}. {r[lbl]} {_val(r['Landing (P50)'], fmt)} ({_rng(r['P10'], r['P90'], fmt)}), "
                     + cmp_phrase(r["Gap vs budget"], r["Budget"], "budget", fmt, r["_fav_Gap vs budget"],
                                  getattr(obj, "is_cost", False), r["Gap % vs budget"]))
    if items:
        facts.append(("Expected to miss budget (largest shortfall first): " if miss_q else "Ranking: ") + "; ".join(items) + ".")
    elif miss_q:
        facts.append(f"No {plural} in {scope} land below budget at P50.")
    facts.append(WIP_NOTE)
    acc = accuracy_note(ctx.sl.engine)
    if acc:
        facts.append(acc)
    columns = [lbl, "Landing (P50)", "P10", "P90", "Budget", "Gap vs budget", "Gap % vs budget", fcv, f"Gap vs {fcv}"] + \
        (["Billing pattern"] if lvl == "l6_bu" else [])
    col_fmt = {c: ("pct" if c == "Gap % vs budget" else fmt) for c in columns if c not in (lbl, "Billing pattern")}
    if fmt == "pct":
        col_fmt["Gap vs budget"] = col_fmt[f"Gap vs {fcv}"] = "pp"
        col_fmt["Gap % vs budget"] = None
    table = _table(columns, shown, col_fmt, f"{obj.name} landing for {ti.month_label(month)} (P50 with P10-P90) vs "
                                           f"budget and {fcv}. {WIP_NOTE}",
                   fav_cols=["Gap vs budget", f"Gap vs {fcv}"])
    chart = {"type": "hbar", "title": f"{obj.name} landing vs budget, {ti.month_label(month)} - {scope}",
             "fmt": "pp" if fmt == "pct" else fmt, "x": "value", "y": ["label"],
             "data": [{"label": str(r[lbl]), "value": r["Gap vs budget"], "fav": r["_fav_Gap vs budget"]}
                      for r in shown[:15]], "meta": {}}
    first = shown[0][lbl] if shown else scope
    return ToolOutput(tool="rank_landing", kind="landing_rank", data=_strip(shown), facts=facts,
                      filters_used=_filters(ctx, q, filt, f"{ti.month_label(month)} (landing)", ti.month_label(month)),
                      notes=_landing_notes(ctx, notes),
                      meta={"table_spec": table, "chart_spec": chart, "level": lvl, "level_label": lbl,
                            "ascending": asc, "name": f"{obj.name} landing",
                            "followups": [f"Explain the landing for {first}",
                                          f"What's the {ti.MONTH_NAMES[month % 100 - 1]} landing for {first}?",
                                          f"Revenue YTD till {ti.MONTH_NAMES[month % 100 - 1]} with landing vs budget "
                                          f"for {scope}"]})


# ------------------------------------------------------------------------------------------
# explain_landing
# ------------------------------------------------------------------------------------------
def tool_explain_landing(args: ExplainLandingArgs, ctx: ToolContext) -> ToolOutput:
    from app.landing.query import method_rows  # noqa: WPS433

    filt, refusal, notes = resolve_org(ctx, args.org, "explain_landing")
    if refusal:
        return refusal
    q = LandingQuery(ctx.sl)
    if not q.available:
        return _no_landing("explain_landing", q)
    month = q.month
    mr = method_rows(ctx.sl, filt)
    bu = q.bu_measures(filt)
    if mr.empty or bu.empty:
        return _refusal("explain_landing", "No business units in your scope match this request.", "refusal")
    scope = org_label(filt)
    single = bu["bu_id"].nunique() == 1
    rows = []
    facts = [f"How the {ti.month_label(month)} billing landing for {scope} is calculated (as of "
             f"{q.snap.snapshot_date.isoformat()}): each BU's billing is forecast with four methods on monthly "
             "history (working-day adjusted) and combined with weights learned from each method's recent errors; "
             "costs follow the billing landing (intragroup, subcontracting and other costs as ratios to billing), "
             "personnel uses a seasonality-adjusted 3-month run-rate and functional lines come from the latest forecast."]
    total = float(bu["billing_p50"].sum())
    for m in (*E.METHODS, E.BASELINE):
        sub = mr[mr["method"] == m]
        pred = float(sub["prediction"].sum()) if not sub.empty else np.nan
        if single:
            wgt = float(sub["weight"].iloc[0]) if not sub.empty and _ok(sub["weight"].iloc[0]) else np.nan
            wape = float(sub["backtest_wape"].iloc[0]) if not sub.empty and _ok(sub["backtest_wape"].iloc[0]) else np.nan
        else:
            ok = sub.dropna(subset=["weight"])
            wgt = float((ok["weight"] * ok["prediction"]).sum() / pred) if pred and m in E.METHODS else np.nan
            wape = np.nan
        rows.append({"Method": E.METHOD_LABEL[m], "Billing prediction": pred,
                     "Weight in the landing": wgt if m in E.METHODS else None,
                     "Recent error of this method (WAPE)": wape})
    rows.append({"Method": E.METHOD_LABEL["ensemble"], "Billing prediction": total, "Weight in the landing": 1.0,
                 "Recent error of this method (WAPE)": None, "_kind": "subtotal"})
    for r in rows[:-1]:
        if _ok(r["Billing prediction"]):
            facts.append(f"{r['Method']}: {F.eur(r['Billing prediction'])}" +
                         (f", weight {F.pct(r['Weight in the landing'], 0)}" if _ok(r.get("Weight in the landing")) else "") +
                         (f", recent WAPE {F.pct(r['Recent error of this method (WAPE)'])}"
                          if _ok(r.get("Recent error of this method (WAPE)")) else "") + ".")
    facts.append(f"Landing P50 (weighted): {F.eur(total)}.")
    if single:
        b = bu.iloc[0]
        pat = C.PATTERN_LABELS.get(b["pattern_class"], b["pattern_class"])
        prof = _profile(ctx, int(b["bu_id"]))
        m3 = mr[mr["method"] == "M3_forecast_bias"]["detail"]
        ratio = m3.iloc[0].get("ratio") if not m3.empty else None
        fcv = m3.iloc[0].get("forecast") if not m3.empty else None
        facts.append(f"Billing pattern: {pat}" + (f" (quarter-end months {F.pct(prof.get('quarter_end_share'))} of the "
                                                  f"year, December {F.pct(prof.get('december_share'))}, month-to-month "
                                                  f"noise {F.pct(prof.get('cv'))})" if prof else "") + ".")
        if ratio:
            facts.append(f"Over the last 24 months actual billing was {F.pct(float(ratio), 1)} of the forecast available "
                         f"at the time; the forecast-based method scales {fcv} by that (shrunk toward 100%).")
        facts.append(f"P10-P90 {F.eur(float(b['billing_p10']))} - {F.eur(float(b['billing_p90']))} from this BU's "
                     "(or its pattern class's) past landing errors.")
    else:
        mix = bu.groupby("pattern_class")["billing_p50"].sum().sort_values(ascending=False)
        facts.append("Billing landing by pattern class: " + "; ".join(
            f"{C.PATTERN_LABELS.get(k, k)} {F.eur(v)}" for k, v in mix.items()) + ".")
    facts.append(WIP_NOTE)
    acc = accuracy_note(ctx.sl.engine)
    if acc:
        facts.append(acc)
    columns = ["Method", "Billing prediction", "Weight in the landing", "Recent error of this method (WAPE)"]
    table = _table(columns, rows, {"Billing prediction": "eur", "Weight in the landing": "pct",
                                   "Recent error of this method (WAPE)": "pct"},
                   "Billing landing by method; weights are learned per BU from recent errors and shrunk toward the "
                   "BU's pattern class." + ("" if single else " For several BUs the weight is the billing-weighted average."))
    chart = {"type": "bar", "title": f"Billing landing by method, {ti.month_label(month)} - {scope}", "fmt": "eur",
             "x": "label", "y": ["value"], "data": [{"label": r["Method"], "value": r["Billing prediction"]} for r in rows
                                                     if _ok(r["Billing prediction"])], "meta": {}}
    return ToolOutput(tool="explain_landing", kind="landing_explain", data=_strip(rows), facts=facts,
                      filters_used=_filters(ctx, q, filt, f"{ti.month_label(month)} (landing)", ti.month_label(month)),
                      notes=_landing_notes(ctx, notes),
                      meta={"table_spec": table, "chart_spec": chart, "name": "Landing method",
                            "followups": [f"What's the {ti.MONTH_NAMES[month % 100 - 1]} landing for {scope}?",
                                          f"Which BUs in {scope} are expected to miss budget this month?",
                                          "What data do you use?"]})


def _profile(ctx, bu_id: int) -> dict:
    from app.landing.query import bu_profiles  # noqa: WPS433

    df = bu_profiles(ctx.sl)
    if df.empty:
        return {}
    r = df[df["bu_id"] == bu_id]
    if r.empty:
        return {}
    r = r.iloc[0]
    return {k: float(r[k]) for k in ("quarter_end_share", "december_share", "cv") if _ok(r[k])}


# ------------------------------------------------------------------------------------------
# Both operating margins side by side (get_ratio with generic margin wording)
# ------------------------------------------------------------------------------------------
def ratio_pair_output(ctx: ToolContext, filt, period, comps, notes) -> ToolOutput:
    reg = registry()
    res = [ctx.sl.ratio(rid, filt, period, comps) for rid in MARGINS]
    a, b = res[0].df, res[1].df
    names = [reg.ratios[r].name for r in MARGINS]
    df = pd.DataFrame({"Version": a["Version"], "Period": a["Period"],
                       reg.metrics["maop"].name: a[a.columns[2]], reg.metrics["revenue"].name: a[a.columns[3]],
                       reg.metrics["production"].name: b[b.columns[3]], names[0]: a[names[0]], names[1]: b[names[1]]})
    rows = _records(df)
    base = rows[0] if rows else {}
    facts = [f"No margin base was named, so both operating margins are shown for {res[0].filters['org']}, "
             f"{base.get('Period')} (Actual): {names[0]} {_val(base.get(names[0]), 'pct')}; "
             f"{names[1]} {_val(base.get(names[1]), 'pct')}. Aggregates are ratios of sums."]
    facts.append(f"Components (Actual): {reg.metrics['maop'].name} {F.eur(base.get(reg.metrics['maop'].name))}; "
                 f"Revenue {F.eur(base.get('Revenue'))}; Production {F.eur(base.get('Production'))}.")
    for n in names:                           # one key-figure line per margin, actual value first (like P&L lines)
        parts = [f"Actual {_val(base.get(n), 'pct')}"]
        for r in rows[1:]:
            d = (base.get(n) - r.get(n)) if _ok(base.get(n)) and _ok(r.get(n)) else None
            r[f"vs {n}"] = d
            parts.append(cmp_phrase(d, r.get(n), f"{r['Version']} ({r['Period']})", "pct", ti.is_favorable(d, "up")))
        facts.append(f"{n}: " + "; ".join(parts) + ".")
    for r in rows:
        r.setdefault(f"vs {names[0]}", None)
        r.setdefault(f"vs {names[1]}", None)
    columns = ["Version", "Period", reg.metrics["maop"].name, "Revenue", "Production", names[0], names[1]]
    col_fmt = {reg.metrics["maop"].name: "eur", "Revenue": "eur", "Production": "eur", names[0]: "pct", names[1]: "pct"}
    table = _table(columns, rows, col_fmt, "Both operating margins (no base named). Margins = operating profit / "
                                           "revenue and / production; aggregates are ratios of sums.")
    chart = {"type": "grouped_bar", "title": f"Operating margins - {res[0].filters['org']}", "fmt": "pct",
             "x": "category", "y": names,
             "data": [{"category": f"{r['Version']} ({r['Period']})", "series": n, "value": r.get(n)}
                      for r in rows for n in names], "meta": {}}
    out_notes = list(dict.fromkeys([MARGIN_PAIR_NOTE] + notes + res[0].notes + res[1].notes))
    return ToolOutput(tool="get_ratio", kind="ratio_pair", data=rows, sql=res[0].sql + res[1].sql,
                      filters_used=res[0].filters, notes=out_notes, facts=facts,
                      meta={"table_spec": table, "chart_spec": chart, "name": "Operating margins", "fmt": "pct",
                            "target": "operating_margins", "series": list(a["Version"])})


TOOL_DESCRIPTIONS = {
    "describe_catalog": f"What {B.APP_NAME} covers, from the live data catalog (never SQL): regions, countries, product lines, "
                        "businesses, business units, P&L lines (accounts), metrics, ratios, versions, periods, billing "
                        "patterns, capabilities or example questions. Use for 'what regions are in scope?', 'which "
                        "businesses can I ask about?', 'list all metrics', 'what ratios do you support?', 'what data do "
                        "you use?', 'what can you do?', 'help'.",
    "get_landing": "Current-month landing (expected month-end of the open month) with P50 and P10-P90 for billing, "
                   "revenue, production, operating profit and both operating margins, vs budget, latest forecast and "
                   "PY. Use for 'November landing', 'where will revenue land this month', 'profit % landing'.",
    "get_ytd_with_landing": "YTD / QTD including the landing (closed-month actuals + landing month) or the full-year "
                            "outlook (actuals + landing + latest forecast) for a metric or ratio, vs PY, budget and "
                            "latest forecast. Use for 'YTD margin through November including the landing', "
                            "'revenue YTD till November with landing vs budget', 'full-year outlook'.",
    "rank_landing": "Rank BUs / businesses / countries by their landing vs budget or forecast. Use for 'which BUs are "
                    "expected to miss budget this month?'.",
    "explain_landing": "How a landing was calculated: methods, weights, billing pattern, forecast accuracy and range.",
}

TOOLS_EXTRA = {
    "describe_catalog": (DescribeCatalogArgs, tool_describe_catalog),
    "get_landing": (GetLandingArgs, tool_get_landing),
    "get_ytd_with_landing": (GetYtdWithLandingArgs, tool_get_ytd_with_landing),
    "rank_landing": (RankLandingArgs, tool_rank_landing),
    "explain_landing": (ExplainLandingArgs, tool_explain_landing),
}


def dumps(x) -> str:
    return json.dumps(x, default=str)
