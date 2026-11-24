"""Semantic query builder.

All numbers come from SQLAlchemy Core queries (identical on SQL Server and DuckDB) aggregated
at leaf-account level, then pivoted into a "wide" frame where every P&L line, subtotal, account
group and statistic is a column. The LLM never does arithmetic: every figure it sees is produced
here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import Integer, case, cast, distinct, func, select

from app.config import as_of_date, backend, settings
from app.db import dim_employee, dim_org, dim_version, fact_employee_month, fact_pnl, fact_stats, get_engine
from app.semantic import time_intel as ti
from app.semantic.access import allowed_bus, bus_for_filter, child_level, level_label
from app.semantic.dims import dims
from app.semantic.entity_resolver import ORG_LEVELS, org_label
from app.semantic.registry import MetricDef, RatioDef, registry

CURRENCY = settings().get("currency", "USD")
FX_RATE_CODE = str(settings().get("fx_rate_label", "constant budget rate"))
KEY_LINES = ["production", "revenue", "personnel", "subcontracting", "other_cost", "functional_cost",
             "gross_profit", "maop", "management_op", "net_income"]

# Workforce (fictional employee records): groupings and the main figures a question can ask for
WF_GROUPS = {"role": "Role", "grade": "Grade", "staff_type": "Staff type", "month": "Month"}
WF_METRICS = {   # id -> (column in the workforce table, display name, format, favourable direction)
    "headcount": ("Avg headcount", "Average headcount", "num", "neutral"),
    "fte": ("Avg FTE", "Average FTE", "num", "neutral"),
    "hires": ("Hires", "Hires", "count", "neutral"),
    "leavers": ("Leavers", "Leavers", "count", "down"),
    "restructuring_leavers": ("of which restructuring", "Restructuring leavers", "count", "down"),
    "attrition": ("Attrition", "Attrition rate (annualised)", "pct", "down"),
    "voluntary_attrition": ("Voluntary attrition", "Voluntary attrition rate (annualised)", "pct", "down"),
    "utilization": ("Utilization", "Utilization rate (direct staff, billable / available hours)", "pct", "up"),
    "overtime": ("Overtime ratio", "Overtime ratio (direct staff, overtime / available hours)", "pct", "down"),
}


@dataclass
class Result:
    kind: str                                   # pnl | trend | ratio | drivers | ranking | versions
    df: pd.DataFrame
    meta: dict = field(default_factory=dict)
    sql: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    filters: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


def add_lines(w: pd.DataFrame, leaf_codes: list[str], line_of: dict, group_of: dict,
              formulas: dict[int, tuple[int, ...]], computed=()) -> pd.DataFrame:
    """Add line totals (L1..L21), account groups (7A/7B), subtotals and computed amounts."""
    for c in leaf_codes:
        if c not in w.columns:
            w[c] = 0.0
    new = {}
    for ln in sorted(set(line_of.values())):
        new[f"L{ln}"] = w[[c for c in leaf_codes if line_of[c] == ln]].sum(axis=1)
    for g in ("7A", "7B"):
        new[g] = w[[c for c in leaf_codes if group_of[c] == g]].sum(axis=1)
    w = pd.concat([w, pd.DataFrame(new, index=w.index)], axis=1)
    for ln in sorted(formulas):
        w[f"L{ln}"] = sum(w[f"L{p}"] for p in formulas[ln])
    for col, parts in computed:
        w[col] = sum(w[p] for p in parts)
    return w


NA_DENOMINATOR_NOTE = "n/a = the denominator is zero or negative, so the ratio is not meaningful."


def safe_ratio(num, den):
    """num / den, NaN (shown as n/a) where the denominator is zero or negative; never divides by zero."""
    if isinstance(den, pd.Series):
        ok = den > 0
        return (num / den.where(ok, np.nan)).where(ok, np.nan)
    try:
        d = float(den)
    except (TypeError, ValueError):
        return np.nan
    return float(num) / d if np.isfinite(d) and d > 0 else np.nan


class SemanticLayer:
    def __init__(self, user_id: str, as_of: date | None = None):
        self.user_id = user_id
        self.as_of = as_of or as_of_date()
        self.engine = get_engine(user_id)
        self.reg = registry()
        self.d = dims()
        self.python_rls = backend() == "duckdb"
        self.allowed = allowed_bus(user_id)
        self.sql_log: list[str] = []
        acc = self.d.leaves
        self.code_of = dict(zip(acc["account_id"].astype(int), acc["l3_code"].astype(str)))
        self.leaf_codes = acc["l3_code"].astype(str).tolist()
        self.line_of = dict(zip(acc["l3_code"].astype(str), acc["line_no"].astype(int)))
        self.group_of = dict(zip(acc["l3_code"].astype(str), acc["l2_code"].astype(str)))

    # ------------------------------------------------------------------ SQL access
    def _compile(self, stmt) -> str:
        try:
            return str(stmt.compile(dialect=self.engine.dialect, compile_kwargs={"literal_binds": True}))
        except Exception:  # noqa: BLE001
            return str(stmt)

    def _where_org(self, stmt, org_filter, bu_col):
        for level, values in (org_filter or {}).items():
            stmt = stmt.where(dim_org.c[level].in_(list(values)))
        if self.python_rls:          # DuckDB: identical RLS rule enforced in Python
            stmt = stmt.where(bu_col.in_(sorted(self.allowed) or [-1]))
        return stmt

    @staticmethod
    def _where_months(stmt, col, months):
        ms = sorted(months)
        if ms == ti.month_range(ms[0], ms[-1]):
            return stmt.where(col.between(ms[0], ms[-1]))
        return stmt.where(col.in_(ms))

    def landing_snapshot(self):
        """Latest landing run for the open month at this as-of date (None if `make landing` has not run)."""
        if not hasattr(self, "_landing_snap"):
            from app.landing.query import latest_snapshot  # noqa: WPS433 (avoids a circular import)
            self._landing_snap = latest_snapshot(self.engine, self.as_of)
        return self._landing_snap

    def _fetch_landing_leaf(self, months, org_filter, group_cols=()) -> pd.DataFrame:
        from app.db import fact_landing_leaf  # noqa: WPS433

        gc = list(group_cols)
        snap = self.landing_snapshot()
        if snap is None or snap.month_key not in set(months):
            return pd.DataFrame(columns=gc + ["account_id", "amount"])
        f, o = fact_landing_leaf, dim_org
        gcols = [o.c[g] for g in gc if g in ORG_LEVELS] + ([f.c.month_key] if "month_key" in gc else [])
        stmt = (select(*gcols, f.c.account_id, func.sum(f.c.amount_usd).label("amount"))
                .select_from(f.join(o, f.c.bu_id == o.c.bu_id))
                .where(f.c.snapshot_date == snap.snapshot_date).where(f.c.month_key == snap.month_key))
        stmt = self._where_org(stmt, org_filter, f.c.bu_id)
        stmt = stmt.group_by(*gcols, f.c.account_id)
        self.sql_log.append(self._compile(stmt))
        with self.engine.connect() as conn:
            df = pd.read_sql(stmt, conn)
        df["amount"] = df["amount"].astype(float)
        return df

    def fetch_leaf(self, version: str, months, org_filter, group_cols=()) -> pd.DataFrame:
        gc = list(group_cols)
        if not months:
            return pd.DataFrame(columns=gc + ["account_id", "amount"])
        if version == "LANDING":                       # virtual version: stored landing P50 (open month)
            return self._fetch_landing_leaf(months, org_filter, gc)
        f, o, v = fact_pnl, dim_org, dim_version
        gcols = [o.c[g] for g in gc if g in ORG_LEVELS] + ([f.c.month_key] if "month_key" in gc else [])
        stmt = (select(*gcols, f.c.account_id, func.sum(f.c.amount_usd).label("amount"))
                .select_from(f.join(o, f.c.bu_id == o.c.bu_id).join(v, f.c.version_id == v.c.version_id))
                .where(v.c.name == version))
        stmt = self._where_months(stmt, f.c.month_key, months)
        stmt = self._where_org(stmt, org_filter, f.c.bu_id)
        stmt = stmt.group_by(*gcols, f.c.account_id)
        self.sql_log.append(self._compile(stmt))
        with self.engine.connect() as conn:
            df = pd.read_sql(stmt, conn)
        df["amount"] = df["amount"].astype(float)
        return df

    def fetch_stats(self, version: str, months, org_filter, group_cols=()) -> pd.DataFrame:
        gc = list(group_cols)
        stat_cols = [f"{k}_sum" for k in self.reg.stat_ids]
        if not months:
            return pd.DataFrame(columns=gc + stat_cols + ["n_months"])
        s, o, v = fact_stats, dim_org, dim_version
        gcols = [o.c[g] for g in gc if g in ORG_LEVELS] + ([s.c.month_key] if "month_key" in gc else [])
        stmt = (select(*gcols, *[func.sum(s.c[k]).label(f"{k}_sum") for k in self.reg.stat_ids],
                       func.count(distinct(s.c.month_key)).label("n_months"))
                .select_from(s.join(o, s.c.bu_id == o.c.bu_id).join(v, s.c.version_id == v.c.version_id))
                .where(v.c.name == version))
        stmt = self._where_months(stmt, s.c.month_key, months)
        stmt = self._where_org(stmt, org_filter, s.c.bu_id)
        if gcols:
            stmt = stmt.group_by(*gcols)
        self.sql_log.append(self._compile(stmt))
        with self.engine.connect() as conn:
            df = pd.read_sql(stmt, conn)
        for c in stat_cols + ["n_months"]:
            df[c] = df[c].astype(float)
        return df

    def _wide(self, leaf: pd.DataFrame, group_cols) -> pd.DataFrame:
        gc = list(group_cols)
        if leaf.empty:
            w = pd.DataFrame(columns=gc + self.leaf_codes, dtype=float)
        else:
            leaf = leaf.assign(code=leaf["account_id"].astype(int).map(self.code_of))
            if gc:
                w = leaf.pivot_table(index=gc, columns="code", values="amount", aggfunc="sum",
                                     fill_value=0.0).reset_index()
            else:
                w = leaf.groupby("code")["amount"].sum().to_frame().T.reset_index(drop=True)
            w.columns.name = None
        return add_lines(w, self.leaf_codes, self.line_of, self.group_of, self.reg.line_formulas,
                         self.reg.computed)

    def frame(self, series: list[ti.Series], org_filter, group_cols=(), with_stats=False) -> pd.DataFrame:
        parts = []
        gc = list(group_cols)
        for s in series:
            w = self._wide(self.fetch_leaf(s.version, s.months, org_filter, gc), gc)
            if with_stats:
                st = self.fetch_stats(s.version, s.months, org_filter, gc)
                if gc:
                    w = w.merge(st, on=gc, how="left")
                else:
                    cols = [c for c in st.columns]
                    row = st.iloc[0] if not st.empty else pd.Series({c: np.nan for c in cols})
                    for c in cols:
                        w[c] = float(row[c]) if pd.notna(row[c]) else np.nan
            w.insert(0, "series", s.label)
            parts.append(w)
        if not parts:
            return pd.DataFrame()
        return pd.concat(parts, ignore_index=True)

    # ------------------------------------------------------------------ metric math
    def target(self, name: str) -> tuple[str, MetricDef | RatioDef]:
        kind, obj = self.reg.resolve(name)
        if obj is None:
            raise ValueError(f"Unknown metric or ratio: {name!r}")
        return kind, obj

    def needs_stats(self, kind: str, obj) -> bool:
        if kind == "metric":
            return obj.kind == "stat"
        return self.reg.metrics[obj.num].kind == "stat" or self.reg.metrics[obj.den].kind == "stat"

    def metric_value(self, w, m: MetricDef):
        if m.kind == "stat":
            if m.agg == "avg":                           # stock: average over months
                return w[m.column] / w["n_months"]
            return w[m.column]                           # flow: sum
        return w[m.column] * m.natural_sign

    def ratio_parts(self, w, r: RatioDef):
        num = self.metric_value(w, self.reg.metrics[r.num])
        den_m = self.reg.metrics[r.den]
        if den_m.kind == "stat" and den_m.agg == "avg" and r.annualize:
            return num * 12.0, w[den_m.column]           # annualised per average FTE
        return num, self.metric_value(w, den_m)

    def value(self, w, kind: str, obj):
        if kind == "metric":
            return self.metric_value(w, obj)
        num, den = self.ratio_parts(w, obj)
        return safe_ratio(num, den)

    @staticmethod
    def fmt_of(kind: str, obj) -> str:
        if kind == "ratio":
            return obj.fmt
        if obj.kind == "stat":
            return "num"
        return "eur"

    def _filters(self, org_filter, period: ti.Period | None, series=None, extra=None) -> dict:
        d = {"org": org_label(org_filter), "org_filter": org_filter or {}, "currency": CURRENCY,
             "fx_rate": FX_RATE_CODE, "as_of_date": self.as_of.isoformat(), "user": self.user_id,
             "rls": "SQL Server SECURITY POLICY (SESSION_CONTEXT)" if not self.python_rls else "Python filter (DuckDB)"}
        if period is not None:
            d["period"] = period.label()
            d["months"] = f"{ti.month_label(period.months()[0])} - {ti.month_label(period.months()[-1])}"
        if series:
            d["versions"] = [f"{s.label} ({s.version}, {s.period.label()})" for s in series]
        d.update(extra or {})
        return d

    def _take_sql(self) -> list[str]:
        out, self.sql_log = self.sql_log, []
        return out

    # ------------------------------------------------------------------ P&L statement
    def pnl_rows(self, depth: int) -> list[dict]:
        acc = self.d.account.sort_values("display_order")
        rows = []
        for a in acc.itertuples():
            code = str(a.l3_code)
            if not a.is_leaf and a.display_order % 100 == 0:
                name = a.l1_name.upper() if a.is_subtotal else a.l1_name
                rows.append({"col": f"L{a.line_no}", "label": name, "code": str(a.line_no),
                             "kind": "subtotal" if a.is_subtotal else "line", "level": 0})
            elif not a.is_leaf:
                if depth >= 2:
                    rows.append({"col": code, "label": str(a.l2_name), "code": code,
                                 "kind": "group", "level": 1})
            elif depth >= 3:
                rows.append({"col": code, "label": str(a.l3_name), "code": code, "kind": "leaf",
                             "level": 2 if a.l2_code in ("7A", "7B") else 1})
        return rows

    def pnl(self, org_filter, period: ti.Period, versions=("Actual", "PY", "Budget"), depth: int = 1) -> Result:
        versions = list(versions) or ["Actual", "PY", "Budget"]
        series, notes = ti.resolve_series(versions[0], period, versions[1:], self.as_of)
        w = self.frame(series, org_filter, with_stats=True).set_index("series")
        labels = [s.label for s in series if s.label in w.index]
        primary = labels[0]
        out = []
        for r in self.pnl_rows(depth):
            row = {"Line": r["label"], "_code": r["code"], "_kind": r["kind"], "_level": r["level"], "_fmt": "eur"}
            for lab in labels:
                row[lab] = float(w.loc[lab, r["col"]])
            for lab in labels[1:]:
                diff, pct = ti.variance(row[primary], row[lab])
                row[f"Var vs {lab}"] = diff
                row[f"Var % vs {lab}"] = pct
                row[f"_fav_{lab}"] = ti.is_favorable(diff, "up")   # signed values: up = better
            out.append(row)
        for rid in ("maop_margin_revenue", "maop_margin_production", "gross_margin", "direct_margin",
                    "personnel_to_production"):
            r = self.reg.ratios[rid]
            row = {"Line": f"{r.name}", "_code": rid, "_kind": "ratio", "_level": 0, "_fmt": "pct"}
            for lab in labels:
                row[lab] = float(self.value(w.loc[[lab]], "ratio", r).iloc[0])
            for lab in labels[1:]:
                diff = row[primary] - row[lab]
                row[f"Var vs {lab}"] = diff
                row[f"Var % vs {lab}"] = None
                row[f"_fav_{lab}"] = ti.is_favorable(diff, r.favorable)
            out.append(row)
        for sid in ("fte", "headcount"):
            m = self.reg.metrics[sid]
            row = {"Line": f"{m.name} (average)", "_code": sid, "_kind": "stat", "_level": 0, "_fmt": "num"}
            for lab in labels:
                row[lab] = float(self.metric_value(w.loc[[lab]], m).iloc[0])
            for lab in labels[1:]:
                diff, pct = ti.variance(row[primary], row[lab])
                row[f"Var vs {lab}"] = diff
                row[f"Var % vs {lab}"] = pct
                row[f"_fav_{lab}"] = None
            out.append(row)
        df = pd.DataFrame(out)
        return Result("pnl", df, meta={"series": labels, "primary": primary, "depth": depth},
                      sql=self._take_sql(), notes=notes,
                      filters=self._filters(org_filter, series[0].period, series))

    # ------------------------------------------------------------------ trend
    def _by_month(self, version, months, org_filter, with_stats):
        months = [k for k in months if ti.data_bounds()[0] <= k <= ti.data_bounds()[1]]
        if not months:
            return pd.DataFrame(columns=["month_key"])
        s = ti.Series(version, version, ti.Period("RANGE", months[-1], months[0]), tuple(months))
        return self.frame([s], org_filter, ["month_key"], with_stats).set_index("month_key").sort_index()

    def trend(self, target: str, org_filter, start_key: int, end_key: int,
              versions=("Actual", "PY", "Budget")) -> Result:
        kind, obj = self.target(target)
        last = ti.last_closed_month(self.as_of)
        lo, hi = ti.data_bounds()
        start_key, end_key = max(start_key, lo), min(end_key, hi)
        if start_key > end_key:
            start_key = end_key
        months = ti.month_range(start_key, end_key)
        stats = self.needs_stats(kind, obj)
        out = pd.DataFrame({"month_key": months, "Month": [ti.month_label(k) for k in months]})
        notes = []
        cols = []
        yearly: dict[str, dict[int, dict]] = {}
        totals: dict[str, float] = {}

        def add_yearly(label: str, w: pd.DataFrame, shift: int = 0):
            """Yearly figures over the months shown: ratios = sum(numerator) / sum(denominator);
            amounts = sum; stocks (FTE, headcount) = average. Amount totals over all shown months too."""
            if w.empty:
                return
            if kind == "ratio":
                num, den = self.ratio_parts(w, obj)
                parts = pd.DataFrame({"num": num, "den": den})
            else:
                vals = self.value(w, kind, obj)
                parts = pd.DataFrame({"num": vals, "den": 1.0})
            parts.index = [ti.add_months(int(k), shift) for k in parts.index]
            parts = parts[parts.index.isin(months)].dropna()
            if parts.empty:
                return
            stock = kind == "metric" and obj.kind == "stat" and obj.agg == "avg"
            if kind == "metric" and not stock:
                totals[label] = float(parts["num"].sum())
            for y, g in parts.groupby(parts.index // 100):
                if kind == "ratio" and not g["den"].sum():
                    continue
                v = g["num"].sum() / g["den"].sum() if (kind == "ratio" or stock) else g["num"].sum()
                yearly.setdefault(label, {})[int(y)] = {"value": float(v), "months": int(len(g)),
                                                       "last": int(g.index.max())}
        for v in versions:
            vn = ti.normalize_version(v) or v
            if vn == "Actual":
                fetch = [k for k in months if k <= last]
                if kind == "ratio":
                    fetch = ti.month_range(max(ti.add_months(start_key, -11), lo), min(end_key, last)) if start_key <= last else []
                w = self._by_month("Actual", fetch, org_filter, stats)
                if w.empty:
                    continue
                vals = self.value(w, kind, obj)
                out["Actual"] = out["month_key"].map(vals)
                cols.append("Actual")
                add_yearly("Actual", w)
                if kind == "ratio" and obj.fmt == "pct":
                    num, den = self.ratio_parts(w, obj)
                    r12 = num.rolling(12, min_periods=12).sum() / den.rolling(12, min_periods=12).sum()
                    out["Actual R12M"] = out["month_key"].map(r12)
                    cols.append("Actual R12M")
                if end_key > last:
                    notes.append(f"Actuals are available to {ti.month_label(last)}.")
            elif vn == "PY":
                py = [ti.add_months(k, -12) for k in months if lo <= ti.add_months(k, -12) <= last]
                w = self._by_month("Actual", py, org_filter, stats)
                if w.empty:
                    continue
                vals = self.value(w, kind, obj)
                vals.index = [ti.add_months(int(k), 12) for k in vals.index]
                out["PY"] = out["month_key"].map(vals)
                cols.append("PY")
                add_yearly("PY", w, shift=12)
            else:
                if vn == "LatestFC":
                    vn = ti.latest_forecast(ti.ym(end_key)[0], self.as_of) or "Budget"
                if vn not in ("Budget", "FC1", "FC2", "FC3"):
                    continue
                vm = [k for k in months if vn == "Budget" or ti.forecast_available(vn, ti.ym(k)[0], self.as_of)]
                w = self._by_month(vn, vm, org_filter, stats)
                if w.empty:
                    notes.append(f"{vn} is not available for the selected months.")
                    continue
                out[vn] = out["month_key"].map(self.value(w, kind, obj))
                cols.append(vn)
                add_yearly(vn, w)
        period = ti.Period("RANGE", end_key, start_key)
        return Result("trend", out, meta={"target": obj.id, "name": obj.name, "kind": kind,
                                          "fmt": self.fmt_of(kind, obj), "series": cols,
                                          "favorable": obj.favorable},
                      sql=self._take_sql(), notes=notes,
                      filters=self._filters(org_filter, period, extra={"versions": cols}),
                      extra={k: v for k, v in (("yearly", yearly), ("totals", totals)) if v})

    # ------------------------------------------------------------------ ratio
    def ratio(self, target: str, org_filter, period: ti.Period, comparisons=("PY", "Budget")) -> Result:
        kind, obj = self.target(target)
        if kind != "ratio":
            raise ValueError(f"{target!r} is not a ratio")
        series, notes = ti.resolve_series("Actual", period, list(comparisons), self.as_of)
        w = self.frame(series, org_filter, with_stats=self.needs_stats(kind, obj))
        num, den = self.ratio_parts(w, obj)
        num_m, den_m = self.reg.metrics[obj.num], self.reg.metrics[obj.den]
        den_label = f"{den_m.name} (average)" if den_m.kind == "stat" and den_m.agg == "avg" else den_m.name
        df = pd.DataFrame({"Version": w["series"],
                           "Period": [s.period.label() for s in series if s.label in set(w["series"])],
                           num_m.name: self.metric_value(w, num_m).values,
                           den_label: self.metric_value(w, den_m).values,
                           obj.name: safe_ratio(num, den).values})
        if df[obj.name].isna().any():
            notes = notes + [NA_DENOMINATOR_NOTE]
        base = df[obj.name].iloc[0]
        df["Actual vs version"] = base - df[obj.name]
        df.loc[0, "Actual vs version"] = np.nan
        df["_fav"] = [None] + [ti.is_favorable(base - x, obj.favorable) for x in df[obj.name].iloc[1:]]
        return Result("ratio", df, meta={"target": obj.id, "name": obj.name, "fmt": obj.fmt,
                                         "favorable": obj.favorable, "num": num_m.name, "den": den_label,
                                         "num_is_stat": num_m.kind == "stat", "den_is_stat": den_m.kind == "stat",
                                         "series": list(w["series"])},
                      sql=self._take_sql(), notes=notes,
                      filters=self._filters(org_filter, series[0].period, series))

    # ------------------------------------------------------------------ variance drivers
    def drivers(self, target: str, org_filter, period: ti.Period, comparison: str = "PY", depth: int = 1) -> Result:
        kind, obj = self.target(target)
        series, notes = ti.resolve_series("Actual", period, [comparison], self.as_of)
        if len(series) < 2:
            raise ValueError(f"Comparison {comparison} is not available for {period.label()}")
        cur_s, cmp_s = series[0], series[1]
        stats = self.needs_stats(kind, obj)
        w = self.frame(series, org_filter, with_stats=stats).set_index("series")
        cur, cmpw = w.loc[[cur_s.label]], w.loc[[cmp_s.label]]
        total_cur = float(self.value(cur, kind, obj).iloc[0])
        total_cmp = float(self.value(cmpw, kind, obj).iloc[0])
        is_pct_ratio = kind == "ratio" and obj.fmt == "pct" and obj.num in self.reg.metrics \
            and self.reg.metrics[obj.num].kind != "stat"
        rows = []
        if kind == "metric" and obj.kind != "stat":
            for ch in self.reg.children(obj, depth):
                c_cur = float(cur[ch.column].iloc[0])
                c_cmp = float(cmpw[ch.column].iloc[0])
                contrib = (c_cur - c_cmp) * obj.natural_sign
                rows.append({"Driver": ch.name, "_code": ch.id, cur_s.label: c_cur * ch.natural_sign,
                             cmp_s.label: c_cmp * ch.natural_sign, "Impact": contrib,
                             "_fav": ti.is_favorable(contrib, obj.favorable)})
            unit = "eur"
        elif is_pct_ratio:
            num_m = self.reg.metrics[obj.num]
            den_cur, den_cmp = (float(self.metric_value(cur, self.reg.metrics[obj.den]).iloc[0]),
                                float(self.metric_value(cmpw, self.reg.metrics[obj.den]).iloc[0]))
            kids = self.reg.children(num_m, 1)
            if depth >= 2:
                expanded = []
                for ch in kids:
                    sub = self.reg.children(ch, depth - 1) if ch.is_cost else []
                    expanded += sub or [ch]
                kids = expanded
            for ch in kids or [num_m]:
                c_cur = float(cur[ch.column].iloc[0])
                c_cmp = float(cmpw[ch.column].iloc[0])
                contrib = c_cur * num_m.natural_sign / den_cur - c_cmp * num_m.natural_sign / den_cmp
                rows.append({"Driver": f"{ch.name} as % of {self.reg.metrics[obj.den].name.lower()}",
                             "_code": ch.id,
                             cur_s.label: c_cur * ch.natural_sign / den_cur,
                             cmp_s.label: c_cmp * ch.natural_sign / den_cmp,
                             "Impact": contrib,
                             "_fav": ti.is_favorable(contrib, obj.favorable)})
            unit = "pp"
        else:
            unit = obj.fmt if kind == "ratio" else "num"
        acc_df = pd.DataFrame(rows)
        if not acc_df.empty:
            tot = acc_df["Impact"].sum()
            acc_df["Share of variance"] = acc_df["Impact"] / tot if abs(tot) > 1e-12 else np.nan
            acc_df = acc_df.reindex(acc_df["Impact"].abs().sort_values(ascending=False).index).reset_index(drop=True)
        groups = []
        if kind == "metric" and obj.kind != "stat" and depth >= 2:
            first, deep = self.reg.children(obj, 1), self.reg.children(obj, depth)
            if first and {c.id for c in first} != {c.id for c in deep}:
                for ch in first:
                    g_cur, g_cmp = float(cur[ch.column].iloc[0]), float(cmpw[ch.column].iloc[0])
                    contrib = (g_cur - g_cmp) * obj.natural_sign
                    groups.append({"Group": ch.name, cur_s.label: g_cur * ch.natural_sign,
                                   cmp_s.label: g_cmp * ch.natural_sign, "Impact": contrib,
                                   "_fav": ti.is_favorable(contrib, obj.favorable)})

        # org drill-down: next level with more than one member
        level = child_level(org_filter, bus_for_filter(org_filter) & self.allowed)
        org_df = pd.DataFrame()
        if level:
            wo = self.frame(series, org_filter, [level], with_stats=stats)
            p_cur = wo[wo["series"] == cur_s.label].set_index(level)
            p_cmp = wo[wo["series"] == cmp_s.label].set_index(level)
            ents = sorted(set(p_cur.index) | set(p_cmp.index))
            p_cur, p_cmp = p_cur.reindex(ents), p_cmp.reindex(ents)
            v_cur, v_cmp = self.value(p_cur, kind, obj), self.value(p_cmp, kind, obj)
            org_df = pd.DataFrame({level_label(level): ents, cur_s.label: v_cur.values, cmp_s.label: v_cmp.values})
            org_df["Impact"] = org_df[cur_s.label] - org_df[cmp_s.label] if kind == "ratio" else \
                (org_df[cur_s.label].fillna(0) - org_df[cmp_s.label].fillna(0))
            org_df["_fav"] = [ti.is_favorable(x, obj.favorable) if pd.notna(x) else None for x in org_df["Impact"]]
            org_df = org_df.reindex(org_df["Impact"].abs().sort_values(ascending=False).index).reset_index(drop=True)
        meta = {"target": obj.id, "name": obj.name, "kind": kind, "fmt": self.fmt_of(kind, obj), "unit": unit,
                "current": cur_s.label, "comparison": cmp_s.label, "total_current": total_cur,
                "total_comparison": total_cmp, "favorable": obj.favorable, "org_level": level,
                "natural_sign": getattr(obj, "natural_sign", 1)}
        extra = {"org": org_df}
        if groups:
            extra["groups"] = pd.DataFrame(groups)
        return Result("drivers", acc_df, meta=meta, sql=self._take_sql(), notes=notes,
                      filters=self._filters(org_filter, cur_s.period, series), extra=extra)

    # ------------------------------------------------------------------ ranking
    def rank(self, target: str, level: str, parent_filter, period: ti.Period, top_n: int | None = 5,
             ascending: bool = False, comparison: str | None = "PY") -> Result:
        kind, obj = self.target(target)
        if level not in ORG_LEVELS:
            raise ValueError(f"Unknown org level {level!r}")
        series, notes = ti.resolve_series("Actual", period, [comparison] if comparison else [], self.as_of)
        w = self.frame(series, parent_filter, [level], with_stats=self.needs_stats(kind, obj))
        cur_l = series[0].label
        cur = w[w["series"] == cur_l].set_index(level)
        df = pd.DataFrame({level_label(level): cur.index, cur_l: self.value(cur, kind, obj).values})
        if len(series) > 1:
            cmp_l = series[1].label
            c = w[w["series"] == cmp_l].set_index(level).reindex(cur.index)
            df[cmp_l] = self.value(c, kind, obj).values
            df["Var"] = df[cur_l] - df[cmp_l]
            if kind == "metric":
                df["Var %"] = df["Var"] / df[cmp_l].abs().replace(0, np.nan)
            df["_fav"] = [ti.is_favorable(x, obj.favorable) if pd.notna(x) else None for x in df["Var"]]
        df = df.sort_values(cur_l, ascending=ascending, na_position="last").reset_index(drop=True)
        total = len(df)
        if top_n and top_n > 0:
            df = df.head(top_n)
        df.insert(0, "Rank", range(1, len(df) + 1))
        return Result("ranking", df, meta={"target": obj.id, "name": obj.name, "kind": kind,
                                           "fmt": self.fmt_of(kind, obj), "level": level,
                                           "level_label": level_label(level), "ascending": ascending,
                                           "top_n": top_n, "entities_total": total,
                                           "favorable": obj.favorable, "current": cur_l},
                      sql=self._take_sql(), notes=notes,
                      filters=self._filters(parent_filter, series[0].period, series,
                                            {"ranking_level": level_label(level)}))

    # ------------------------------------------------------------------ versions
    def compare_versions(self, org_filter, period: ti.Period,
                         versions=("Actual", "Budget", "FC1", "FC2", "FC3")) -> Result:
        versions = [ti.normalize_version(v) or v for v in versions] or ["Actual", "Budget"]
        if "LatestFC" in versions:
            lf = ti.latest_forecast(period.year, self.as_of)
            versions = [lf if v == "LatestFC" else v for v in versions if v != "LatestFC" or lf]
        versions = list(dict.fromkeys(versions))
        pre_notes = []
        last = ti.last_closed_month(self.as_of)
        if period.period_type == "FY" and period.end_key > last and any(v != "Actual" for v in versions):
            if "Actual" in versions:
                versions = [v for v in versions if v != "Actual"]
                pre_notes.append(f"Full-year view: Budget and forecasts cover {period.label()}; Actuals are only "
                                 f"available to {ti.month_label(last)} and are not shown.")
            if versions and "Budget" not in versions:
                versions.append("Budget")
        primary = "Actual" if "Actual" in versions else versions[0]
        others = [v for v in versions if v != primary and v != "PY"]
        series, notes = ti.resolve_series(primary, period, others, self.as_of)
        notes = pre_notes + notes
        w = self.frame(series, org_filter).set_index("series")
        labels = [s.label for s in series]
        ref = "Budget" if "Budget" in labels and len(labels) > 1 else (labels[1] if len(labels) > 1 else None)
        rows = []
        for mid in KEY_LINES:
            m = self.reg.metrics[mid]
            row = {"Line": m.name.upper() if m.subtotal else m.name, "_code": mid,
                   "_kind": "subtotal" if m.subtotal else "line", "_fmt": "eur"}
            for lab in labels:
                row[lab] = float(w.loc[lab, m.column])
            for lab in labels:
                if lab == ref:
                    continue
                if ref:
                    diff = row[lab] - row[ref]
                    row[f"{lab} vs {ref}"] = diff
                    row[f"_fav_{lab}"] = ti.is_favorable(diff, "up")
            rows.append(row)
        for rid in ("maop_margin_revenue", "maop_margin_production", "gross_margin", "direct_margin"):
            r = self.reg.ratios[rid]
            row = {"Line": r.name, "_code": r.id, "_kind": "ratio", "_fmt": "pct"}
            for lab in labels:
                row[lab] = float(self.value(w.loc[[lab]], "ratio", r).iloc[0])
            for lab in labels:
                if ref and lab != ref:
                    row[f"{lab} vs {ref}"] = row[lab] - row[ref]
                    row[f"_fav_{lab}"] = ti.is_favorable(row[lab] - row[ref], "up")
            rows.append(row)
        df = pd.DataFrame(rows)
        return Result("versions", df, meta={"series": labels, "reference": ref, "primary": primary},
                      sql=self._take_sql(), notes=notes,
                      filters=self._filters(org_filter, series[0].period, series))

    # ------------------------------------------------------------------ KPI cockpit
    def cockpit(self, org_filter, month_key: int | None = None) -> Result:
        """Operational profitability cockpit: MTD and YTD actuals vs LY and vs Budget for the KPI
        list in metrics.yaml (direct margin, production, direct labor, utilization, ...)."""
        last = ti.last_closed_month(self.as_of)
        month_key = min(month_key or last, last)
        blocks = {}
        notes: list[str] = []
        for label, period in (("MTD", ti.Period("MONTH", month_key)), ("YTD", ti.Period("YTD", month_key))):
            series, n = ti.resolve_series("Actual", period, ["PY", "Budget"], self.as_of)
            notes += n
            blocks[label] = (series, self.frame(series, org_filter, with_stats=True).set_index("series"))
        rows = []
        for kid in self.reg.cockpit:
            kind, obj = self.target(kid)
            fmt = self.fmt_of(kind, obj)
            row = {"KPI": obj.name, "_code": kid, "_fmt": fmt, "_kind": "line", "_favorable": obj.favorable}
            for label, (series, w) in blocks.items():
                vals = {s.label: float(self.value(w.loc[[s.label]], kind, obj).iloc[0]) for s in series}
                cur = vals.get("Actual")
                row[label] = cur
                for cmp_lab, col in (("PY", f"{label} vs LY"), ("Budget", f"{label} vs Budget")):
                    c = vals.get(cmp_lab)
                    if cur is None or c is None or (isinstance(c, float) and np.isnan(c)):
                        row[col] = None
                        continue
                    diff = cur - c
                    row[col] = diff if fmt == "pct" else (diff / abs(c) if c else None)
                    row[f"_fav_{col}"] = ti.is_favorable(diff, obj.favorable)
            rows.append(row)
        df = pd.DataFrame(rows)
        trend = self.trend("direct_margin", org_filter, ti.mk(ti.ym(month_key)[0], 1), month_key,
                           ("Actual", "PY", "Budget"))
        sql = self._take_sql()
        period = ti.Period("YTD", month_key)
        return Result("cockpit", df, meta={"month": ti.month_label(month_key), "kpis": self.reg.cockpit},
                      sql=sql + trend.sql, notes=list(dict.fromkeys(notes)),
                      filters=self._filters(org_filter, period, extra={
                          "versions": ["Actual", "PY (LY)", "Budget"],
                          "period": f"MTD {ti.month_label(month_key)} and YTD {ti.month_label(month_key)}"}),
                      extra={"trend": trend.df})

    # ------------------------------------------------------------------ workforce (employee records)
    WF_SUMS = ["headcount", "fte", "available_hours", "billable_hours", "overtime_hours", "hires", "leavers",
               "restructuring_leavers"]

    def fetch_workforce(self, months, org_filter, group: str | None = None) -> pd.DataFrame:
        """Employee-month records summed per month (and per `group`: role, grade, staff_type or an org
        level). headcount = employees on payroll, hires / leavers = first / last month on payroll."""
        gname = [group] if group else []
        if not months:
            return pd.DataFrame(columns=gname + ["month_key"] + self.WF_SUMS)
        f, e, o = fact_employee_month, dim_employee, dim_org
        gmap = {"role": e.c.role, "grade": e.c.grade, "staff_type": e.c.staff_type}
        gcols = [gmap[group] if group in gmap else o.c[group]] if group else []
        leaver = cast(f.c.is_leaver, Integer)
        stmt = (select(*gcols, f.c.month_key,
                       func.count().label("headcount"),
                       func.sum(f.c.fte).label("fte"),
                       func.sum(f.c.available_hours).label("available_hours"),
                       func.sum(f.c.billable_hours).label("billable_hours"),
                       func.sum(f.c.overtime_hours).label("overtime_hours"),
                       func.sum(cast(f.c.is_hire, Integer)).label("hires"),
                       func.sum(leaver).label("leavers"),
                       func.sum(case((e.c.leave_reason == "Restructuring", leaver), else_=0)).label("restructuring_leavers"))
                .select_from(f.join(e, f.c.employee_id == e.c.employee_id).join(o, f.c.bu_id == o.c.bu_id)))
        stmt = self._where_months(stmt, f.c.month_key, months)
        stmt = self._where_org(stmt, org_filter, f.c.bu_id)
        stmt = stmt.group_by(*gcols, f.c.month_key)
        self.sql_log.append(self._compile(stmt))
        with self.engine.connect() as conn:
            df = pd.read_sql(stmt, conn)
        for c in self.WF_SUMS:
            df[c] = df[c].astype(float)
        df["month_key"] = df["month_key"].astype(int)
        return df

    def _wf_summary(self, df: pd.DataFrame, by: str | None, n_months: int) -> pd.DataFrame:
        """Sum employee-month columns per `by` (None = one total row) and derive the rates:
        averages over the period's months, attrition annualised = leavers x 12 / months / avg headcount."""
        if by:
            s = df.groupby(by)[self.WF_SUMS].sum().reset_index() if not df.empty else \
                pd.DataFrame(columns=[by] + self.WF_SUMS)
        else:
            s = df[self.WF_SUMS].sum().to_frame().T
        n = max(int(n_months), 1)
        s["avg_headcount"] = s["headcount"] / n
        s["avg_fte"] = s["fte"] / n
        hc = s["avg_headcount"].replace(0, np.nan)
        s["attrition"] = s["leavers"] * 12.0 / n / hc
        s["voluntary_attrition"] = (s["leavers"] - s["restructuring_leavers"]) * 12.0 / n / hc
        av = s["available_hours"].replace(0, np.nan)
        s["utilization"] = s["billable_hours"] / av
        s["overtime"] = s["overtime_hours"] / av
        return s

    def _wf_r12(self, months, org_filter) -> dict[int, tuple[float, float]]:
        """Attrition over the rolling 12 months to each month: (all leavers, voluntary leavers) x 12 / sum of
        monthly headcount in the window. Months with less than 12 months of history are left out."""
        lo = ti.data_bounds()[0]
        ext = [k for k in ti.month_range(ti.add_months(months[0], -11), months[-1]) if k >= lo]
        df = self.fetch_workforce(ext, org_filter, None)
        if df.empty:
            return {}
        s = df.groupby("month_key")[["headcount", "leavers", "restructuring_leavers"]].sum().reindex(ext, fill_value=0.0)
        roll = s.rolling(12, min_periods=12).sum()
        out = {}
        for k in months:
            r = roll.loc[k] if k in roll.index else None
            if r is not None and pd.notna(r["headcount"]) and r["headcount"] > 0:
                out[k] = (float(r["leavers"] * 12.0 / r["headcount"]),
                          float((r["leavers"] - r["restructuring_leavers"]) * 12.0 / r["headcount"]))
        return out

    def workforce(self, org_filter, period: ti.Period, group: str | None = None, focus: str = "headcount",
                  top_n: int | None = None, ascending: bool | None = None) -> Result:
        """Workforce view from the employee records (Actual months only), vs the same months of the
        prior year. group: None (total only) | role | grade | staff_type | month | l2_region..l6_bu."""
        focus = focus if focus in WF_METRICS else "headcount"
        last = ti.last_closed_month(self.as_of)
        lo = ti.data_bounds()[0]
        shown = period.truncate(last)
        months = [k for k in shown.months() if lo <= k <= last]
        if not months:
            raise ValueError(f"No employee records for {period.label()}: they cover the closed months "
                             f"{ti.month_label(lo)} - {ti.month_label(last)}.")
        notes = []
        if period.months()[-1] > last:
            notes.append(f"Employee records cover closed months up to {ti.month_label(last)}.")
        py_months = [ti.add_months(k, -12) for k in months]
        has_py = py_months[0] >= lo
        if not has_py:
            notes.append(f"No prior-year comparison: employee records start in {ti.month_label(lo)}.")
        by_month = group == "month"
        gcol = None if (not group or by_month) else group
        n = len(months)
        cur = self.fetch_workforce(months, org_filter, gcol)
        prev = self.fetch_workforce(py_months, org_filter, gcol) if has_py else pd.DataFrame()
        if not prev.empty:
            prev = prev.assign(month_key=[ti.add_months(int(k), 12) for k in prev["month_key"]])

        hc_col, fte_col = ("Headcount", "FTE") if by_month else ("Avg headcount", "Avg FTE")
        cols = {k: v[0] for k, v in WF_METRICS.items()}
        cols.update({"headcount": hc_col, "fte": fte_col})
        label = WF_GROUPS.get(group) if group in WF_GROUPS else (level_label(group) if group else "Scope")

        def row_of(name, c, p, kind: str) -> dict:
            def g(src, k):
                return None if src is None or pd.isna(src.get(k)) else float(src.get(k))
            r = {label: name, "_kind": kind, hc_col: g(c, "avg_headcount"), "Headcount PY": g(p, "avg_headcount"),
                 fte_col: g(c, "avg_fte"), "Hires": g(c, "hires"), "Leavers": g(c, "leavers"),
                 "of which restructuring": g(c, "restructuring_leavers"),
                 "Attrition": g(c, "attrition"), "Attrition PY": g(p, "attrition"),
                 "Utilization": g(c, "utilization"), "Utilization PY": g(p, "utilization"),
                 "Overtime ratio": g(c, "overtime"),
                 "_fte_py": g(p, "avg_fte"), "_hires_py": g(p, "hires"), "_leavers_py": g(p, "leavers"),
                 "_restructuring_py": g(p, "restructuring_leavers"),
                 "_voluntary_attrition_py": g(p, "voluntary_attrition"), "Voluntary attrition": g(c, "voluntary_attrition"),
                 "_overtime_py": g(p, "overtime")}
            for key, direction in (("Attrition", "down"), ("Utilization", "up")):
                a, b = r[key], r[f"{key} PY"]
                r[f"_fav_{key}"] = ti.is_favorable(a - b, direction) if a is not None and b is not None else None
            return r

        tot_c = self._wf_summary(cur, None, n).iloc[0]
        tot_p = self._wf_summary(prev, None, n).iloc[0] if has_py and not prev.empty else None
        total = row_of("Total", tot_c, tot_p, "subtotal")
        rows, entities_total = [], 0
        if by_month:
            mc = self._wf_summary(cur, "month_key", 1).set_index("month_key")
            mp = self._wf_summary(prev, "month_key", 1).set_index("month_key") if has_py and not prev.empty else None
            r12, r12_py = self._wf_r12(months, org_filter), (self._wf_r12(py_months, org_filter) if has_py else {})
            for k in months:
                c = mc.loc[k] if k in mc.index else None
                p = mp.loc[k] if mp is not None and k in mp.index else None
                row = row_of(ti.month_label(k), c, p, "line")
                a, b = r12.get(k, (None, None)), r12_py.get(ti.add_months(k, -12), (None, None))
                row.update({"Attrition": a[0], "Voluntary attrition": a[1], "Attrition PY": b[0],
                            "_voluntary_attrition_py": b[1],
                            "_fav_Attrition": ti.is_favorable(a[0] - b[0], "down") if None not in (a[0], b[0]) else None})
                rows.append(row)
            total[label] = f"Total {shown.label()}"
            rows.append(total)
        else:
            if gcol:
                gc = self._wf_summary(cur, gcol, n).set_index(gcol)
                gp = self._wf_summary(prev, gcol, n).set_index(gcol) if has_py and not prev.empty else None
                body = [row_of(str(k), gc.loc[k], gp.loc[k] if gp is not None and k in gp.index else None, "line")
                        for k in gc.index]
                entities_total = len(body)
                fcol = cols[focus]
                if gcol == "grade":
                    body.sort(key=lambda r: r[label])
                elif gcol == "staff_type":
                    body.sort(key=lambda r: (r[label] != "Direct", r[label]))
                else:
                    desc = not bool(ascending)
                    body.sort(key=lambda r: (r.get(fcol) is None, -(r.get(fcol) or 0) if desc else (r.get(fcol) or 0)))
                    if top_n and top_n > 0:
                        body = body[:top_n]
                rows = [total] + body
            else:
                rows = [total]
        # monthly totals (peak month for hires / leavers)
        monthly = cur.groupby("month_key")[["headcount", "hires", "leavers", "restructuring_leavers"]].sum() \
            if not cur.empty else pd.DataFrame()
        peak = None
        if n > 1 and not monthly.empty and monthly["leavers"].max() > 0:
            k = int(monthly["leavers"].idxmax())
            peak = {"month": ti.month_label(k), "leavers": float(monthly.loc[k, "leavers"]),
                    "restructuring": float(monthly.loc[k, "restructuring_leavers"])}
        df = pd.DataFrame(rows)
        series = [f"Actual ({shown.label()})"] + ([f"PY ({ti.month_label(py_months[0])} - "
                                                     f"{ti.month_label(py_months[-1])})"] if has_py else [])
        meta = {"group": group, "group_label": label, "focus": focus, "cols": cols, "has_py": has_py,
                "n_months": n, "entities_total": entities_total, "ascending": bool(ascending),
                "top_n": top_n, "peak_leavers": peak, "series": ["Actual"] + (["PY"] if has_py else []),
                "monthly": {ti.month_label(int(k)): {c: float(v) for c, v in r.items()} for k, r in monthly.iterrows()}
                if n > 1 else {}}
        if group in ORG_LEVELS:
            meta.update({"level": group, "level_label": label})
        return Result("workforce", df, meta=meta, sql=self._take_sql(), notes=notes,
                      filters=self._filters(org_filter, shown, extra={
                          "versions": series, "source": "fictional employee records (closed months)"}))

