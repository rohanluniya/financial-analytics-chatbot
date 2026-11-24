"""Data catalog: what IRIS covers, read live from the database and metrics.yaml, filtered by the
user's row-level security. Shared by the Data Catalog page and the `describe_catalog` tool.

No numbers are hardcoded: counts, months, ranges and accuracy are computed when asked. P&L lines are
shown by name only (no line numbers or account codes on screen).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.ui import branding as B
from app.config import as_of_date, settings
from app.semantic import time_intel as ti
from app.semantic.access import allowed_bus
from app.semantic.dims import dims
from app.semantic.registry import registry

KINDS = ("regions", "countries", "product_lines", "businesses", "business_units", "accounts", "metrics", "ratios",
         "versions", "periods", "billing_patterns", "capabilities", "example_questions")
KIND_LABEL = {"regions": "Regions", "countries": "Countries", "product_lines": "Product lines",
              "businesses": "Businesses", "business_units": "Business units", "accounts": "P&L lines and accounts",
              "metrics": "Metrics", "ratios": "Ratios", "versions": "Versions", "periods": "Periods",
              "billing_patterns": "Billing patterns", "capabilities": f"What {B.APP_NAME} can do",
              "example_questions": "Example questions"}
KIND_WORDS = [  # first match wins (order matters: "business units" before "businesses")
    ("business_units", r"\b(business units?|bus|bu list|units)\b"), ("businesses", r"\bbusiness(es)?\b"),
    ("product_lines", r"\b(product lines?|pls?|sectors?)\b"), ("countries", r"\bcountr(y|ies)\b"),
    ("regions", r"\bregions?\b"), ("ratios", r"\b(ratios?|margins?)\b"),
    ("accounts", r"\b(accounts?|p&l lines?|ledger lines?|lines)\b"),
    ("metrics", r"\b(metrics?|measures?|kpis?)\b"), ("versions", r"\b(versions?|forecasts?|budgets?)\b"),
    ("periods", r"\b(periods?|months?|calendar|close dates?|closing)\b"),
    ("billing_patterns", r"\b(billing patterns?|patterns?|pattern class(es)?)\b"),
    ("example_questions", r"\b(examples?|example questions|what can i ask|sample questions)\b"),
    ("capabilities", r"\b(what can you do|capabilit\w*|help|what do you (do|know|cover)|what data|which data|how do i use)\b"),
]
LEVEL_OF_KIND = {"regions": "l2_region", "countries": "l3_country", "product_lines": "l4_product_line",
                 "businesses": "l5_business", "business_units": "l6_bu"}
VERSION_TEXT = {
    "Actual": "Booked results of closed months (a month closes on the 5th of the following month).",
    "Budget": "Annual plan set before the year starts.",
    "FC1": "First reforecast: actuals for January-April plus a reforecast of the remaining months.",
    "FC2": "Second reforecast: actuals for January-August plus a reforecast of the remaining months.",
    "FC3": "Third reforecast: actuals for January-September plus a reforecast of the remaining months.",
}
PERIOD_TYPES = [("Month", "One calendar month", "October 2026"), ("QTD", "Quarter to date", "QTD Oct 2026"),
                ("YTD", "Year to date", "YTD Oct 2026"), ("Rolling 12M", "Last twelve months", "R12M to Oct 2026"),
                ("Full year", "January to December", "FY 2025"), ("Quarter", "A full quarter", "Q3 2026"),
                ("Range", "Any span of months", "Jan 2025 - Jun 2026")]
PATTERN_TEXT = {
    "steady": "Billing spread evenly through the year with mild seasonality.",
    "quarter_end": "A large share of billing in March, June, September and December.",
    "year_end": "A large share of billing in December (annual fees and audits).",
    "seasonal": "Clear seasonal shape: a March peak and an August dip.",
    "lumpy": "Project billing: large, irregular months; the widest landing ranges.",
}
CAPABILITIES = [
    ("Performance against budget, prior year and forecasts", "How is operating profit YTD vs last year and budget for the United States?"),
    ("Both operating margins", "What is our profit % this year?"),
    ("Trends over time", "Show revenue by month since 2024 for Canada"),
    ("Why something changed (drivers)", "Why did Canada Environmental Lab Testing operating profit drop vs last year?"),
    ("Rankings and comparisons", "Which 5 BUs have the lowest operating margin on revenue YTD?"),
    ("Budget and forecast versions", "Compare budget, FC2 and FC3 for Mexico this year"),
    ("Drill-down to accounts and business units", "Break down personnel costs for US Elevators & Pressure Vessels"),
    ("Current-month landing with a P10-P90 range", "What's the November landing for the United States?"),
    ("YTD and full year including the landing", "What will YTD MAOP margin be through November including the landing?"),
    ("Workforce from fictional employee records", "What is the attrition rate by role in Canada Environmental Lab Testing?"),
    ("Discovery: what is in scope", "Which businesses can I ask about?"),
]
EXAMPLES = [  # intent, question (the Americas; shared with the User Guide gallery)
    ("Performance", "How is operating profit YTD vs last year and budget for the United States?"),
    ("Performance", "How is Canada doing this year?"),
    ("Margins", "What is our profit % YTD?"),
    ("Margins", "Operating margin on production for US & Canada vs budget"),
    ("Trends", "Show revenue by month since 2024 for Mexico"),
    ("Drivers", "Why did Canada Environmental Lab Testing operating profit drop vs last year?"),
    ("Rankings", "Which 5 BUs have the lowest operating margin on revenue YTD?"),
    ("Versions", "Compare budget, FC2 and FC3 for Mexico this year"),
    ("Drill-down", "Break down personnel costs for US Elevators & Pressure Vessels"),
    ("Landing", "What's the November landing for the United States?"),
    ("Landing", "Which BUs are expected to miss budget this month?"),
    ("Landing", "What will YTD MAOP margin be through November including the landing?"),
    ("Discovery", "Which countries are in scope?"),
    ("Discovery", "What ratios do you support?"),
    ("Follow-ups", "now for Mexico"),
    ("Follow-ups", "how does that compare with last year?"),
]


@dataclass
class CatalogResult:
    kind: str
    title: str
    df: pd.DataFrame
    description: str
    followups: list[str] = field(default_factory=list)
    chart: dict | None = None


def visible_org(user_id: str, parent_filter: dict | None = None) -> pd.DataFrame:
    org = dims().org
    org = org[org["bu_id"].isin(allowed_bus(user_id))]
    for level, values in (parent_filter or {}).items():
        org = org[org[level].isin(values)]
    return org


def close_calendar(as_of: date | None = None) -> dict:
    as_of = as_of or as_of_date()
    last = ti.last_closed_month(as_of)
    open_key = ti.add_months(last, 1)
    y, m = ti.ym(open_key)
    return {"as_of": as_of, "first_month": ti.data_bounds()[0], "last_closed": last, "open_month": open_key,
            "next_close": ti.close_date(y, m), "close_day": int(settings()["close_day_of_next_month"])}


def _line_rows() -> pd.DataFrame:
    reg = registry()
    acc = dims().account
    rows = []
    for m in reg.metrics.values():
        if m.kind != "line" or m.subtotal:
            continue
        subs = acc[(acc["line_no"] == m.line) & (acc["is_leaf"].astype(bool))]["l3_name"].tolist()
        rows.append({"P&L line": m.name, "Accounts": ", ".join(s for s in subs if s != m.name) or "-",
                     "Sign": "Revenue / income" if m.natural_sign > 0 else "Cost",
                     "Favourable when": "higher" if m.favorable == "up" else "lower",
                     "Also understood as": ", ".join(list(m.synonyms)[:4])})
    return pd.DataFrame(rows)


def _formula_words(m) -> str:
    reg = registry()
    if m.kind == "line" and m.subtotal:
        parts = [next(x.name for x in reg.metrics.values() if x.kind == "line" and x.line == p) for p in m.formula]
        return " + ".join(parts)
    if m.kind == "group":
        return "Sum of its accounts"
    if m.kind == "computed":
        return {"direct_margin_amount": "Production - Direct staff costs",
                "direct_margin_incl_subc_amount": "Production - Direct staff costs - External subcontracting"}.get(m.id, "")
    if m.kind == "stat":
        return "Average over the months" if m.agg == "avg" else "Sum over the months"
    return "Booked amount"


def _metric_rows() -> pd.DataFrame:
    reg = registry()
    rows = []
    for m in reg.metrics.values():
        if m.kind in ("leaf",):
            continue
        kind = {"line": "Subtotal" if m.subtotal else "P&L line", "group": "Account group", "computed": "Amount",
                "stat": "Statistic"}[m.kind]
        rows.append({"Metric": m.name, "Type": kind, "Definition": _formula_words(m),
                     "Favourable when": {"up": "higher", "down": "lower"}.get(m.favorable, "-"),
                     "Also understood as": ", ".join(list(m.synonyms)[:4])})
    return pd.DataFrame(rows)


def ratio_rows(user_id: str | None = None, typical: bool = True) -> pd.DataFrame:
    """Ratios with the formula in words and, when available, the typical range by business type."""
    reg = registry()
    rows = []
    rng = typical_ranges(user_id) if (typical and user_id) else {}
    for r in reg.ratios.values():
        num, den = reg.metrics[r.num], reg.metrics[r.den]
        unit = "%" if r.fmt == "pct" else f"{settings().get('currency', 'USD')}"
        row = {"Ratio": r.name, "Formula": f"{num.name} / {den.name}" + (" x 12 (annualised)" if r.annualize else ""),
               "Unit": unit, "Favourable when": {"up": "higher", "down": "lower"}.get(r.favorable, "-")}
        if rng:
            row["Typical range (middle half of BUs, last 12 months)"] = rng.get(r.id, "-")
        row["Also understood as"] = ", ".join(list(r.synonyms)[:3])
        rows.append(row)
    pair = reg.pairs.get("operating_margins")
    if pair:
        rows.append({"Ratio": "Profit % / margin (no base given)", "Formula": "Shows both operating margins side by side",
                     "Unit": "%", "Favourable when": "higher",
                     **({"Typical range (middle half of BUs, last 12 months)": "-"} if rng else {}),
                     "Also understood as": ", ".join(list(pair.synonyms)[:5])})
    return pd.DataFrame(rows)


def typical_ranges(user_id: str) -> dict[str, str]:
    """Interquartile range of each percentage ratio across the user's BUs over the last 12 closed months,
    by business type, e.g. 'laboratory 9.8%-14.1%; inspection 6.2%-9.0%'."""
    from app.semantic.query_builder import SemanticLayer  # noqa: WPS433

    sl = SemanticLayer(user_id)
    last = ti.last_closed_month(sl.as_of)
    months = ti.month_range(ti.add_months(last, -11), last)
    s = ti.Series("Actual", "Actual", ti.Period("R12M", last), tuple(months))
    w = sl.frame([s], {}, ["l6_bu"], with_stats=True)
    if w.empty:
        return {}
    btype = dims().org.set_index("l6_bu")["business_type"]
    w = w.assign(btype=w["l6_bu"].map(btype))
    out = {}
    for r in sl.reg.ratios.values():
        if r.fmt != "pct":
            continue
        try:
            v = sl.value(w, "ratio", r)
        except Exception:  # noqa: BLE001
            continue
        parts = []
        for bt, grp in pd.Series(v.values, index=w["btype"]).groupby(level=0):
            g = grp.dropna()
            if len(g) >= 3:
                lo, hi = np.quantile(g, [0.25, 0.75])
                parts.append(f"{bt} {100 * lo:.1f}%-{100 * hi:.1f}%")
        out[r.id] = "; ".join(parts) if parts else "-"
    return out


def describe(kind: str, user_id: str, parent_filter: dict | None = None, as_of: date | None = None,
             engine=None) -> CatalogResult:
    kind = kind if kind in KINDS else "capabilities"
    org = visible_org(user_id, parent_filter)
    scope_note = ""
    if parent_filter:
        from app.semantic.entity_resolver import org_label  # noqa: WPS433
        scope_note = f" within {org_label(parent_filter)}"
    cal = close_calendar(as_of)
    if kind in LEVEL_OF_KIND:
        lvl = LEVEL_OF_KIND[kind]
        g = org.groupby(lvl)
        if kind == "regions":
            df = g.agg(Countries=("l3_country", "nunique"), Businesses=("l5_business", "nunique"),
                       BUs=("bu_id", "nunique")).reset_index().rename(columns={lvl: "Region"})
        elif kind == "countries":
            df = g.agg(Region=("l2_region", "first"), **{"Product lines": ("l4_product_line", "nunique")},
                       Businesses=("l5_business", "nunique"), BUs=("bu_id", "nunique")).reset_index().rename(
                columns={lvl: "Country"})
        elif kind == "product_lines":
            df = g.agg(**{"Business type": ("business_type", "first")}, Countries=("l3_country", "nunique"),
                       Businesses=("l5_business", "nunique"), BUs=("bu_id", "nunique")).reset_index().rename(
                columns={lvl: "Product line"})
        elif kind == "businesses":
            df = g.agg(**{"Product line": ("l4_product_line", "first")}, Country=("l3_country", "first"),
                       BUs=("bu_id", "nunique")).reset_index().rename(columns={lvl: "Business"})
        else:
            df = org[["l6_bu", "l5_business", "l4_product_line", "l3_country", "city"]].rename(columns={
                "l6_bu": "BU", "l5_business": "Business", "l4_product_line": "Product line", "l3_country": "Country",
                "city": "City"})
            pats = pattern_classes(user_id, engine)
            if pats:
                df["Billing pattern"] = df["BU"].map(pats).map(lambda k: PATTERN_LABELS.get(k, "-") if isinstance(k, str) else "-")
        df = df.sort_values(df.columns[0]).reset_index(drop=True)
        n = len(df)
        name = KIND_LABEL[kind].lower()
        singular = {"regions": "region", "countries": "country", "product_lines": "product line",
                    "businesses": "business", "business_units": "business unit"}[kind]
        desc = (f"{n} {name if n != 1 else singular} in your scope{scope_note}, with monthly P&L from "
                f"{ti.month_label(cal['first_month'])} to {ti.month_label(cal['last_closed'])} "
                f"(the last closed month).")
        first = str(df.iloc[0, 0]) if n else ""
        fu = [f"How is {first} doing YTD vs budget?" if first else "How are we doing YTD vs budget?",
              f"Rank {name} by operating margin on revenue YTD",
              f"What's the {ti.MONTH_NAMES[cal['open_month'] % 100 - 1]} landing for {first}?" if first else
              "What's the landing this month?"]
        chart = {"type": "hbar", "title": f"BUs by {KIND_LABEL[kind].rstrip('s').lower()}", "fmt": "count",
                 "x": "value", "y": ["label"], "data": [{"label": str(r[df.columns[0]]), "value": r["BUs"], "fav": None}
                                                     for _, r in df.iterrows()] if "BUs" in df.columns else [],
                 "meta": {}} if "BUs" in df.columns and 1 < n <= 30 else None
        return CatalogResult(kind, KIND_LABEL[kind], df, desc, fu, chart)
    if kind == "accounts":
        df = _line_rows()
        return CatalogResult(kind, KIND_LABEL[kind], df,
                             f"{len(df)} P&L lines from billing to net income; subtotals (revenue, production, gross "
                             "profit, operating profit, EBIT, net income) are computed from the accounts, never stored.",
                             ["Show the P&L for the United States YTD", "Break down other costs for Mexico",
                              "Personnel costs by month since 2025"])
    if kind == "metrics":
        df = _metric_rows()
        return CatalogResult(kind, KIND_LABEL[kind], df,
                             f"{len(df)} metrics: P&L lines and subtotals, account groups, amounts and statistics. "
                             "Costs are shown as positive amounts in answers; favourability follows the sign.",
                             ["How is operating profit YTD vs budget?", "Show production by month since 2024",
                              "What ratios do you support?"])
    if kind == "ratios":
        df = ratio_rows(user_id)
        return CatalogResult(kind, KIND_LABEL[kind], df,
                             f"{len(df) - 1} ratios plus 'profit %' (both operating margins). Aggregates are always a "
                             "ratio of sums; a zero or negative denominator shows n/a.",
                             ["What is our profit % YTD?", "Operating margin on production by country",
                              "Personnel costs as % of revenue trend since 2024"])
    if kind == "versions":
        rows = []
        for v in dims().version.itertuples():
            yrs = [y for y in range(ti.data_bounds()[0] // 100, ti.data_bounds()[1] // 100 + 1)
                   if v.name in ("Actual", "Budget") or ti.forecast_available(v.name, y, cal["as_of"])]
            rows.append({"Version": v.name, "What it is": VERSION_TEXT.get(v.name, ""),
                         "Available for": f"{yrs[0]}-{yrs[-1]}" if yrs else "-"})
        rows.append({"Version": "Latest forecast", "What it is": "The newest of FC3, FC2, FC1 published for the year "
                     "(else the Budget).", "Available for": f"{ti.latest_forecast(cal['open_month'] // 100, cal['as_of']) or 'Budget'} "
                     f"for {cal['open_month'] // 100}"})
        rows.append({"Version": "Landing", "What it is": "Expected month-end of the open month (P50 with a P10-P90 "
                     "range), computed by the landing engine from monthly history; WIP = 0, so revenue = billing.",
                     "Available for": ti.month_label(cal["open_month"])})
        return CatalogResult(kind, KIND_LABEL[kind], pd.DataFrame(rows),
                             "Actuals for closed months, the Budget, three reforecasts and the current-month landing.",
                             ["Compare budget, FC2 and FC3 for the group this year",
                              f"What's the {ti.MONTH_NAMES[cal['open_month'] % 100 - 1]} landing?",
                              "Operating profit vs latest forecast YTD"])
    if kind == "periods":
        df = pd.DataFrame(PERIOD_TYPES, columns=["Period type", "Meaning", "Example"])
        desc = (f"Monthly data from {ti.month_label(cal['first_month'])}. Last closed month "
                f"{ti.month_label(cal['last_closed'])}; months close on day {cal['close_day']} of the following month; "
                f"the open month is {ti.month_label(cal['open_month'])} (landing month), which closes on "
                f"{cal['next_close'].isoformat()}.")
        return CatalogResult(kind, KIND_LABEL[kind], df, desc,
                             ["How is revenue QTD vs budget?", "Operating profit R12M by region",
                              "Revenue YTD till November with landing vs budget"])
    if kind == "billing_patterns":
        pats = pattern_classes(user_id, engine)
        counts = pd.Series([pats.get(b) for b in org["l6_bu"]]).value_counts().to_dict() if pats else {}
        acc = pattern_accuracy(engine)
        rows = [{"Pattern": PATTERN_LABELS[k], "What it means": PATTERN_TEXT[k], "BUs in your scope": counts.get(k, 0),
                 "Landing backtest error (BU billing WAPE)": acc.get(k, "not measured yet")} for k in PATTERN_TEXT]
        return CatalogResult(kind, KIND_LABEL[kind], pd.DataFrame(rows),
                             "Each BU's billing pattern is classified from its own history by the landing engine; the "
                             "error column is measured by `make backtest`.",
                             ["Which BUs are expected to miss budget this month?",
                              "Explain the landing for US Buildings & Infrastructure",
                              "What's the November landing for the United States?"])
    if kind == "example_questions":
        return CatalogResult(kind, KIND_LABEL[kind], pd.DataFrame(EXAMPLES, columns=["Intent", "Example question"]),
                             "Good questions name a measure, a scope, a period and a comparison. Click one to try it.",
                             [q for _, q in EXAMPLES[:3]])
    df = pd.DataFrame(CAPABILITIES, columns=["Capability", "Example question"])
    desc = (f"{B.APP_NAME} answers questions about the monthly management P&L by organisation (group to business unit), "
            f"Actual, Budget and three forecasts from {ti.month_label(cal['first_month'])} to "
            f"{ti.month_label(cal['last_closed'])}, plus the {ti.month_label(cal['open_month'])} landing. "
            "Every answer shows the figures used, a table and a chart; numbers come from governed definitions, "
            "never from the language model.")
    return CatalogResult("capabilities", KIND_LABEL["capabilities"], df, desc,
                         ["Which countries are in scope?", "List all metrics", "What's the landing this month?"])


PATTERN_LABELS = {"steady": "Steady", "quarter_end": "Quarter-end loaded", "year_end": "Year-end loaded",
                  "seasonal": "Seasonal (March peak, August dip)", "lumpy": "Lumpy (project billing)"}


def pattern_classes(user_id: str, engine=None) -> dict[str, str]:
    """BU name -> billing pattern class from the latest landing profile (empty if no landing run)."""
    try:
        from app.landing.query import bu_profiles  # noqa: WPS433
        from app.semantic.query_builder import SemanticLayer  # noqa: WPS433

        df = bu_profiles(SemanticLayer(user_id))
    except Exception:  # noqa: BLE001
        return {}
    if df is None or df.empty:
        return {}
    return dict(zip(df["l6_bu"], df["pattern_class"]))


def pattern_accuracy(engine=None) -> dict[str, str]:
    try:
        from app.db import get_engine  # noqa: WPS433
        from app.landing.query import backtest_metrics  # noqa: WPS433

        m = backtest_metrics(engine or get_engine(admin=False, user_id="__catalog__"))
    except Exception:  # noqa: BLE001
        return {}
    m = m[(m.scope_type == "pattern_class") & (m.measure == "billing") & (m.metric == "wape") & (m.method == "ensemble")]
    return {r.scope_value: f"{100 * r.value:.1f}% ({r.n} BU-months)" for r in m.itertuples() if r.value == r.value}


def kind_from_text(text: str) -> str:
    import re  # noqa: WPS433

    t = (text or "").lower()
    for kind, rx in KIND_WORDS:
        if re.search(rx, t):
            return kind
    return "capabilities"


# ------------------------------------------------------------------------------------------
# Data Catalog page and docs/data_manual.md (same functions, so the page and the manual agree)
# ------------------------------------------------------------------------------------------
LINEAGE_DOT = """
digraph {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#E6F4F1", color="#0F766E", fontname="Helvetica", fontsize=10];
  edge [color="#3730A3", fontsize=9];
  gen [label="Synthetic data generator\\n(seeded, monthly)"];
  pq [label="Parquet files\\n(data/)"];
  db [label="SQL Server 2022 / DuckDB\\nleaf accounts only,\\nrow-level security"];
  sem [label="Semantic layer\\n(metrics.yaml: subtotals,\\nratios, versions)"];
  land [label="Landing engine\\n(make landing,\\nmonthly history only)"];
  fl [label="fact_landing\\n(P10 / P50 / P90)"];
  tools [label="Agent tools\\n(governed queries)"];
  ans [label="Answer: text,\\ntable, chart", fillcolor="#EEF0FB", color="#3730A3"];
  gen -> pq -> db -> sem -> tools -> ans;
  db -> land -> fl -> sem;
}
"""
ASSUMPTIONS = [
    "Synthetic data generated for this prototype; structure mirrors the target model.",
    "One currency (USD) at a constant budget exchange rate.",
    "Only leaf accounts are stored; every subtotal and ratio is computed by the semantic layer, so totals "
    "always reconcile.",
    "A month closes on day {close_day} of the following month; the month after the last closed month is the "
    "open (landing) month.",
    "Budget is set before the year; FC1, FC2 and FC3 carry 4, 8 and 9 months of actuals plus a reforecast.",
    "The landing has WIP = 0 in the landing month (revenue = billing) and uses monthly history only.",
    "Employee records are fictional codes without names or personal attributes.",
]
REFRESH_TEXT = ("Actuals: monthly, after the close on day {close_day} of the following month. Budget: once a "
                "year. Forecasts: three times a year. Landing: `make landing` (daily in production, for example "
                "with the optional private CronJob).")


def landing_refresh(user_id: str):
    """Last landing run (Snapshot) or None."""
    try:
        from app.db import get_engine  # noqa: WPS433
        from app.landing.query import last_refresh  # noqa: WPS433

        return last_refresh(get_engine(user_id))
    except Exception:  # noqa: BLE001
        return None


def coverage(user_id: str, as_of: date | None = None) -> dict:
    """Counts and calendar facts for the coverage cards (RLS-filtered)."""
    org = visible_org(user_id)
    cal = close_calendar(as_of)
    acc = dims().account
    lines = [m for m in registry().metrics.values() if m.kind == "line" and not m.subtotal]
    snap = landing_refresh(user_id)
    return {"regions": int(org["l2_region"].nunique()), "countries": int(org["l3_country"].nunique()),
            "product_lines": int(org["l4_product_line"].nunique()), "businesses": int(org["l5_business"].nunique()),
            "bus": int(org["bu_id"].nunique()), "accounts": int(acc["is_leaf"].astype(bool).sum()),
            "lines": len(lines), **cal, "landing": snap}


def org_table(user_id: str) -> pd.DataFrame:
    org = visible_org(user_id)
    cols = {"l2_region": "Region", "l3_country": "Country", "l4_product_line": "Product line",
            "l5_business": "Business", "l6_bu": "BU", "city": "City", "business_type": "Business type"}
    return org[list(cols)].rename(columns=cols).sort_values(["Region", "Country", "Product line", "BU"]).reset_index(drop=True)


def bu_heatmap(user_id: str) -> pd.DataFrame:
    """Number of BUs by country (rows) and product line (columns)."""
    org = visible_org(user_id)
    return org.pivot_table(index="l3_country", columns="l4_product_line", values="bu_id", aggfunc="nunique").fillna(0).astype(int)


def revenue_heatmap(user_id: str, as_of: date | None = None) -> pd.DataFrame:
    """Revenue YTD (last closed month) by country and product line, through the semantic layer (RLS applies)."""
    from app.semantic.query_builder import SemanticLayer  # noqa: WPS433

    sl = SemanticLayer(user_id, as_of)
    last = ti.last_closed_month(sl.as_of)
    per = ti.Period("YTD", last)
    w = sl.frame([ti.Series("Actual", "Actual", per, tuple(per.months()))], {}, ["l3_country", "l4_product_line"])
    if w.empty:
        return pd.DataFrame()
    w = w.assign(value=sl.value(w, "metric", sl.reg.metrics["revenue"]).values)
    return w.pivot_table(index="l3_country", columns="l4_product_line", values="value", aggfunc="sum")


def version_row_counts(user_id: str) -> pd.DataFrame:
    """Stored P&L rows per version and the months they cover (only rows the user may see)."""
    from sqlalchemy import func, select  # noqa: WPS433

    from app.config import backend  # noqa: WPS433
    from app.db import fact_pnl, get_engine  # noqa: WPS433
    from app.db import dim_version as dv  # noqa: WPS433

    stmt = (select(dv.c.name, func.count().label("n"), func.min(fact_pnl.c.month_key).label("m0"),
                   func.max(fact_pnl.c.month_key).label("m1"))
            .select_from(fact_pnl.join(dv, fact_pnl.c.version_id == dv.c.version_id)))
    if backend() == "duckdb":                       # SQL Server applies the RLS policy itself
        stmt = stmt.where(fact_pnl.c.bu_id.in_(sorted(allowed_bus(user_id))))
    stmt = stmt.group_by(dv.c.name)
    with get_engine(user_id).connect() as conn:
        rows = conn.execute(stmt).all()
    order = {v: i for i, v in enumerate(["Actual", "Budget", "FC1", "FC2", "FC3"])}
    df = pd.DataFrame([{"Version": r.name, "Rows": int(r.n), "From": ti.month_label(int(r.m0)),
                        "To": ti.month_label(int(r.m1))} for r in rows])
    return df.sort_values("Version", key=lambda s: s.map(order)).reset_index(drop=True) if not df.empty else df


def reconcile_status() -> dict | None:
    """Result of the last `make reconcile` (results/reconcile_report_<backend>.md), or None."""
    import re  # noqa: WPS433
    from datetime import datetime  # noqa: WPS433

    from app.config import ROOT, backend  # noqa: WPS433

    p = ROOT / "results" / f"reconcile_report_{backend()}.md"
    if not p.exists():
        return None
    text = p.read_text()
    m = re.search(r"\*\*Mismatches: (\d+)\*\* \(subtotal checks: (\d+)\), integrity check failures: (\d+)", text)
    if not m:
        return None
    return {"mismatches": int(m.group(1)), "checks": int(m.group(2)), "integrity_failures": int(m.group(3)),
            "run_at": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}


def close_schedule(as_of: date | None = None, months_back: int = 6, months_ahead: int = 3) -> pd.DataFrame:
    cal = close_calendar(as_of)
    rows = []
    for k in ti.month_range(ti.add_months(cal["last_closed"], -months_back + 1), ti.add_months(cal["open_month"], months_ahead)):
        y, m = ti.ym(k)
        status = "Closed" if k <= cal["last_closed"] else ("Open (landing month)" if k == cal["open_month"] else "Future")
        rows.append({"Month": ti.month_label(k), "Closes on": ti.close_date(y, m).isoformat(), "Status": status})
    return pd.DataFrame(rows)


def backtest_tables(user_id: str) -> dict[str, pd.DataFrame]:
    """Measured landing accuracy from the latest `make backtest` run (empty dict if none)."""
    try:
        from app.db import get_engine  # noqa: WPS433
        from app.landing import engine as LE  # noqa: WPS433
        from app.landing.query import backtest_metrics  # noqa: WPS433

        m = backtest_metrics(get_engine(user_id))
    except Exception:  # noqa: BLE001
        return {}
    if m.empty:
        return {}
    label = LE.METHOD_LABEL
    out = {"run_date": pd.Timestamp(m["run_date"].iloc[0]).date().isoformat()}
    g = m[(m.scope_type == "group") & (m.metric == "wape")]
    if not g.empty:
        piv = g.pivot_table(index="method", columns="measure", values="value", aggfunc="first")
        keep = [c for c in ("billing", "revenue", "maop_xw", "maop") if c in piv.columns]
        piv = (100 * piv[keep]).round(2).rename(columns={"billing": "Billing WAPE %", "revenue": "Revenue WAPE %",
                                                           "maop_xw": "Operating profit WAPE % (excl. WIP)",
                                                           "maop": "Operating profit WAPE % (as booked)"})
        piv.index = [label.get(i, i) for i in piv.index]
        out["group"] = piv.reset_index().rename(columns={"index": "Method"})
    cov = m[(m.scope_type == "org_level") & (m.measure == "billing") & (m.method == "ensemble")
            & (m.metric.str.startswith("coverage"))]
    if not cov.empty:
        out["coverage"] = pd.DataFrame({"Organisation level": cov.scope_value,
                                        "Actual inside P10-P90 %": (100 * cov.value).round(1).values,
                                        "Months x units": cov.n.values})
    pc = m[(m.scope_type == "pattern_class") & (m.measure == "billing") & (m.metric == "wape")
           & (m.method.isin(["ensemble", LE.BASELINE]))]
    if not pc.empty:
        piv = (100 * pc.pivot_table(index="scope_value", columns="method", values="value", aggfunc="first")).round(1)
        piv = piv.rename(columns={"ensemble": f"{B.APP_NAME} landing WAPE %", LE.BASELINE: "Latest forecast WAPE %"})
        piv.index = [LE.CLASS_LABEL.get(i, i) for i in piv.index]
        out["pattern"] = piv.reset_index().rename(columns={"index": "Billing pattern"})
    pl = m[(m.scope_type == "product_line") & (m.measure == "billing") & (m.metric == "wape")
           & (m.method.isin(["ensemble", LE.BASELINE]))]
    if not pl.empty:
        piv = (100 * pl.pivot_table(index="scope_value", columns="method", values="value", aggfunc="first")).round(1)
        out["product_line"] = piv.rename(columns={"ensemble": f"{B.APP_NAME} landing WAPE %",
                                                  LE.BASELINE: "Latest forecast WAPE %"}).reset_index().rename(
            columns={"scope_value": "Product line"})
    return out


LANDING_METHOD_TEXT = """\
The landing is the expected month-end result of the open month, computed by a separate, tested Python engine
(never by the language model) from monthly data only: closed-month actuals, the Budget and the forecasts.

1. Each BU's billing history is profiled (seasonal index, quarter-end and December share, volatility) and
   classified as steady, quarter-end loaded, year-end loaded, seasonal or lumpy.
2. Four methods forecast billing, all adjusted for working days: same month last year x recent growth;
   trailing 12 months x seasonal index; latest forecast x the BU's historical forecast accuracy; and
   exponential smoothing.
3. The methods are combined with weights learned from each method's recent errors, shrunk toward the
   weights of the BU's pattern class.
4. P10 and P90 come from the engine's own past errors; group and other totals use a 1,000-draw simulation.
5. Costs follow the billing landing (ratios to billing, a personnel run-rate, functional lines from the latest
   forecast). WIP is 0 in the landing month, so the revenue landing equals the billing landing.
6. BU results add up exactly to every higher level; margins are ratios of sums.
"""


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df is None or len(df) == 0:
        return "_No rows._\n"
    d = df.head(max_rows) if max_rows else df
    cols = [str(c) for c in d.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in d.iterrows():
        out.append("| " + " | ".join(_cell(v) for v in r.values) + " |")
    if max_rows and len(df) > max_rows:
        out.append(f"\n_{len(df) - max_rows} more rows in the Data Catalog page._")
    return "\n".join(out) + "\n"


def _cell(v) -> str:
    if isinstance(v, float):
        return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"
    return str(v).replace("|", "/")


def data_manual_markdown(user_id: str = "group_cfo", as_of: date | None = None) -> str:
    """docs/data_manual.md: the Data Catalog content as one document (full group scope by default)."""
    cov = coverage(user_id, as_of)
    snap = cov["landing"]
    rec = reconcile_status()
    close_day = cov["close_day"]
    lines = [f"# {B.APP_NAME} data manual", "",
             "Generated from the live database and `app/semantic/metrics.yaml` by `make data-manual`; the Data "
             "Catalog page shows the same content, filtered by each user's access. "
             "Synthetic data generated for this prototype; structure mirrors the target model.", "",
             "## Coverage", "",
             f"- Organisation: {cov['regions']} regions, {cov['countries']} countries, {cov['product_lines']} product "
             f"lines, {cov['businesses']} businesses, {cov['bus']} business units (BUs).",
             f"- P&L: {cov['lines']} P&L lines over {cov['accounts']} leaf accounts, monthly, in USD.",
             f"- Months: {ti.month_label(cov['first_month'])} to {ti.month_label(cov['last_closed'])} (last closed "
             f"month, as of {cov['as_of'].isoformat()}); the next close is {cov['next_close'].isoformat()}.",
             f"- Landing month: {ti.month_label(cov['open_month'])}; last landing refresh: "
             + (f"{snap.run_at:%Y-%m-%d %H:%M} (as of {snap.snapshot_date.isoformat()})." if snap and snap.run_at
                else "not computed yet."), ""]
    lines += ["## Organisation", "", _md_table(describe("regions", user_id, as_of=as_of).df), "",
              _md_table(describe("countries", user_id, as_of=as_of).df), "",
              _md_table(describe("product_lines", user_id, as_of=as_of).df), ""]
    lines += ["## P&L lines and accounts", "", "Names only; subtotals are computed from the accounts.", "",
              _md_table(_line_rows()), "", "## Metrics", "", _md_table(_metric_rows()), ""]
    lines += ["## Ratios", "", "Aggregates are always a ratio of sums; a zero or negative denominator shows n/a. "
              "'Profit %' or 'margin' without a base returns both operating margins.", "",
              _md_table(ratio_rows(user_id)), ""]
    lines += ["## Versions and periods", "", _md_table(describe("versions", user_id, as_of=as_of).df), "",
              _md_table(describe("periods", user_id, as_of=as_of).df), "", "### Close calendar", "",
              _md_table(close_schedule(as_of)), ""]
    bt = backtest_tables(user_id)
    lines += ["## Landing", "", LANDING_METHOD_TEXT, "", _md_table(describe("billing_patterns", user_id, as_of=as_of).df), ""]
    if bt:
        lines += [f"### Measured backtest accuracy (run {bt['run_date']})", "",
                  "Measured by `make backtest` over the last 24 closed months; see docs/landing_backtest_report.md.", ""]
        for key, title in (("group", "Group level, by method"), ("coverage", "P10-P90 coverage by organisation level"),
                           ("pattern", "BU billing by pattern class")):
            if key in bt:
                lines += [f"**{title}**", "", _md_table(bt[key]), ""]
    else:
        lines += ["No backtest has been run yet (`make backtest`).", ""]
    lines += ["## Data and sources", "",
              "- Storage: leaf accounts only, monthly, one currency (USD); subtotals and ratios are computed by the "
              "semantic layer from `metrics.yaml`.",
              "- Refresh: " + REFRESH_TEXT.format(close_day=close_day),
              "- Lineage: generator -> Parquet -> SQL Server 2022 (or DuckDB) -> semantic layer -> agent tools -> "
              "answer; the landing engine reads the same database and writes `fact_landing`.",
              "- Reconciliation: " + (f"last `make reconcile` on {rec['run_at']}: {rec['mismatches']} mismatches in "
                                      f"{rec['checks']} subtotal checks, {rec['integrity_failures']} integrity failures."
                                      if rec else "not run yet."), "", "### Rows per version", "",
              _md_table(version_row_counts(user_id)), "", "### Assumptions", ""]
    lines += [f"- {a.format(close_day=close_day)}" for a in ASSUMPTIONS] + [""]
    lines += [f"## What {B.APP_NAME} can do", "", _md_table(pd.DataFrame(CAPABILITIES, columns=["Capability", "Example question"])), ""]
    return "\n".join(lines)
