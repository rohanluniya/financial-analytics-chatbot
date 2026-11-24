"""Read API for the current-month landing (tools, Data Catalog, About page), under row-level security.

* P50 of any scope is the exact sum of its BUs' P50 (leaf-level, so every P&L line, account group and
  ratio of the semantic layer works for the landing month; aggregate margins are ratios of sums).
* P10 / P90 of a scope come from a seeded simulation (engine.simulate): billing-driven lines scale with
  each BU's simulated billing, personnel and functional lines stay at their P50.
* YTD / QTD including the landing = closed-month actuals + the landing month; the full-year outlook adds
  the latest forecast for the months after the landing month.
* Lines below operating profit (other operating expenses, financial result, taxes) and the operational
  statistics are outside the landing scope.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.config import settings
from app.db import dim_org, fact_landing, fact_landing_leaf, landing_backtest_metric, landing_bu_profile, \
    landing_method, landing_residual, landing_run
from app.landing import engine as E
from app.semantic import time_intel as ti
from app.semantic.query_builder import Result, SemanticLayer, add_lines
from app.semantic.registry import registry

SCALED_LINES = (1, 4, 5, 8, 9)               # follow billing in the simulation
OUT_OF_SCOPE_LINES = (17, 18, 19, 20, 21)    # below operating profit
LANDING_MEASURES = ("billing", "revenue", "production", "personnel", "subcontracting", "other_cost",
                    "functional_neutralization", "functional_cost", "gross_profit", "maop",
                    "maop_margin_revenue", "maop_margin_production")
HEADLINE = ("billing", "revenue", "production", "maop", "maop_margin_revenue", "maop_margin_production")
WIP_NOTE = ("WIP is 0 in the landing month, so the revenue landing equals the billing landing.")
DATA_NOTE = ("The landing uses monthly history only (closed-month actuals, Budget and forecasts); "
             "there is no intra-month data.")


@dataclass(frozen=True)
class Snapshot:
    snapshot_date: date
    month_key: int
    run_at: datetime | None
    notes: str | None

    @property
    def label(self) -> str:
        return ti.month_label(self.month_key)


def latest_snapshot(engine, as_of: date) -> Snapshot | None:
    """The newest landing run for the open month at `as_of` (run on or before `as_of`)."""
    key = E.open_month(as_of)
    stmt = (select(landing_run).where(landing_run.c.month_key == key).where(landing_run.c.snapshot_date <= as_of)
            .order_by(landing_run.c.snapshot_date.desc()).limit(1))
    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn)
    if df.empty:
        return None
    r = df.iloc[0]
    return Snapshot(pd.Timestamp(r["snapshot_date"]).date(), int(r["month_key"]),
                    pd.Timestamp(r["run_at"]).to_pydatetime() if pd.notna(r["run_at"]) else None,
                    r["notes"] if pd.notna(r["notes"]) else None)


def last_refresh(engine) -> Snapshot | None:
    stmt = select(landing_run).order_by(landing_run.c.run_at.desc()).limit(1)
    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn)
    if df.empty:
        return None
    r = df.iloc[0]
    return Snapshot(pd.Timestamp(r["snapshot_date"]).date(), int(r["month_key"]),
                    pd.Timestamp(r["run_at"]).to_pydatetime(), r["notes"] if pd.notna(r["notes"]) else None)


def measure_label(m: str) -> str:
    reg = registry()
    if m in reg.metrics:
        return reg.metrics[m].name
    if m in reg.ratios:
        return reg.ratios[m].name
    return m.replace("_", " ").capitalize()


def measure_target(m: str):
    reg = registry()
    if m in reg.ratios:
        return "ratio", reg.ratios[m]
    return "metric", reg.metrics[m]


def in_scope(kind: str, obj) -> bool:
    """True if the metric / ratio can be computed for the landing month."""
    reg = registry()
    if kind == "ratio":
        return in_scope("metric", reg.metrics[obj.num]) and in_scope("metric", reg.metrics[obj.den])
    if obj.kind == "stat":
        return False
    if obj.kind == "line":
        return obj.line not in OUT_OF_SCOPE_LINES
    if obj.kind == "leaf":
        return obj.line not in OUT_OF_SCOPE_LINES
    return True


class LandingQuery:
    """Landing numbers for one user (RLS) and as-of date."""

    def __init__(self, sl: SemanticLayer):
        self.sl = sl
        self.snap = latest_snapshot(sl.engine, sl.as_of)
        self.draws = int(E.cfg()["simulation_draws"])
        self.seed = int(settings()["seed"]) + (self.snap.month_key if self.snap else 0)

    @property
    def available(self) -> bool:
        return self.snap is not None

    @property
    def month(self) -> int:
        return self.snap.month_key if self.snap else E.open_month(self.sl.as_of)

    # -------------------------------------------------------------------------- raw reads (RLS)
    def _read(self, table, org_filter, cols=None, extra_where=None) -> pd.DataFrame:
        o = dim_org
        sel_cols = cols if cols is not None else [table]
        stmt = select(*sel_cols, o.c.l2_region, o.c.l3_country, o.c.l4_product_line, o.c.l5_business,
                      o.c.l6_bu).select_from(table.join(o, table.c.bu_id == o.c.bu_id))
        stmt = stmt.where(table.c.snapshot_date == self.snap.snapshot_date)
        if extra_where is not None:
            stmt = stmt.where(extra_where)
        stmt = self.sl._where_org(stmt, org_filter, table.c.bu_id)
        self.sl.sql_log.append(self.sl._compile(stmt))
        with self.sl.engine.connect() as conn:
            return pd.read_sql(stmt, conn)

    def bu_measures(self, org_filter) -> pd.DataFrame:
        """One row per BU: org columns, pattern class, weights and p10/p50/p90 per measure."""
        df = self._read(fact_landing, org_filter, extra_where=fact_landing.c.month_key == self.month)
        if df.empty:
            return df
        for c in ("p10", "p50", "p90"):
            df[c] = df[c].astype(float)
        wide = df.pivot_table(index="bu_id", columns="measure", values=["p10", "p50", "p90"], aggfunc="first")
        wide.columns = [f"{m}_{q}" for q, m in wide.columns]
        info = df.drop_duplicates("bu_id").set_index("bu_id")[
            ["l2_region", "l3_country", "l4_product_line", "l5_business", "l6_bu", "pattern_class",
             "method_weights_json"]]
        return info.join(wide).reset_index()

    def leaf_matrix(self, org_filter) -> tuple[np.ndarray, list[str], np.ndarray]:
        """(bu_ids, leaf codes, matrix BU x code) of P50 amounts (signed)."""
        df = self._read(fact_landing_leaf, org_filter,
                        cols=[fact_landing_leaf.c.bu_id, fact_landing_leaf.c.account_id, fact_landing_leaf.c.amount_usd],
                        extra_where=fact_landing_leaf.c.month_key == self.month)
        codes = self.sl.leaf_codes
        if df.empty:
            return np.array([], dtype=int), codes, np.zeros((0, len(codes)))
        df["code"] = df["account_id"].astype(int).map(self.sl.code_of)
        m = df.pivot_table(index="bu_id", columns="code", values="amount_usd", aggfunc="sum", fill_value=0.0)
        m = m.reindex(columns=codes, fill_value=0.0).astype(float)
        return m.index.to_numpy(), codes, m.to_numpy()

    def residuals(self, bu_ids: np.ndarray) -> np.ndarray:
        if len(bu_ids) == 0:
            return np.zeros((0, 0))
        t = landing_residual
        stmt = select(t.c.bu_id, t.c.origin_month_key, t.c.log_error).where(t.c.snapshot_date == self.snap.snapshot_date)
        stmt = stmt.where(t.c.bu_id.in_([int(b) for b in bu_ids]))
        if self.sl.python_rls:
            stmt = stmt.where(t.c.bu_id.in_(sorted(self.sl.allowed) or [-1]))
        with self.sl.engine.connect() as conn:
            df = pd.read_sql(stmt, conn)
        if df.empty:
            return np.full((len(bu_ids), 0), np.nan)
        df["log_error"] = df["log_error"].astype(float)
        m = df.pivot_table(index="bu_id", columns="origin_month_key", values="log_error", aggfunc="first")
        return m.reindex(index=[int(b) for b in bu_ids]).to_numpy(dtype=float)

    # -------------------------------------------------------------------------- wide frames
    def _wide_from_codes(self, values: np.ndarray, codes: list[str]) -> pd.DataFrame:
        w = pd.DataFrame(values, columns=codes)
        return add_lines(w, self.sl.leaf_codes, self.sl.line_of, self.sl.group_of, self.sl.reg.line_formulas,
                         self.sl.reg.computed)

    def landing_wide(self, org_filter) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
        """(P50 wide frame with 1 row, simulated wide frame with D rows, info) for the landing month."""
        bu_ids, codes, L = self.leaf_matrix(org_filter)
        info = {"n_bus": int(len(bu_ids)), "bu_ids": [int(b) for b in bu_ids]}
        if len(bu_ids) == 0:
            empty = self._wide_from_codes(np.zeros((1, len(codes))), codes)
            return empty, empty, info
        scaled = np.array([self.sl.line_of[c] in SCALED_LINES for c in codes])
        b50 = L[:, [i for i, c in enumerate(codes) if self.sl.line_of[c] == 1]].sum(axis=1)
        R = self.residuals(bu_ids)
        draws = E.simulate(b50, R, self.draws, self.seed)                     # (D, B)
        with np.errstate(divide="ignore", invalid="ignore"):
            S = np.where(np.abs(b50) > 1e-9, draws / np.where(np.abs(b50) > 1e-9, b50, 1.0), 1.0)
        agg50 = L.sum(axis=0, keepdims=True)
        aggD = np.repeat(agg50, self.draws, axis=0)
        aggD[:, scaled] = S @ L[:, scaled]
        return self._wide_from_codes(agg50, codes), self._wide_from_codes(aggD, codes), info

    def actual_wide(self, org_filter, version: str, months: list[int]) -> pd.DataFrame:
        if not months:
            return self._wide_from_codes(np.zeros((1, len(self.sl.leaf_codes))), self.sl.leaf_codes)
        s = ti.Series(version, version, ti.Period("RANGE", months[-1], months[0]), tuple(months))
        w = self.sl.frame([s], org_filter)
        return w.drop(columns=["series"]).reset_index(drop=True)

    # -------------------------------------------------------------------------- numbers
    def value_and_range(self, kind: str, obj, w50: pd.DataFrame, wD: pd.DataFrame,
                        base: pd.DataFrame | None = None) -> tuple[float, float, float]:
        """P50 and the P10 / P90 of a metric or ratio, optionally on top of a fixed base (closed months)."""
        if base is not None:
            cols = [c for c in w50.columns if c in base.columns]
            w50 = w50[cols] + base[cols].iloc[0]
            wD = wD[cols] + base[cols].iloc[0]
        p50 = float(np.asarray(self.sl.value(w50, kind, obj)).ravel()[0])
        vals = np.asarray(self.sl.value(wD, kind, obj), dtype=float).ravel()
        vals = vals[np.isfinite(vals)]
        if not np.isfinite(p50) or vals.size == 0:
            return p50, np.nan, np.nan
        lo, hi = np.quantile(vals, [0.1, 0.9])
        return p50, float(min(lo, p50)), float(max(hi, p50))

    def comparison_wide(self, org_filter, label: str, months: list[int]) -> tuple[str, pd.DataFrame] | None:
        """Comparison frames over `months`: Budget, LatestFC, PY (Actual a year earlier)."""
        year = months[-1] // 100
        if label == "PY":
            return "PY", self.actual_wide(org_filter, "Actual", [ti.add_months(k, -12) for k in months])
        if label == "Budget":
            return "Budget", self.actual_wide(org_filter, "Budget", months)
        if label in ("LatestFC", "Forecast"):
            v = ti.latest_forecast(year, self.sl.as_of)
            if not v:
                return None
            return v, self.actual_wide(org_filter, v, months)
        if label in ("FC1", "FC2", "FC3") and ti.forecast_available(label, year, self.sl.as_of):
            return label, self.actual_wide(org_filter, label, months)
        return None


def backtest_metrics(engine, run_date: date | None = None) -> pd.DataFrame:
    """Measured backtest accuracy (latest run unless a date is given). Aggregated, no BU rows."""
    t = landing_backtest_metric
    with engine.connect() as conn:
        if run_date is None:
            last = pd.read_sql(select(t.c.run_date).order_by(t.c.run_date.desc()).limit(1), conn)
            if last.empty:
                return pd.DataFrame(columns=[c.name for c in t.columns])
            run_date = pd.Timestamp(last.iloc[0, 0]).date()
        df = pd.read_sql(select(t).where(t.c.run_date == run_date), conn)
    df["value"] = df["value"].astype(float)
    return df


def accuracy_note(engine) -> str:
    """One sentence with the measured backtest accuracy of the group billing landing (or why there is none)."""
    df = backtest_metrics(engine)
    if df.empty:
        return "No backtest has been run yet (`make backtest`), so no accuracy figure is available."
    g = df[(df.scope_type == "group") & (df.measure == "billing") & (df.metric == "wape")]
    ens = g[g.method == "ensemble"]["value"]
    fc = g[g.method == E.BASELINE]["value"]
    cov = df[(df.scope_type == "org_level") & (df.scope_value == "BU") & (df.measure == "billing")
             & (df.metric == "coverage_p10_p90") & (df.method == "ensemble")]["value"]
    n = int(g["n"].max()) if not g.empty else 0
    parts = []
    if not ens.empty:
        parts.append(f"group billing error (WAPE) {100 * ens.iloc[0]:.1f}% over the last {n} closed months")
    if not fc.empty:
        parts.append(f"vs {100 * fc.iloc[0]:.1f}% for the latest forecast as published")
    if not cov.empty:
        parts.append(f"BU actuals fell inside P10-P90 {100 * cov.iloc[0]:.0f}% of the time")
    return "Backtest (measured): " + ", ".join(parts) + "." if parts else ""


def bu_profiles(sl: SemanticLayer, org_filter=None) -> pd.DataFrame:
    """Billing pattern class and profile per visible BU for the current snapshot."""
    q = LandingQuery(sl)
    if not q.available:
        return pd.DataFrame()
    df = q._read(landing_bu_profile, org_filter or {})
    return df


def method_rows(sl: SemanticLayer, org_filter) -> pd.DataFrame:
    q = LandingQuery(sl)
    if not q.available:
        return pd.DataFrame()
    df = q._read(landing_method, org_filter, extra_where=landing_method.c.month_key == q.month)
    for c in ("prediction", "weight", "backtest_wape"):
        df[c] = df[c].astype(float)
    df["detail"] = df["detail_json"].map(lambda s: json.loads(s) if isinstance(s, str) and s else {})
    return df
