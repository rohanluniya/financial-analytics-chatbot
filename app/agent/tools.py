"""Agent tools (Pydantic-typed). Every tool returns a ToolOutput with
{data, sql, filters_used, notes} plus deterministic `facts` (pre-formatted numbers that the LLM
may quote) and rendering metadata. Tool arguments are deliberately simple strings so that small
local models can call them; the tools resolve org/period/version text themselves.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator

from app.config import as_of_date, backend
from app.semantic import time_intel as ti
from app.semantic.access import check_access, default_org
from app.semantic.dims import dims
from app.semantic.entity_resolver import LEVEL_LABEL, ORG_LEVELS, Resolution, org_label, resolve
from app.semantic.query_builder import Result, SemanticLayer
from app.semantic.registry import registry
from app.viz import format as F

CUR = F.CUR
CMP_RX = re.compile(r"\b(vs\.?|versus|against|compared?|relative to)\b", re.I)


# ------------------------------------------------------------------------------------------
# Output + context
# ------------------------------------------------------------------------------------------
class ToolOutput(BaseModel):
    tool: str
    ok: bool = True
    kind: str = ""
    data: list[dict] = Field(default_factory=list)
    sql: list[str] = Field(default_factory=list)
    filters_used: dict = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)
    error: str | None = None

    def llm_view(self) -> str:
        if not self.ok:
            return f"[{self.tool}] ERROR: {self.error}"
        lines = [f"[{self.tool}] scope: {self.filters_used.get('org')} | period: {self.filters_used.get('period')}"]
        lines += [f"- {f}" for f in self.facts]
        lines += [f"NOTE: {n}" for n in self.notes]
        return "\n".join(lines)


@dataclass
class ToolContext:
    user_id: str
    as_of: date = field(default_factory=as_of_date)
    question: str = ""
    resolution: Resolution | None = None
    memory: dict = field(default_factory=dict)
    _sl: SemanticLayer | None = None

    @property
    def sl(self) -> SemanticLayer:
        if self._sl is None:
            self._sl = SemanticLayer(self.user_id, self.as_of)
        return self._sl


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        parts = re.split(r",|;|\bvs\.?\b|\bversus\b|\band\b|/", v)
        return [p.strip() for p in parts if p.strip()]
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            out += _as_list(x) if isinstance(x, str) and ("," in x) else ([str(x).strip()] if str(x).strip() else [])
        return out
    return [str(v)]


def _as_int(v: Any, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes", "asc", "ascending", "bottom", "lowest", "worst")


# ------------------------------------------------------------------------------------------
# Argument schemas (simple on purpose)
# ------------------------------------------------------------------------------------------
class ResolveEntitiesArgs(BaseModel):
    text: str = Field(description="Question or fragment to resolve, e.g. 'Brazl env lab Q3 2025'")


class GetPnlArgs(BaseModel):
    org: str = Field("", description="Org in plain words: 'United States', 'Canada Environmental Lab Testing', 'US & Canada', 'BPU', 'US-EPV-DEN-01'. Empty = user's default scope")
    period: str = Field("", description="'YTD', 'Q3 2025', 'March 2025', 'FY 2025', 'last month', 'R12M'. Empty = YTD of last closed month")
    period_type: str = Field("", description="Optional: MONTH, QTD, YTD, R12M, FY, QUARTER")
    versions: list[str] = Field(default_factory=lambda: ["Actual", "PY", "Budget"],
                                description="First = main version, rest = comparisons. Allowed: Actual, PY, Budget, FC1, FC2, FC3, LatestFC")
    account_depth: int = Field(1, description="1 = P&L lines, 2 = adds direct / indirect staff costs, 3 = all accounts")

    @field_validator("versions", mode="before")
    @classmethod
    def coerce_versions(cls, v):
        return _as_list(v) or ["Actual", "PY", "Budget"]

    @field_validator("account_depth", mode="before")
    @classmethod
    def coerce_account_depth(cls, v):
        return _as_int(v, 1)

class GetTrendArgs(BaseModel):
    metric_or_ratio: str = Field(description="Metric or ratio: 'operating profit', 'production', 'personnel cost', 'wip', 'personnel_to_revenue', 'operating margin'")
    org: str = Field("", description="Org in plain words (see get_pnl)")
    start: str = Field("", description="First month, e.g. '2023-01' or 'Jan 2025'. Empty = 24 months back")
    end: str = Field("", description="Last month, e.g. '2026-10'. Empty = last closed month")
    versions: list[str] = Field(default_factory=lambda: ["Actual", "PY", "Budget"],
                                description="Series to plot: Actual, PY, Budget, FC1, FC2, FC3, LatestFC")

    @field_validator("versions", mode="before")
    @classmethod
    def coerce_versions(cls, v):
        return _as_list(v) or ["Actual", "PY", "Budget"]

class GetRatioArgs(BaseModel):
    ratio_name: str = Field(description="Ratio: direct_margin, gross_margin, maop_margin_revenue, personnel_to_billing, personnel_to_revenue, personnel_to_production, direct_labor_to_production, subcontracting_pct, other_cost_pct, functional_cost_pct, utilization_rate, production_per_hour, production_per_fte, personnel_cost_per_fte, overtime_ratio, production_hourly_cost, wip_pct_revenue, net_income_margin, or 'X / Y'")
    org: str = Field("", description="Org in plain words")
    period: str = Field("", description="Period words (see get_pnl)")
    comparison: str = Field("PY,Budget", description="Comma-separated: PY, Budget, FC1, FC2, FC3, LatestFC")

    @field_validator("comparison", mode="before")
    @classmethod
    def coerce_comparison(cls, v):
        return ",".join(_as_list(v)) if not isinstance(v, str) else v

class VarianceDriversArgs(BaseModel):
    metric: str = Field(description="Metric or ratio to explain: 'operating profit', 'operating margin', 'personnel_7a' (direct staff costs), 'production', 'subcontracting'")
    org: str = Field("", description="Org in plain words")
    period: str = Field("", description="Period words (see get_pnl)")
    comparison: str = Field("PY", description="One of PY, Budget, FC1, FC2, FC3, LatestFC")
    depth: int = Field(1, description="1 = direct drivers, 2 = leaf accounts")

    @field_validator("comparison", mode="before")
    @classmethod
    def coerce_comparison(cls, v):
        return (_as_list(v) or ["PY"])[0]

    @field_validator("depth", mode="before")
    @classmethod
    def coerce_depth(cls, v):
        return _as_int(v, 1)

class RankEntitiesArgs(BaseModel):
    metric_or_ratio: str = Field(description="Metric or ratio to rank by, e.g. 'operating margin', 'subcontracting'")
    org_level: str = Field("l6_bu", description="l2_region, l3_country, l4_product_line, l5_business or l6_bu")
    parent_filter: str = Field("", description="Org to rank within, e.g. 'US & Canada' or 'Mexico'. Empty = user's default scope")
    period: str = Field("", description="Period words (see get_pnl)")
    top_n: int = Field(5, description="Number of entities, 0 = all")
    ascending: bool = Field(False, description="true = lowest first (bottom/worst)")

    @field_validator("top_n", mode="before")
    @classmethod
    def coerce_top_n(cls, v):
        return _as_int(v, 5)

    @field_validator("ascending", mode="before")
    @classmethod
    def coerce_ascending(cls, v):
        return _as_bool(v)

class CompareVersionsArgs(BaseModel):
    org: str = Field("", description="Org in plain words")
    period: str = Field("", description="Period words (see get_pnl)")
    versions: list[str] = Field(default_factory=lambda: ["Actual", "Budget", "FC1", "FC2", "FC3"],
                                description="Versions: Actual, Budget, FC1, FC2, FC3, LatestFC")

    @field_validator("versions", mode="before")
    @classmethod
    def coerce_versions(cls, v):
        return _as_list(v) or ["Actual", "Budget", "FC1", "FC2", "FC3"]

class GetKpiCockpitArgs(BaseModel):
    org: str = Field("", description="Org in plain words (see get_pnl)")
    month: str = Field("", description="Month for MTD, e.g. 'March 2026' or '2026-03'. Empty = last closed month")


class GetWorkforceArgs(BaseModel):
    org: str = Field("", description="Org in plain words (see get_pnl)")
    period: str = Field("", description="Period words (see get_pnl). Employee records cover closed months only")
    group_by: str = Field("", description="role, grade, staff_type (direct / indirect), month, or an org level "
                                          "(region, country, product line, business, BU). Empty = from the question")
    metric: str = Field("", description="Main figure: headcount, fte, hires, leavers, attrition, voluntary_attrition, "
                                        "utilization, overtime. Empty = from the question")
    top_n: int = Field(0, description="For org levels: number of entities to list, 0 = all")

    @field_validator("top_n", mode="before")
    @classmethod
    def coerce_top_n(cls, v):
        return _as_int(v, 0)


class RunReadonlySqlArgs(BaseModel):
    sql: str = Field(description="ONE read-only SELECT over the views v_pnl, v_pnl_leaf, v_stats, v_org, v_account, v_period, "
                                 "v_version, v_employee, v_employee_month")


LEVEL_WORDS = {
    "bu": "l6_bu", "bus": "l6_bu", "business unit": "l6_bu", "business units": "l6_bu", "l6": "l6_bu",
    "business": "l5_business", "businesses": "l5_business", "l5": "l5_business",
    "product line": "l4_product_line", "product lines": "l4_product_line", "pl": "l4_product_line",
    "l4": "l4_product_line", "country": "l3_country", "countries": "l3_country", "l3": "l3_country",
    "region": "l2_region", "regions": "l2_region", "l2": "l2_region",
    "sector": "l4_product_line", "sectors": "l4_product_line",
}


# ------------------------------------------------------------------------------------------
# Resolution helpers
# ------------------------------------------------------------------------------------------
def _refusal(tool: str, message: str, kind: str = "refusal", options: list | None = None) -> ToolOutput:
    return ToolOutput(tool=tool, ok=False, kind=kind, error=message, extra={"options": options or []})


def resolve_org(ctx: ToolContext, org_text: str | None, tool: str):
    """Return (org_filter, refusal_or_None, notes)."""
    filt: dict = {}
    amb: list = []
    q_filter = ctx.resolution.org_filter if ctx.resolution else {}
    if org_text and org_text.strip() and org_text.strip().lower() not in ("none", "null", "default", "all"):
        r = resolve(org_text, dims().org, ctx.as_of)
        filt, amb = r.org_filter, r.ambiguous
        if not filt and not amb:
            filt = q_filter
    else:
        filt = q_filter or {}
    if not filt and ctx.memory.get("org_filter"):
        filt = ctx.memory["org_filter"]
    if amb:
        opts = amb[0]["options"]
        return None, _refusal(tool, f"'{amb[0]['text']}' matches several businesses: " + ", ".join(opts)
                              + ". Which one do you mean?", "clarify", opts), []
    if not filt:
        filt = default_org(ctx.user_id)
    decision = check_access(ctx.user_id, filt)
    if decision.status in ("denied", "empty"):
        return None, _refusal(tool, decision.message or "No access."), []
    notes = [decision.message] if decision.status == "narrowed" else []
    return decision.org_filter, None, notes


def resolve_period(ctx: ToolContext, period_text: str | None, period_type: str | None = None) -> ti.Period:
    if period_text and period_text.strip():
        return ti.parse_period(period_text, period_type, ctx.as_of)
    if ctx.resolution and ctx.resolution.period:
        p = ctx.resolution.period_obj()
        if period_type and p.period_type in ("MONTH", "FY", "YTD"):
            return ti.parse_period(ti.month_label(p.end_key) if p.period_type == "MONTH" else str(p.year),
                                   period_type, ctx.as_of)
        return p
    if ctx.memory.get("period"):
        m = ctx.memory["period"]
        return ti.Period(m["type"], m["end"], m["start"] if m["type"] == "RANGE" else None)
    return ti.parse_period(None, period_type, ctx.as_of)


def norm_versions(values: list[str]) -> list[str]:
    out = []
    for v in values:
        n = ti.normalize_version(v)
        if n and n not in out:
            out.append(n)
    return out


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    clean = df.replace([np.inf, -np.inf], np.nan).astype(object).where(pd.notna(df), None)
    recs = clean.to_dict(orient="records")
    for r in recs:
        for k, v in r.items():
            if isinstance(v, (np.floating,)):
                r[k] = float(v)
            elif isinstance(v, (np.integer,)):
                r[k] = int(v)
            elif isinstance(v, np.bool_):
                r[k] = bool(v)
    return recs


def _output(tool: str, res: Result, notes: list[str]) -> ToolOutput:
    return ToolOutput(tool=tool, kind=res.kind, data=_records(res.df), sql=res.sql,
                      filters_used=res.filters, notes=list(dict.fromkeys(notes + res.notes)),
                      meta=res.meta,
                      extra={k: _records(v) if isinstance(v, pd.DataFrame) else v for k, v in res.extra.items()})


def _fav_word(f) -> str:
    if f is None or (isinstance(f, float) and math.isnan(f)):
        return "neutral"
    return "favourable" if bool(f) else "unfavourable"


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _val(x: float | None, fmt: str) -> str:
    if fmt == "rate":
        return F.rate(x)
    return F.eur(x) if fmt == "eur" else F.value(x, fmt)


def _mag(x: float, fmt: str) -> str:
    """Unsigned magnitude of a difference in display format."""
    if fmt == "pct":
        return F.pp(abs(x)).lstrip("+")
    if fmt == "num":
        return F.num(abs(x), 1 if abs(x) < 100 else 0)
    if fmt == "rate":
        return F.rate(abs(x))
    return F.eur(abs(x))


def cmp_phrase(diff: float | None, ref: float | None, lab: str, fmt: str = "eur", fav=None,
               cost: bool = False, rel: float | None = None) -> str:
    """Comparison spelled out for the writer, so that small models never have to infer a direction:
    'USD 3.5M (6.8%) above PY (USD 51.0M), favourable' / '2.4 pp below Budget (17.1%), unfavourable' /
    'USD 6.9M (4.4%) higher than PY (USD 155.5M), unfavourable'. `diff` and `rel` are display values."""
    ref_txt = f" ({_val(ref, fmt)})" if _ok(ref) else ""
    if not _ok(diff):
        return f"no {lab} comparison available"
    tiny = 5e-4 if fmt == "pct" else (0.05 if fmt in ("num", "rate") else 500)
    if abs(diff) < tiny:
        return f"in line with {lab}{ref_txt}"
    up = diff > 0
    word = ("higher than" if up else "lower than") if cost else ("above" if up else "below")
    rel_txt = f" ({F.pct(abs(rel))})" if _ok(rel) and fmt != "pct" else ""
    fav_txt = "" if fav is None else f", {_fav_word(fav)}"
    return f"{_mag(diff, fmt)}{rel_txt} {word} {lab}{ref_txt}{fav_txt}"


def _line_meta() -> dict[str, tuple[str, int]]:
    reg = registry()
    out = {str(m.line): (m.name, m.natural_sign) for m in reg.metrics.values() if m.kind == "line"}
    for g in ("personnel_7a", "personnel_7b"):
        m = reg.metrics[g]
        out[m.code] = (m.name, m.natural_sign)
    return out


# ------------------------------------------------------------------------------------------
# Facts (deterministic, pre-formatted) per result kind
# ------------------------------------------------------------------------------------------
PNL_FACT_LINES = ("13", "6", "3", "11", "7", "8", "9", "12", "18", "21", "1", "2")
OP_BRIDGE = ("6", "7", "8", "9", "10", "12")            # operating profit (line 13) = 6 + 7 + 8 + 9 + 10 + 12


def facts_pnl(res: Result, focus: str | None = None, focus_meta: tuple[str, int] | None = None) -> list[str]:
    df = res.df.set_index("_code")
    labels = res.meta["series"]
    p = labels[0]
    meta = _line_meta()
    if focus and focus_meta and focus not in meta:      # an account or sub-group the question asks about
        meta = {**meta, focus: focus_meta}
    facts = [f"Scope {res.filters['org']}, {res.filters['period']}, main version {p}, amounts in {CUR}."]
    order = list(PNL_FACT_LINES)
    if focus and focus in df.index:
        order = [focus] + [c for c in order if c != focus]
    for code in order:
        if code not in df.index or code not in meta:
            continue
        name, sign = meta[code]
        row = df.loc[code]
        s = f"{name}: {p} {F.eur(row[p] * sign)}"
        for lab in labels[1:]:
            diff, rel = row.get(f"Var vs {lab}"), row.get(f"Var % vs {lab}")
            if _ok(diff):
                s += "; " + cmp_phrase(diff * sign, row[lab] * sign, lab, "eur", row.get(f"_fav_{lab}"),
                                       cost=sign < 0, rel=rel * sign if _ok(rel) else None)
        facts.append(s + ".")
    reasons = []
    # An account / sub-group question (restructuring, bonus, direct staff costs): the operating-profit
    # explanation is not about it, and small models then attribute its drivers to the account.
    for lab in ([] if focus_meta else labels[1:]):
        if "13" not in df.index or not _ok(df.loc["13"].get(f"Var vs {lab}")):
            continue
        total = df.loc["13"][f"Var vs {lab}"]
        up = total >= 0
        items = [(code, df.loc[code][f"Var vs {lab}"]) for code in OP_BRIDGE
                 if code in df.index and _ok(df.loc[code].get(f"Var vs {lab}")) and abs(df.loc[code][f"Var vs {lab}"]) >= 500]

        def word(code, v):
            higher = (v > 0) == (meta[code][1] > 0)
            return f"{meta[code][0]} ({F.eur(abs(v))} {'higher' if higher else 'lower'}, {_fav_word(v > 0)})"
        drivers = sorted([i for i in items if (i[1] > 0) == up], key=lambda x: -abs(x[1]))[:2]
        offsets = sorted([i for i in items if (i[1] > 0) != up], key=lambda x: -abs(x[1]))[:2]
        s = (f"{meta['13'][0]} vs {lab}: {'increase' if up else 'decrease'} of {F.eur(abs(total))}"
             + (" driven by " + " and ".join(word(c, v) for c, v in drivers) if drivers else "")
             + (", partly offset by " + " and ".join(word(c, v) for c, v in offsets) if offsets else "") + ".")
        reasons.append(s)
    facts[2:2] = reasons
    for code in ("maop_margin_revenue", "gross_margin", "direct_margin", "personnel_to_production"):
        if code in df.index:
            row = df.loc[code]
            s = f"{row['Line']}: {p} {F.pct(row[p])}"
            for lab in labels[1:]:
                if _ok(row.get(lab)):
                    s += "; " + cmp_phrase(row.get(f"Var vs {lab}"), row[lab], lab, "pct", row.get(f"_fav_{lab}"))
            facts.append(s + ".")
    for code in ("fte", "headcount"):
        if code in df.index:
            row = df.loc[code]
            s = f"{row['Line']}: {p} {F.num(row[p])}"
            for lab in labels[1:]:
                if _ok(row.get(lab)):
                    s += "; " + cmp_phrase(row.get(f"Var vs {lab}"), row[lab], lab, "num", None,
                                           rel=row.get(f"Var % vs {lab}"))
            facts.append(s + ".")
    return facts


def facts_trend(res: Result) -> list[str]:
    df, meta = res.df, res.meta
    fmt = meta["fmt"]
    name = meta["name"]
    cols = meta["series"]
    yearly = (res.extra or {}).get("yearly") or {}
    facts = [f"{name} monthly trend for {res.filters['org']}, {res.filters['period']} (series: {', '.join(cols)}), {CUR}."]
    act = df.dropna(subset=["Actual"]) if "Actual" in df else pd.DataFrame()
    if len(df) <= 13:
        for c in [c for c in cols if c != "Actual R12M"]:
            vals = ", ".join(f"{m} {F.value(v, fmt)}" for m, v in zip(df["Month"], df[c]) if _ok(v))
            facts.append(f"{c} by month: {vals}")
    years = sorted({int(k) // 100 for k in df["month_key"]})
    if len(years) > 1 or len(df) > 13:
        for c in [c for c in cols if c in ("Actual", "Budget", "PY")]:
            parts = []
            for y in years:
                if c in yearly and y in yearly[c]:          # ratios: sum(numerator) / sum(denominator)
                    yv = yearly[c][y]
                    span = "full year" if yv["months"] == 12 else f"Jan-{ti.month_label(yv['last'])[:3]}" \
                        if yv["months"] == ti.ym(yv["last"])[1] else f"{yv['months']} months"
                    parts.append(f"{y} {F.value(yv['value'], fmt)} ({span})")
                    continue
                sub = df[(df["month_key"] // 100 == y)][c].dropna()
                if sub.empty or meta.get("kind") == "ratio":
                    continue
                v = sub.mean() if fmt in ("pct", "num") else sub.sum()
                parts.append(f"{y}{' average' if fmt in ('pct', 'num') else ''} {F.value(v, fmt)}"
                             + (f" ({len(sub)} months)" if len(sub) < 12 else ""))
            if parts:
                facts.append(f"{c} by calendar year: " + ", ".join(parts))
    if not act.empty:
        last = act.iloc[-1]
        s = f"Latest month {last['Month']}: Actual {F.value(last['Actual'], fmt)}"
        for c in ("PY", "Budget"):
            if c in act and _ok(last.get(c)):
                s += f", {c} {F.value(last[c], fmt)}"
        facts.append(s)
        if fmt == "eur" and meta.get("kind") != "ratio":
            tot = act["Actual"].sum()
            s = f"Total Actual over {act['Month'].iloc[0]} - {act['Month'].iloc[-1]}: {F.eur(tot)}"
            for c in ("PY", "Budget"):
                if c in act and act[c].notna().all():
                    s += "; " + cmp_phrase(tot - act[c].sum(), act[c].sum(), f"{c} for the same months", "eur",
                                           ti.is_favorable(tot - act[c].sum(), meta.get("favorable", "up")),
                                           cost=meta.get("favorable") == "down")
            facts.append(s)
            vals = act["Actual"].tolist()
            if any(v > 0 for v in vals) and any(v < 0 for v in vals):
                runs, start = [], 0
                for i in range(1, len(vals) + 1):
                    if i == len(vals) or (vals[i] > 0) != (vals[start] > 0):
                        runs.append((start, i - 1))
                        start = i
                if len(runs) <= 6:
                    parts = []
                    for a, b in runs:
                        tot_run = float(sum(vals[a:b + 1]))
                        span = act["Month"].iloc[a] if a == b else f"{act['Month'].iloc[a]} - {act['Month'].iloc[b]}"
                        sign = "positive" if vals[a] > 0 else "negative"
                        parts.append(f"{span} total {F.eur(tot_run, signed=True)}"
                                     + (f" ({sign} every month)" if b > a else ""))
                    facts.append("Pattern of Actual: " + "; ".join(parts))
        hi, lo = act.loc[act["Actual"].idxmax()], act.loc[act["Actual"].idxmin()]
        facts.append(f"Highest Actual month: {hi['Month']} {F.value(hi['Actual'], fmt)}; "
                     f"lowest: {lo['Month']} {F.value(lo['Actual'], fmt)}")
        if "Actual R12M" in act and act["Actual R12M"].notna().any():
            r = act.dropna(subset=["Actual R12M"])
            d = r["Actual R12M"].iloc[-1] - r["Actual R12M"].iloc[0]
            facts.append(f"Rolling 12-month {name}: {r['Month'].iloc[0]} {F.pct(r['Actual R12M'].iloc[0])} -> "
                         f"{r['Month'].iloc[-1]} {F.pct(r['Actual R12M'].iloc[-1])} "
                         f"({'up' if d > 0 else 'down'} {F.pp(abs(d)).lstrip('+')})")
    return facts


def facts_ratio(res: Result) -> list[str]:
    df, meta = res.df, res.meta
    fmt = meta["fmt"]
    vfmt = "rate" if fmt == "eur" else fmt
    name = meta["name"]
    base = df.iloc[0]
    facts = [f"{name} for {res.filters['org']}, {base['Period']} (Actual): {_val(base[name], vfmt)}."]
    num_col, den_col = df.columns[2], df.columns[3]
    nfmt = (lambda v: F.num(v, 1)) if meta.get("num_is_stat") else F.eur
    dfmt = (lambda v: F.num(v, 1)) if meta.get("den_is_stat") else F.eur
    facts.append(f"Components (Actual): {num_col} {nfmt(base[num_col])}; {den_col} {dfmt(base[den_col])}.")
    for _, r in df.iloc[1:].iterrows():
        facts.append(f"Actual is " + cmp_phrase(r["Actual vs version"], r[name], f"{r['Version']} ({r['Period']})",
                                                vfmt, r["_fav"]) + ".")
    return facts


def facts_drivers(res: Result) -> list[str]:
    m, df, org = res.meta, res.df, res.extra.get("org")
    if isinstance(org, pd.DataFrame):
        org = _records(org)
    fmt, unit = m["fmt"], m["unit"]
    vfmt = "rate" if (fmt == "eur" and m["kind"] == "ratio") else fmt
    cur, cmp_ = m["current"], m["comparison"]
    tc, tp = m["total_current"], m["total_comparison"]
    diff = tc - tp if _ok(tc) and _ok(tp) else None
    fav = ti.is_favorable(diff, m["favorable"]) if _ok(diff) else None
    rel = diff / abs(tp) if _ok(diff) and tp and fmt == "eur" else None
    head = (f"{m['name']} for {res.filters['org']}, {res.filters['period']}: {cur} {_val(tc, vfmt)}, "
            + cmp_phrase(diff, tp, cmp_, vfmt, fav, cost=m["favorable"] == "down", rel=rel) + ".")
    facts = [head]
    groups = res.extra.get("groups")
    if isinstance(groups, pd.DataFrame) and not groups.empty:
        facts.append("By sub-group: " + "; ".join(
            f"{g['Group']}: {cur} {F.eur(g[cur])} vs {cmp_} {F.eur(g[cmp_])}, change {F.eur(g['Impact'], signed=True)}"
            f" ({_fav_word(g['_fav'])})" for _, g in groups.iterrows()))
    if not df.empty:
        parts = []
        if unit == "pp":
            keep = df[df["Impact"].abs() >= 5e-4]
        else:
            keep = df[df["Impact"].abs() >= max(500.0, 0.005 * abs(diff or 0))]
        for _, r in (keep if not keep.empty else df).head(5).iterrows():
            if unit == "pp":
                parts.append(f"{r['Driver']}: {F.pct(r[cur])} vs {F.pct(r[cmp_])}, impact on {m['name']} "
                             f"{F.pp(r['Impact'])} ({_fav_word(r['_fav'])})")
            else:
                parts.append(f"{r['Driver']}: {F.eur(r[cur])} vs {F.eur(r[cmp_])}, impact {F.eur(r['Impact'], signed=True)}"
                             f" ({_fav_word(r['_fav'])}"
                             + (f", {F.pct(r['Share of variance'])} of the change" if _ok(r.get("Share of variance")) else "")
                             + ")")
        facts.append("Account drivers (largest first): " + "; ".join(parts))
    if org is not None and len(org):
        lvl = [k for k in org[0].keys() if k not in (cur, cmp_, "Impact", "_fav")][0]
        parts = []
        for r in org[:5]:
            if fmt == "pct":
                parts.append(f"{r[lvl]} {F.pct(r[cur])} vs {F.pct(r[cmp_])} ({F.pp(r['Impact'])}, {_fav_word(r['_fav'])})")
            else:
                parts.append(f"{r[lvl]} {_val(r[cur], vfmt)} vs {_val(r[cmp_], vfmt)} "
                             f"(change {F.value(r['Impact'], 'eur' if vfmt == 'rate' else fmt, signed=True)}, {_fav_word(r['_fav'])})")
        facts.append(f"By {lvl if lvl.isupper() else lvl.lower()} (largest change first): " + "; ".join(parts))
    return facts


def facts_ranking(res: Result) -> list[str]:
    m, df = res.meta, res.df
    fmt, lvl, cur = m["fmt"], m["level_label"], m["current"]
    vfmt = "rate" if (fmt == "eur" and m.get("kind") == "ratio") else fmt
    order = "lowest first" if m["ascending"] else "highest first"
    facts = [f"Ranking of {F.plural(lvl)} by {m['name']} within {res.filters['org']}, {res.filters['period']} ({order}); "
             f"{m['entities_total']} {F.plural(lvl)} in scope, showing {len(df)}."]
    parts = []
    for _, r in df.iterrows():
        s = f"{int(r['Rank'])}. {r[lvl]} {_val(r[cur], vfmt)}"
        if "PY" in df.columns and _ok(r.get("PY")):
            s += f" (PY {_val(r['PY'], vfmt)}"
            if fmt == "pct":
                s += f", {F.pp(r['Var'])})"
            else:
                s += f", {F.eur(r['Var'], signed=True)}" + (f", {F.pct(r['Var %'], signed=True)}" if _ok(r.get("Var %")) else "") + ")"
        parts.append(s)
    facts.append("; ".join(parts))
    if fmt == "eur" and m.get("kind") != "ratio" and len(df):
        tot = float(df[cur].sum())
        s = f"Total of the listed {F.plural(lvl)}: {F.eur(tot)}"
        if "PY" in df.columns and df["PY"].notna().all():
            py = float(df["PY"].sum())
            s += "; " + cmp_phrase(tot - py, py, "PY", "eur", ti.is_favorable(tot - py, m.get("favorable", "up")),
                                   cost=m.get("favorable") == "down", rel=(tot - py) / abs(py) if py else None)
        facts.append(s)
    return facts


def facts_versions(res: Result) -> list[str]:
    df = res.df.set_index("_code")
    labels, ref = res.meta["series"], res.meta["reference"]
    facts = [f"Version comparison for {res.filters['org']}, {res.filters['period']}: {', '.join(labels)} ({CUR})."]
    for code, sign in (("maop", 1), ("production", 1), ("personnel", -1), ("subcontracting", -1),
                       ("other_cost", -1), ("functional_cost", -1), ("gross_profit", 1), ("net_income", 1)):
        row = df.loc[code]
        s = f"{registry().metrics[code].name}: " + ", ".join(
            f"{lab} {F.eur(row[lab] * sign)}" for lab in labels)
        if ref:
            for lab in labels:
                if lab != ref and _ok(row.get(f"{lab} vs {ref}")):
                    d = row[f"{lab} vs {ref}"] * sign
                    base = row[ref] * sign
                    s += f"; {lab} is " + cmp_phrase(d, None, ref, "eur", row.get(f"_fav_{lab}"), cost=sign < 0,
                                                     rel=d / abs(base) if base else None)
        facts.append(s + ".")
    for code in ("maop_margin_revenue", "gross_margin", "direct_margin"):
        row = df.loc[code]
        s = f"{row['Line']}: " + ", ".join(f"{lab} {F.pct(row[lab])}" for lab in labels)
        if ref:
            for lab in labels:
                if lab != ref and _ok(row.get(f"{lab} vs {ref}")):
                    s += f"; {lab} is " + cmp_phrase(row[f"{lab} vs {ref}"], None, ref, "pct", row.get(f"_fav_{lab}"))
        facts.append(s + ".")
    return facts


def facts_cockpit(res: Result) -> list[str]:
    df = res.df
    facts = [f"KPI cockpit for {res.filters['org']}: MTD = {res.meta['month']}, YTD = Jan-{res.meta['month']}; "
             f"Actual vs LY (prior year) and vs Budget; {CUR} at budget rate."]
    for _, r in df.iterrows():
        fmt = r["_fmt"]
        vfmt = "rate" if (fmt == "eur" and r["_code"] not in ("production", "personnel_7a")) else fmt
        cost = r.get("_favorable") == "down"
        parts = []
        for lab in ("MTD", "YTD"):
            if not _ok(r.get(lab)):
                continue
            segs = []
            for cmp_ in ("LY", "Budget"):
                d = r.get(f"{lab} vs {cmp_}")
                if not _ok(d):
                    continue
                fav = r.get(f"_fav_{lab} vs {cmp_}")
                if fmt == "pct":
                    segs.append(cmp_phrase(d, None, cmp_, "pct", fav))
                else:                                       # relative difference in %
                    word = ("higher than" if d > 0 else "lower than") if cost else ("above" if d > 0 else "below")
                    segs.append(f"{F.pct(abs(d))} {word} {cmp_}, {_fav_word(fav)}" if abs(d) >= 5e-4
                                else f"in line with {cmp_}")
            parts.append(f"{lab} {_val(r[lab], vfmt)}" + (f" ({'; '.join(segs)})" if segs else ""))
        facts.append(f"{r['KPI']}: " + "; ".join(parts) + ".")
    return facts


WF_PY_COL = {"headcount": "Headcount PY", "fte": "_fte_py", "hires": "_hires_py", "leavers": "_leavers_py",
             "restructuring_leavers": "_restructuring_py", "attrition": "Attrition PY",
             "voluntary_attrition": "_voluntary_attrition_py", "utilization": "Utilization PY", "overtime": "_overtime_py"}
WF_SHORT = {"headcount": "average headcount", "fte": "average FTE", "hires": "hires", "leavers": "leavers",
            "restructuring_leavers": "restructuring leavers", "attrition": "attrition (annualised)",
            "voluntary_attrition": "voluntary attrition (annualised)", "utilization": "utilization",
            "overtime": "overtime ratio"}


def _wf_value(v, fmt: str) -> str:
    if fmt == "pct":
        return F.pct(v)
    if fmt == "count":
        return F.num(v)
    return F.value(v, "num")


def _count_cmp(cur: float, py: float) -> str:
    """'67 (209.4%) more than PY (32)'; the percentage only when PY is at least 20."""
    d = round(cur) - round(py)
    if d == 0:
        return f"in line with PY ({F.num(py)})"
    rel = f" ({F.pct(abs(d) / py)})" if py >= 20 else ""
    return f"{F.num(abs(d))}{rel} {'more' if d > 0 else 'fewer'} than PY ({F.num(py)})"


def facts_workforce(res: Result) -> list[str]:
    from app.semantic.query_builder import WF_METRICS

    m, recs = res.meta, _records(res.df)
    cols, label, focus, has_py = m["cols"], m["group_label"], m["focus"], m["has_py"]
    tot = next((r for r in recs if r.get("_kind") == "subtotal"), recs[0] if recs else {})
    facts = [f"Scope {res.filters['org']}, {res.filters['period']}: workforce from fictional employee records (Actual)"
             + (", compared with the same months of the prior year (PY)." if has_py else ".")]
    items: dict[str, str] = {}
    for key in ("headcount", "fte", "attrition", "voluntary_attrition", "utilization", "overtime"):
        col, name, fmt, fav_dir = cols[key], WF_METRICS[key][1], WF_METRICS[key][2], WF_METRICS[key][3]
        cur, py = tot.get(col), tot.get(WF_PY_COL[key])
        if not _ok(cur):
            continue
        s = f"{name}: {_wf_value(cur, fmt)}"
        if has_py and _ok(py):
            if fmt == "pct":
                s += "; " + cmp_phrase(cur - py, py, "PY", "pct", None if fav_dir == "neutral" else ti.is_favorable(cur - py, fav_dir))
            else:
                s += "; " + cmp_phrase(cur - py, py, "PY", "num", None, rel=(cur / py - 1) if py else None)
        items[key] = s
    lv, rs = tot.get("Leavers"), tot.get("of which restructuring")
    lpy, rpy = tot.get("_leavers_py"), tot.get("_restructuring_py")
    if _ok(lv):
        rs, py_ok = rs or 0, has_py and _ok(lpy)
        vol, vol_py, rs_py = lv - rs, (lpy - (rpy or 0)) if py_ok else None, rpy or 0
        s = f"Leavers: {F.num(lv)}" + (f"; {_count_cmp(lv, lpy)}" if py_ok else "")
        s += f"; of these {F.num(vol)} voluntary and {F.num(rs)} restructuring"
        if py_ok:
            s += f" (PY {F.num(vol_py)} voluntary and {F.num(rs_py)} restructuring)"
        items["leavers"] = s
        # each leaver type with its own change, so the total's change is never paired with one type
        items["restructuring_leavers"] = f"Restructuring leavers: {F.num(rs)}" + (f"; {_count_cmp(rs, rs_py)}" if py_ok else "")
        items["voluntary_leavers"] = f"Voluntary leavers: {F.num(vol)}" + (f"; {_count_cmp(vol, vol_py)}" if py_ok else "")
    if _ok(tot.get("Hires")):
        items["hires"] = f"Hires: {F.num(tot['Hires'])}" + (f"; {_count_cmp(tot['Hires'], tot['_hires_py'])}"
                                                            if has_py and _ok(tot.get("_hires_py")) else "")
    order = [focus] + ["headcount", "attrition", "leavers", "hires", "utilization", "overtime", "voluntary_attrition", "fte",
                       "restructuring_leavers", "voluntary_leavers"]
    seen: list[str] = []
    for k in order:
        if k in items and items[k] not in seen:
            seen.append(items[k])
    facts += [s + "." for s in seen]
    body = [r for r in recs if r.get("_kind") != "subtotal"]
    fcol, fname, ffmt = cols[focus], WF_METRICS[focus][1], WF_METRICS[focus][2]
    if body and m.get("group") == "month":
        mname = fname.replace("(annualised)", "(rolling 12 months)")
        vals = "; ".join(f"{r[label]} {_wf_value(r.get(fcol), ffmt)}" for r in body if _ok(r.get(fcol)))
        facts.append(f"{mname} by month: {vals}.")
        if focus not in ("hires", "leavers", "restructuring_leavers"):
            facts.append("Hires and leavers by month: " + "; ".join(
                f"{r[label]} {F.num(r.get('Hires') or 0)} hires, {F.num(r.get('Leavers') or 0)} leavers" for r in body) + ".")
    elif body:
        pyc = WF_PY_COL.get(focus) if focus in ("headcount", "attrition", "utilization") else None
        short = WF_SHORT.get(focus, focus)
        lt = label if label.isupper() else label.lower()
        ranked = m.get("group") not in ("grade", "staff_type")
        # "highest attrition first" should not list roles with no leavers one by one
        zero_skip = ranked and not m.get("ascending") and focus in (
            "attrition", "voluntary_attrition", "leavers", "restructuring_leavers", "hires")
        zeros = [r for r in body if zero_skip and _ok(r.get(fcol)) and abs(r.get(fcol)) < 1e-12]
        parts = []
        for r in [r for r in body if r not in zeros][:10]:
            s = f"{r[label]} {_wf_value(r.get(fcol), ffmt)}" if _ok(r.get(fcol)) else f"{r[label]} n/a"
            if has_py and pyc and _ok(r.get(pyc)):
                s += f" (PY {_wf_value(r[pyc], ffmt)})"
            parts.append(s)
        if zeros:
            noun = lt if len(zeros) == 1 else F.plural(lt)
            parts.append(f"{'all ' if not parts else ''}{len(zeros)} {'other ' if parts else ''}{noun} "
                         f"{_wf_value(0.0, ffmt)}")
        if ranked:
            head = f"By {lt}, {'lowest' if m.get('ascending') else 'highest'} {short} first"
        else:
            head = f"By {lt}, {short}"
        n_all = m.get("entities_total", 0)
        more = f" ({len(body)} of {n_all} {F.plural(lt)} shown)" if n_all > len(body) else ""
        facts.append(f"{head}{more}: " + "; ".join(parts) + ".")
    peak = m.get("peak_leavers")
    if peak and (focus in ("leavers", "restructuring_leavers", "attrition", "voluntary_attrition") or m.get("group") == "month"):
        rs_txt = f", of which {F.num(peak['restructuring'])} restructuring" if peak["restructuring"] else ""
        facts.append(f"Month with the most leavers: {peak['month']} ({F.num(peak['leavers'])}{rs_txt}).")
    return facts


def make_bullets(out: "ToolOutput") -> list[str]:
    """Key figures as bullet points, copied from the deterministic facts."""
    facts, kind = out.facts or [], out.kind

    def strip(s: str) -> str:
        return s.strip().rstrip(".")

    def items_of(prefix: str, n: int) -> list[str]:
        for f in facts:
            if f.startswith(prefix):
                return [strip(x) for x in f.split(": ", 1)[1].split("; ")][:n]
        return []
    if kind == "pnl":
        rows = {r.get("_code"): r for r in out.data}
        labels = out.meta.get("series", [])
        meta = _line_meta()
        if len(labels) > 1:
            lab = labels[1]
            codes = sorted([c for c in OP_BRIDGE if c in rows and _ok(rows[c].get(f"Var vs {lab}"))],
                           key=lambda c: -abs(rows[c][f"Var vs {lab}"]))[:3]
        else:
            codes = ["6", "7", "11"]
        focus = out.meta.get("focus") or "13"          # no metric named: operating profit is the headline line
        fname = meta[focus][0] if focus in meta else out.meta.get("focus_name")
        codes = [c for c in codes if c != focus]      # the line / account the question asked about comes first
        names = ([fname + ":"] if fname else []) + [meta[c][0] + ":" for c in codes if c in meta]
        picked = [strip(f) for n in names for f in facts if f.startswith(n)]
        margin = [strip(f) for f in facts if f.startswith("Operating margin")]
        return (picked + margin)[:5 if fname else 4]
    if kind == "drivers":
        head = [strip(facts[0])] if facts else []      # the total and its change come first
        b = items_of("By sub-group: ", 3) + items_of("Account drivers (largest first): ", 3)
        org = next((f for f in facts if f.startswith("By ") and "largest change first" in f), None)
        if org and len(b) < 5:
            lvl = org.split(" (", 1)[0][3:]
            b += [f"{lvl if lvl.isupper() else lvl.capitalize()} with the largest change: "
                  + strip(org.split(": ", 1)[1].split("; ")[0])]
        return (head + b)[:6]
    if kind == "ranking":
        return [re.sub(r"^(\d+)\. ", r"Rank \1: ", strip(x)) for x in (facts[1].split("; ") if len(facts) > 1 else [])][:3]
    if kind == "trend":
        keys = ("Actual by calendar year", "Pattern of Actual", "Total Actual", "Latest month", "Rolling 12-month",
                "Highest Actual month")
        return [strip(f) for k in keys for f in facts if f.startswith(k)][:3]
    if kind == "ratio":
        return [strip(f) for f in facts[1:4]]
    if kind == "versions":
        keep = (registry().metrics["maop"].name + ":", "Production:", "Operating margin")
        return [strip(f) for f in facts if f.startswith(keep)][:3]
    if kind == "cockpit":
        keep = ("Direct margin:", "Utilization rate", "Production per FTE", "Overtime ratio")
        return [strip(f) for f in facts if f.startswith(keep)][:4]
    if kind == "workforce":
        body = [strip(f) for f in facts if not f.startswith("Scope ")]
        head, rest = body[:1], body[1:]
        brk = [f for f in rest if f.startswith("By ")]
        if brk:                                          # top 3 of the breakdown
            name, items = brk[0].split(": ", 1)
            brk = [re.sub(r" \(\d+ of \d+ [^)]* shown\)$", "", name) + ": " + "; ".join(items.split("; ")[:3])]
        others = [f for f in rest if not f.startswith(("By ", "Month with the most", "Hires and leavers by month"))
                  and " by month: " not in f]
        peak = [f for f in rest if f.startswith("Month with the most leavers")]
        return (head + brk + others[:3] + peak)[:6]
    if kind in ("landing", "landing_ytd", "landing_explain", "ratio_pair"):
        skip = ("WIP is 0", "The landing uses", "Backtest", "No margin base", "How the", "Components")
        return [strip(f) for f in facts[1:] if not f.startswith(skip)][:6]
    if kind == "landing_rank":
        return [re.sub(r"^(\d+)\. ", r"Rank \1: ", strip(x)) for x in
                (facts[1].split(": ", 1)[1].split("; ") if len(facts) > 1 and ": " in facts[1] else [])][:5]
    return []


# ------------------------------------------------------------------------------------------
# Tools
# ------------------------------------------------------------------------------------------
def tool_resolve_entities(args: ResolveEntitiesArgs, ctx: ToolContext) -> ToolOutput:
    r = resolve(args.text, dims().org, ctx.as_of)
    d = r.to_dict()
    facts = [f"org: {d['org_label'] or 'not specified'}", f"metric: {d['metric'] or 'not specified'}",
             f"period: {(d['period'] or {}).get('label', 'default (YTD)')}",
             f"versions: {d['versions'] or 'none'}; comparisons: {d['comparisons'] or 'none'}"]
    if r.ambiguous:
        facts.append(f"ambiguous: {r.ambiguous}")
    return ToolOutput(tool="resolve_entities", kind="entities", data=[d], facts=facts,
                      filters_used={"org": d["org_label"]})


def tool_get_pnl(args: GetPnlArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "get_pnl")
    if refusal:
        return refusal
    period = resolve_period(ctx, args.period, args.period_type)
    versions = norm_versions(args.versions) or ["Actual", "PY", "Budget"]
    if versions == ["Actual"] and not (ctx.resolution and (ctx.resolution.versions or ctx.resolution.comparisons)):
        versions = ["Actual", "PY", "Budget"]      # finance users expect PY and Budget unless they ask otherwise
    months = period.months()
    if "Actual" not in versions and months and max(months) <= ti.last_closed_month(ctx.as_of) \
            and CMP_RX.search(ctx.question or ""):
        versions.insert(0, "Actual")               # "how are we doing vs budget": Actual is the main version
    if versions[0] == "PY":
        versions.insert(0, "Actual")
    m = registry().get_metric(ctx.resolution.metric) if ctx.resolution and ctx.resolution.metric else None
    focus, focus_meta, depth = None, None, max(1, min(3, args.account_depth))
    if m is not None and m.kind == "line":
        focus = str(m.line)
    elif m is not None and m.kind in ("group", "leaf") and m.code:
        focus, focus_meta = m.code, (m.name, m.natural_sign)
        depth = max(depth, 2 if m.kind == "group" else 3)    # the account asked about must be in the table
    res = ctx.sl.pnl(filt, period, versions, depth)
    out = _output("get_pnl", res, notes)
    out.facts = facts_pnl(res, focus, focus_meta)
    out.meta["focus"] = focus
    out.meta["focus_name"] = focus_meta[0] if focus_meta else None
    return out


def _month_from_text(text: str, default: int, as_of: date, end: bool) -> int:
    if not text or not text.strip():
        return default
    p = ti.parse_period_text(text, as_of).period
    if p is None:
        return default
    months = p.months()
    return months[-1] if end else months[0]


def tool_get_trend(args: GetTrendArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "get_trend")
    if refusal:
        return refusal
    last = ti.last_closed_month(ctx.as_of)
    q_period = ctx.resolution.period_obj() if ctx.resolution and ctx.resolution.period else None
    if not args.start and q_period is not None:
        months = q_period.months()
        start = months[0] if (len(months) > 1 or ctx.resolution.period_is_range) else ti.add_months(months[0], -11)
        end = min(months[-1], last) if not args.end else _month_from_text(args.end, last, ctx.as_of, True)
        if q_period.period_type == "YTD" and len(months) < 3:
            start = ti.add_months(end, -11)
    else:
        end = _month_from_text(args.end, last, ctx.as_of, True)
        start = _month_from_text(args.start, ti.add_months(end, -23), ctx.as_of, False)
    versions = norm_versions(args.versions) or ["Actual", "PY", "Budget"]
    if "Actual" not in versions:
        versions.insert(0, "Actual")
    if len(ti.month_range(start, end)) > 30 and "PY" in versions:
        versions.remove("PY")        # long ranges: PY line duplicates the Actual line
    res = ctx.sl.trend(args.metric_or_ratio, filt, start, end, versions)
    out = _output("get_trend", res, notes)
    out.facts = facts_trend(res)
    return out


def tool_get_ratio(args: GetRatioArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "get_ratio")
    if refusal:
        return refusal
    period = resolve_period(ctx, args.period)
    comps = norm_versions(_as_list(args.comparison)) or ["PY", "Budget"]
    comps = [c for c in comps if c not in ("Actual", "Landing")]
    reg = registry()
    named = reg.get_ratio(args.ratio_name)
    generic = reg.pair_for(args.ratio_name) is not None or (
        named is not None and named.id in ("maop_margin_revenue", "maop_margin_production")
        and bool(ctx.resolution and ctx.resolution.both_margins))
    if generic:
        from app.agent.tools_landing import ratio_pair_output  # noqa: WPS433

        return ratio_pair_output(ctx, filt, period, comps, notes)
    res = ctx.sl.ratio(args.ratio_name, filt, period, comps)
    out = _output("get_ratio", res, notes)
    out.facts = facts_ratio(res)
    return out


def tool_variance_drivers(args: VarianceDriversArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "variance_drivers")
    if refusal:
        return refusal
    period = resolve_period(ctx, args.period)
    comp = (norm_versions([args.comparison]) or ["PY"])[0]
    if comp == "Actual":
        comp = "PY"
    res = ctx.sl.drivers(args.metric, filt, period, comp, max(1, min(3, args.depth)))
    out = _output("variance_drivers", res, notes)
    out.facts = facts_drivers(res)
    return out


def tool_rank_entities(args: RankEntitiesArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.parent_filter, "rank_entities")
    if refusal:
        return refusal
    lvl = args.org_level.strip().lower()
    lvl = lvl if lvl in ORG_LEVELS else LEVEL_WORDS.get(lvl, LEVEL_WORDS.get(lvl.rstrip("s"), "l6_bu"))
    period = resolve_period(ctx, args.period)
    res = ctx.sl.rank(args.metric_or_ratio, lvl, filt, period, args.top_n, args.ascending, "PY")
    out = _output("rank_entities", res, notes)
    out.facts = facts_ranking(res)
    return out


def tool_compare_versions(args: CompareVersionsArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "compare_versions")
    if refusal:
        return refusal
    period = resolve_period(ctx, args.period)
    versions = [v for v in norm_versions(args.versions) if v != "PY"] or ["Actual", "Budget", "FC1", "FC2", "FC3"]
    res = ctx.sl.compare_versions(filt, period, versions)
    out = _output("compare_versions", res, notes)
    out.facts = facts_versions(res)
    return out


def tool_get_kpi_cockpit(args: GetKpiCockpitArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "get_kpi_cockpit")
    if refusal:
        return refusal
    month = None
    if args.month and args.month.strip():
        p = ti.parse_period_text(args.month, ctx.as_of).period
        month = p.end_key if p else None
    elif ctx.resolution and ctx.resolution.period and ctx.resolution.period["type"] == "MONTH":
        month = ctx.resolution.period["end"]
    res = ctx.sl.cockpit(filt, month)
    out = _output("get_kpi_cockpit", res, notes)
    out.facts = facts_cockpit(res)
    return out


# Workforce questions: grouping and main figure from the text (earliest mention wins)
WF_GROUP_RX = [
    ("role", re.compile(r"\b(?:by|per|each|across|for each)\s+(?:job\s+)?roles?\b|\broles\b|\bjob (?:titles?|families)\b", re.I)),
    ("grade", re.compile(r"\b(?:by|per|each|across)\s+grades?\b|\bgrades\b|\bseniority\b", re.I)),
    ("staff_type", re.compile(r"\bstaff[ _]types?\b|\bdirect\s+(?:vs\.?|versus|and)\s+indirect\b|"
                              r"\bindirect\s+(?:vs\.?|versus|and)\s+direct\b", re.I)),
    ("month", re.compile(r"\b(?:by|per|each)\s+month\b|\bmonthly\b|\bmonth[- ]by[- ]month\b|\btrend\b|\bover time\b|"
                         r"\bsince\b", re.I)),
]
WF_METRIC_RX = [
    ("voluntary_attrition", re.compile(r"\bvoluntary\b|\bresign\w*|\bquit(?:s|ting)?\b", re.I)),
    ("attrition", re.compile(r"\b(?:attrition|turnover|churn|retention)\b", re.I)),
    ("restructuring_leavers", re.compile(r"\brestructuring\s+(?:leavers?|exits?)\b|\blayoffs?\b|\blaid off\b|\bredundanc\w*", re.I)),
    ("leavers", re.compile(r"\b(?:leavers?|left|exits?|departures?|leaving)\b", re.I)),
    ("hires", re.compile(r"\b(?:hires?|hiring|hired|joiners?|new starters?|recruit\w*|onboard\w*)\b", re.I)),
    ("utilization", re.compile(r"\butili[sz]ation\b|\bbillab\w*|\bchargeab\w*", re.I)),
    ("overtime", re.compile(r"\bovertime\b", re.I)),
    ("fte", re.compile(r"\bftes?\b|\bfull[- ]time equivalents?\b", re.I)),
]
WF_HEADCOUNT_RX = re.compile(r"\bhead ?counts?\b", re.I)
WF_GENERIC_RX = re.compile(r"\bemployees\b|\bworkforce\b|\bpeople\b|\bstaff\b", re.I)
WF_GROUP_WORDS = {"role": "role", "roles": "role", "job": "role", "job role": "role", "grade": "grade", "grades": "grade",
                  "seniority": "grade", "staff_type": "staff_type", "staff type": "staff_type", "type": "staff_type",
                  "direct / indirect": "staff_type", "direct vs indirect": "staff_type", "direct": "staff_type",
                  "month": "month", "months": "month", "monthly": "month", "trend": "month"}


def _wf_pick(text: str, rxs) -> str | None:
    best = None
    for key, rx in rxs:
        mm = rx.search(text or "")
        if mm and (best is None or mm.start() < best[1]):
            best = (key, mm.start())
    return best[0] if best else None


def wf_focus_from(text: str) -> str | None:
    """Main workforce figure a question asks for (earliest mention; None if it names none)."""
    return _wf_pick(text, WF_METRIC_RX + [("headcount", WF_HEADCOUNT_RX)]) or \
        ("headcount" if WF_GENERIC_RX.search(text or "") else None)


def wf_group_from(text: str) -> str | None:
    return _wf_pick(text, WF_GROUP_RX)


def _wf_norm_group(v: str | None) -> str | None:
    t = (v or "").strip().lower().replace("-", " ")
    if not t or t in ("none", "null", "total", "all"):
        return None
    if t in ORG_LEVELS:
        return t
    return WF_GROUP_WORDS.get(t) or LEVEL_WORDS.get(t) or LEVEL_WORDS.get(t.rstrip("s")) or wf_group_from(t)


def _wf_norm_metric(v: str | None) -> str | None:
    from app.semantic.query_builder import WF_METRICS

    t = (v or "").strip().lower()
    if not t:
        return None
    return t if t in WF_METRICS else wf_focus_from(t)


def tool_get_workforce(args: GetWorkforceArgs, ctx: ToolContext) -> ToolOutput:
    filt, refusal, notes = resolve_org(ctx, args.org, "get_workforce")
    if refusal:
        return refusal
    period = resolve_period(ctx, args.period)
    q, r = ctx.question or "", ctx.resolution
    mem = ctx.memory if ctx.memory.get("tool") == "get_workforce" else {}
    group = _wf_norm_group(args.group_by) or wf_group_from(q) or (r.level_hint if r is not None else None) \
        or mem.get("wf_group") or "staff_type"
    a_focus, q_focus = _wf_norm_metric(args.metric), wf_focus_from(q)
    # the LLM often asks for "leavers" when the question says "restructuring leavers": keep the narrower figure
    narrower = {"leavers": "restructuring_leavers", "attrition": "voluntary_attrition"}
    focus = q_focus if a_focus and q_focus and narrower.get(a_focus) == q_focus else (a_focus or q_focus)
    if not focus and r is not None:
        rmap = {"utilization_rate": "utilization", "overtime_ratio": "overtime", "fte": "fte", "headcount": "headcount"}
        focus = rmap.get(r.ratio or "") or rmap.get((r.metrics or [""])[0])
    focus = focus or mem.get("wf_focus") or "headcount"
    top_n = args.top_n or (r.top_n if r is not None and r.top_n else 0)
    if not top_n and group in ORG_LEVELS and r is not None and "rank" in (r.intents or []):
        top_n = 10
    asc = bool(r.ascending) if r is not None and r.ascending is not None else False
    res = ctx.sl.workforce(filt, period, group, focus, top_n or None, asc)
    out = _output("get_workforce", res, notes)
    out.facts = facts_workforce(res)
    mentioned = {k for k, rx in WF_METRIC_RX if rx.search(q)}
    if group == "month" and mentioned & {"hires", "leavers", "restructuring_leavers"}:
        out.meta["chart"] = "hires_leavers"            # "headcount, hires and leavers by month": bars per month
    return out


def tool_run_readonly_sql(args: RunReadonlySqlArgs, ctx: ToolContext) -> ToolOutput:
    from app.agent.guardrails import SqlGuardError, execute_readonly, validate_sql

    try:
        safe = validate_sql(args.sql, allowed_bu_ids=ctx.sl.allowed if backend() == "duckdb" else None)
    except SqlGuardError as exc:
        return ToolOutput(tool="run_readonly_sql", ok=False, kind="error", error=f"SQL rejected: {exc}")
    try:
        df = execute_readonly(ctx.sl.engine, safe)
    except Exception as exc:  # noqa: BLE001
        return ToolOutput(tool="run_readonly_sql", ok=False, kind="error", error=f"SQL failed: {exc}")
    facts = [f"Query returned {len(df)} rows; columns: {', '.join(df.columns)}"]
    for _, r in df.head(10).iterrows():
        facts.append("; ".join(f"{c}={F.num(v, 2) if isinstance(v, (int, float, np.floating)) else v}" for c, v in r.items()))
    return ToolOutput(tool="run_readonly_sql", kind="sql", data=_records(df), sql=[safe], facts=facts,
                      filters_used={"org": "per SQL (row-level security applied)", "period": "per SQL",
                                    "currency": CUR, "as_of_date": ctx.as_of.isoformat()},
                      notes=["Fallback free-SQL result over whitelisted views."])


TOOL_DESCRIPTIONS = {
    "resolve_entities": "Resolve org units, metrics, periods and versions mentioned in text (fuzzy).",
    "get_pnl": "General-ledger P&L statement (Billing, WIP, Revenue, Production, costs, Gross profit, Operating profit, "
               "EBIT, Net income) for an org and period, with comparisons (PY, Budget, FCs). "
               "Use for 'how is X doing', overall performance, P&L questions.",
    "get_trend": "Monthly series of a metric or ratio (Actual vs PY vs Budget). Use for trend / over time / since / what happened.",
    "get_ratio": "One ratio for an org and period vs comparisons (e.g. personnel_to_revenue, maop_margin_revenue = operating margin).",
    "variance_drivers": "Explain a variance: drills the account tree and the org children and ranks contributions. "
                        "Use for why / drivers / break down / split questions.",
    "rank_entities": "Rank org units (BU, business, product line, country, region) by a metric or ratio. "
                     "Use for top / bottom / best / worst / 'by product line' questions.",
    "compare_versions": "Actual vs Budget vs FC1/FC2/FC3 for key P&L lines.",
    "get_kpi_cockpit": "Operational profitability cockpit: direct margin, production, direct staff costs, utilization, "
                       "production per hour / per FTE, overtime ratio, hourly cost - MTD and YTD vs LY and Budget.",
    "get_workforce": "Workforce from fictional employee records (closed months, vs prior year): headcount, FTE, hires, "
                     "leavers, attrition, utilization and overtime by role, grade, direct / indirect staff, month or org "
                     "level. Use for attrition / turnover / hires / leavers questions and for headcount or utilization "
                     "by role, grade or staff type.",
    "run_readonly_sql": "FALLBACK ONLY when no other tool fits: one SELECT on the reporting views.",
}

TOOLS: dict[str, tuple[type[BaseModel], Callable]] = {
    "resolve_entities": (ResolveEntitiesArgs, tool_resolve_entities),
    "get_pnl": (GetPnlArgs, tool_get_pnl),
    "get_trend": (GetTrendArgs, tool_get_trend),
    "get_ratio": (GetRatioArgs, tool_get_ratio),
    "variance_drivers": (VarianceDriversArgs, tool_variance_drivers),
    "rank_entities": (RankEntitiesArgs, tool_rank_entities),
    "compare_versions": (CompareVersionsArgs, tool_compare_versions),
    "get_kpi_cockpit": (GetKpiCockpitArgs, tool_get_kpi_cockpit),
    "get_workforce": (GetWorkforceArgs, tool_get_workforce),
    "run_readonly_sql": (RunReadonlySqlArgs, tool_run_readonly_sql),
}


def _register_extra_tools() -> None:
    """Catalog and landing tools live in app.agent.tools_landing (imported last: it imports this module)."""
    from app.agent import tools_landing as TL  # noqa: WPS433

    TOOL_DESCRIPTIONS.update(TL.TOOL_DESCRIPTIONS)
    sql = TOOLS.pop("run_readonly_sql")
    TOOLS.update(TL.TOOLS_EXTRA)
    TOOLS["run_readonly_sql"] = sql                    # keep the SQL fallback last in the planner's list


_register_extra_tools()
DATA_TOOLS = [t for t in TOOLS if t != "resolve_entities"]


def _clean_schema(schema: dict) -> dict:
    schema = dict(schema)
    schema.pop("title", None)
    props = {}
    for k, v in schema.get("properties", {}).items():
        v = {kk: vv for kk, vv in v.items() if kk != "title"}
        props[k] = v
    schema["properties"] = props
    return schema


def openai_tools(names: list[str] | None = None) -> list[dict]:
    names = names or list(TOOLS)
    return [{"type": "function", "function": {"name": n, "description": TOOL_DESCRIPTIONS[n],
                                              "parameters": _clean_schema(TOOLS[n][0].model_json_schema())}}
            for n in names]


def run_tool(name: str, raw_args: dict | None, ctx: ToolContext) -> ToolOutput:
    if name not in TOOLS:
        return ToolOutput(tool=name, ok=False, kind="error", error=f"Unknown tool {name}")
    model, fn = TOOLS[name]
    try:
        args = model.model_validate(raw_args or {})
    except Exception as exc:  # noqa: BLE001
        return ToolOutput(tool=name, ok=False, kind="error", error=f"Invalid arguments: {exc}")
    try:
        out = fn(args, ctx)
        out.meta.setdefault("args", args.model_dump())
        if out.ok and out.facts and not out.bullets:
            out.bullets = make_bullets(out)
        return out
    except Exception as exc:  # noqa: BLE001
        return ToolOutput(tool=name, ok=False, kind="error", error=f"{type(exc).__name__}: {exc}")
