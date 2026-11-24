#!/usr/bin/env python
"""Backtest the current-month landing on the last 24 closed months and write the report.

For every closed month in the window the landing is recomputed as of the 15th of that month, with only
the data that existed then (earlier actuals, forecasts already published). Metrics:
  * WAPE and MAPE for billing, revenue and operating profit
  * mean absolute error in percentage points for both operating margins
  * share of actuals inside the P10-P90 range (coverage)
by org level (BU .. group), product line and billing pattern class, for each method, the ensemble and
the plain latest forecast. Writes docs/landing_backtest_report.md and the landing_backtest_metric table.

    make backtest
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import as_of_date  # noqa: E402
from app.landing import engine as E  # noqa: E402
from app.landing.store import Timer, write_backtest_metrics  # noqa: E402
from app.semantic import time_intel as ti  # noqa: E402

REPORT = ROOT / "docs" / "landing_backtest_report.md"
LEVELS = [("BU", "l6_bu"), ("Business", "l5_business"), ("Product line", "l4_product_line"),
          ("Country", "l3_country"), ("Region", "l2_region"), ("Group", "l1_group")]
METHOD_ORDER = ["ensemble", E.BASELINE, *E.METHODS]
MEASURES = ("billing", "revenue", "maop", "maop_xw")
KEYS = ("billing", "revenue", "production", "maop", "revenue_xw", "production_xw", "maop_xw")
MEASURE_LABEL = {"billing": "Billing", "revenue": "Revenue", "maop": "Operating profit (as booked)",
                 "maop_xw": "Operating profit excl. WIP (like-for-like)"}


def actual_measures(d: E.Data) -> dict[str, np.ndarray]:
    L = d.act
    rev = L[1] + L[2]
    prod = rev + L[4] + L[5]
    maop = prod + L[7] + L[8] + L[9] + L[10] + L[12]
    return {"billing": L[1], "revenue": rev, "production": prod, "maop": maop,
            "revenue_xw": L[1], "production_xw": prod - L[2], "maop_xw": maop - L[2]}


def forecast_measures(d: E.Data, version: str, o: int) -> dict[str, np.ndarray]:
    V = d.ver[version]
    g = lambda ln: V[ln][:, o] if ln in V else np.zeros(d.B)  # noqa: E731
    rev = g(1) + g(2)
    prod = rev + g(4) + g(5)
    maop = prod + g(7) + g(8) + g(9) + g(10) + g(12)
    return {"billing": g(1), "revenue": rev, "production": prod, "maop": maop,
            "revenue_xw": g(1), "production_xw": prod - g(2), "maop_xw": maop - g(2)}


def predictions(d: E.Data, r: E.Rolling, origins: list[int]) -> dict[str, dict[str, np.ndarray]]:
    """method -> measure -> (B, n_origins) predicted values (billing-driven costs per the engine)."""
    out = {m: {k: np.full((d.B, len(origins)), np.nan) for k in KEYS} for m in METHOD_ORDER}
    for j, o in enumerate(origins):
        cl = E.cost_lines(d, o, r.fversion[o])
        for m in METHOD_ORDER:
            if m == E.BASELINE:
                fm = forecast_measures(d, r.fversion[o], o)
                for k in fm:
                    out[m][k][:, j] = fm[k]
                continue
            b = r.p50[:, o] if m == "ensemble" else r.pred[m][:, o]
            mm = E.measures_from_billing(b, cl)
            mm.update({"revenue_xw": mm["revenue"], "production_xw": mm["production"], "maop_xw": mm["maop"]})
            for k in KEYS:
                out[m][k][:, j] = mm[k]
    return out


def group_index(org: pd.DataFrame, col: str) -> dict[str, np.ndarray]:
    return {str(k): np.where(org[col].to_numpy() == k)[0] for k in org[col].unique()}


def agg(x: np.ndarray, groups: dict[str, np.ndarray]) -> np.ndarray:
    """(E, n_origins) sums over the BUs of each entity (NaN if any BU value is missing)."""
    return np.stack([np.sum(x[idx], axis=0) for idx in groups.values()])


def wape(pred, act) -> tuple[float, int]:
    ok = np.isfinite(pred) & np.isfinite(act)
    den = np.abs(act[ok]).sum()
    return (float(np.abs(pred[ok] - act[ok]).sum() / den) if den else np.nan), int(ok.sum())


def mape(pred, act) -> float:
    ok = np.isfinite(pred) & np.isfinite(act) & (np.abs(act) > 1e-6)
    return float(np.mean(np.abs(pred[ok] - act[ok]) / np.abs(act[ok]))) if ok.any() else np.nan


def margin_mae(num_p, den_p, num_a, den_a) -> float:
    mp, ma = E.margin(num_p, den_p), E.margin(num_a, den_a)
    ok = np.isfinite(mp) & np.isfinite(ma)
    return float(np.mean(np.abs(mp[ok] - ma[ok])) * 100) if ok.any() else np.nan


def coverage_bu(r: E.Rolling, A: np.ndarray, origins: list[int], idx: np.ndarray | None = None) -> tuple[float, int]:
    sel = idx if idx is not None else slice(None)
    lo = (r.p50 * np.exp(r.q10))[sel][:, origins]
    hi = (r.p50 * np.exp(r.q90))[sel][:, origins]
    a = A[sel][:, origins]
    ok = np.isfinite(a) & np.isfinite(lo) & np.isfinite(hi)
    return float(((a >= lo) & (a <= hi))[ok].mean()), int(ok.sum())


def coverage_agg(r: E.Rolling, A: np.ndarray, origins: list[int], groups: dict[str, np.ndarray], window: int,
                 draws: int) -> tuple[float, int]:
    hits, n = 0, 0
    for j, o in enumerate(origins):
        rwin = [k for k in r.origins if o - window <= k < o]
        for gi, idx in enumerate(groups.values()):
            p50 = r.p50[idx, o]
            a = A[idx, o]
            if not (np.isfinite(p50).all() and np.isfinite(a).all()):
                continue
            sims = E.simulate(p50, r.resid[idx][:, rwin], draws, seed=1000 + 31 * j + gi).sum(axis=1)
            lo, hi = np.quantile(sims, [0.1, 0.9])
            tot = a.sum()
            hits += int(lo <= tot <= hi)
            n += 1
    return (hits / n if n else np.nan), n


def run(as_of: date | None = None, write: bool = True) -> dict:
    timer = Timer()
    as_of = as_of or as_of_date()
    c = E.cfg()
    d = E.load_data(as_of)
    r = E.rolling(d, as_of)
    origins = [o for o in r.origins if r.live - int(c["backtest_months"]) <= o < r.live]
    act = actual_measures(d)
    A = {k: v[:, origins] for k, v in act.items()}
    P = predictions(d, r, origins)
    org = d.org.assign(l1_group=d.org["l1_group"])
    rows = []

    def add(scope_type, scope_value, measure, method, metric, value, n):
        rows.append({"scope_type": scope_type, "scope_value": scope_value, "measure": measure, "method": method,
                     "metric": metric, "value": None if value is None or not np.isfinite(value) else round(value, 6),
                     "n": int(n)})

    for label, col in LEVELS:
        groups = group_index(org, col)
        for m in METHOD_ORDER:
            for k in MEASURES:
                pa, aa = agg(P[m][k], groups), agg(A[k], groups)
                w, n = wape(pa, aa)
                add("org_level", label, k, m, "wape", w, n)
                add("org_level", label, k, m, "mape", mape(pa, aa), n)
                if label == "Group":
                    add("group", "Group", k, m, "wape", w, n)
                    add("group", "Group", k, m, "mape", mape(pa, aa), n)
            for name, num, den in (("maop_margin_revenue", "maop", "revenue"),
                                   ("maop_margin_production", "maop", "production"),
                                   ("maop_margin_revenue_xw", "maop_xw", "revenue_xw"),
                                   ("maop_margin_production_xw", "maop_xw", "production_xw")):
                v = margin_mae(agg(P[m][num], groups), agg(P[m][den], groups), agg(A[num], groups),
                               agg(A[den], groups))
                add("org_level", label, name, m, "mae_pp", v, len(groups) * len(origins))
                if label == "Group":
                    add("group", "Group", name, m, "mae_pp", v, len(origins))
        if label == "BU":
            cv, n = coverage_bu(r, act["billing"], origins)
        else:
            cv, n = coverage_agg(r, act["billing"], origins, groups, int(c["residual_window"]), 400)
        add("org_level", label, "billing", "ensemble", "coverage_p10_p90", cv, n)
        if label == "Group":
            add("group", "Group", "billing", "ensemble", "coverage_p10_p90", cv, n)
    # product lines (PL totals) and pattern classes (BU level within the class)
    for pl, idx in group_index(org, "l4_product_line").items():
        for m in METHOD_ORDER:
            for k in MEASURES:
                w, n = wape(P[m][k][idx].sum(axis=0), A[k][idx].sum(axis=0))
                add("product_line", pl, k, m, "wape", w, n)
        cv, n = coverage_bu(r, act["billing"], origins, idx)
        add("product_line", pl, "billing", "ensemble", "coverage_p10_p90_bu", cv, n)
    cls = r.profiles[r.live].cls
    for k_cls in E.CLASSES:
        idx = np.where(cls == k_cls)[0]
        if idx.size == 0:
            continue
        for m in METHOD_ORDER:
            for k in MEASURES:
                w, n = wape(P[m][k][idx], A[k][idx])
                add("pattern_class", k_cls, k, m, "wape", w, n)
        cv, n = coverage_bu(r, act["billing"], origins, idx)
        add("pattern_class", k_cls, "billing", "ensemble", "coverage_p10_p90", cv, n)
    metrics = pd.DataFrame(rows)
    monthly = pd.DataFrame([{
        "month": ti.month_label(d.months[o]), "forecast": r.fversion[o],
        "actual": float(np.nansum(act["billing"][:, o])),
        "ensemble": float(np.nansum(r.p50[:, o])), "latest_forecast": float(np.nansum(r.pred[E.BASELINE][:, o]))}
        for o in origins])
    open_check = hidden_truth_check(d, r)
    info = {"as_of": as_of, "origins": [d.months[o] for o in origins], "beta": r.beta[r.live],
            "classes": pd.Series(cls).value_counts().to_dict(), "seconds": timer.seconds,
            "n_bus": d.B, "open_check": open_check}
    if write:
        write_backtest_metrics(metrics, as_of)
        REPORT.write_text(render(metrics, monthly, info))
    return {"metrics": metrics, "monthly": monthly, "info": info}


def hidden_truth_check(d: E.Data, r: E.Rolling) -> dict | None:
    """The generator keeps the true month-end of the open month (synthetic data only; tests/backtests only)."""
    path = ROOT / "data" / "eval_truth_open_month.parquet"
    if not path.exists():
        return None
    ev = pd.read_parquet(path)
    key = d.months[r.live]
    ev = ev[ev["month_key"] == key]
    if ev.empty:
        return None
    line_of = {d.leaf_id[c]: d.leaf_line[c] for c in d.leaf_id}
    ev = ev.assign(line=ev["account_id"].map(line_of))
    bill = ev[ev["line"] == 1].groupby("bu_id")["amount_usd"].sum().reindex(d.bu_ids).to_numpy()
    p50 = r.p50[:, r.live]
    lo, hi = p50 * np.exp(r.q10[:, r.live]), p50 * np.exp(r.q90[:, r.live])
    fc = r.pred[E.BASELINE][:, r.live]
    return {"month": ti.month_label(key), "truth": float(bill.sum()), "landing": float(p50.sum()),
            "forecast": float(np.nansum(fc)), "bu_wape": float(np.abs(p50 - bill).sum() / np.abs(bill).sum()),
            "bu_wape_fc": float(np.abs(fc - bill).sum() / np.abs(bill).sum()),
            "bu_coverage": float(((bill >= lo) & (bill <= hi)).mean())}


def _pct(x, nd=1) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:.{nd}f}%"


def _get(m: pd.DataFrame, **kw) -> float:
    sel = m
    for k, v in kw.items():
        sel = sel[sel[k] == v]
    return float(sel["value"].iloc[0]) if not sel.empty and sel["value"].iloc[0] is not None else np.nan


def _weaknesses(m: pd.DataFrame, info: dict) -> str:
    """Every measured place where the ensemble is worse than the latest forecast as published (no fixed text)."""
    rows = []
    checks = [("group", None, "Group"), ("org_level", "BU", "BU")]
    for scope_type, scope_value, label in checks:
        for measure, name in (("billing", "billing"), ("revenue", "revenue (as booked)"),
                              ("maop", "operating profit (as booked)"), ("maop_xw", "operating profit excl. WIP")):
            kw = {"scope_type": scope_type, "measure": measure, "metric": "wape"}
            if scope_value:
                kw["scope_value"] = scope_value
            a, b = _get(m, method="ensemble", **kw), _get(m, method=E.BASELINE, **kw)
            if np.isfinite(a) and np.isfinite(b) and a > b:
                rows.append(f"- {label} {name}: WAPE {_pct(a, 2)} vs {_pct(b, 2)} for the latest forecast.")
    for k in E.CLASSES:
        if k not in info["classes"]:
            continue
        a = _get(m, scope_type="pattern_class", scope_value=k, measure="billing", method="ensemble", metric="wape")
        b = _get(m, scope_type="pattern_class", scope_value=k, measure="billing", method=E.BASELINE, metric="wape")
        if np.isfinite(a) and np.isfinite(b) and a > b:
            rows.append(f"- {E.CLASS_LABEL[k]} BUs, billing: WAPE {_pct(a, 2)} vs {_pct(b, 2)} for the latest forecast.")
    if not rows:
        return "## Where the landing is weaker\n\nNo measured case where the latest forecast beats the landing.\n"
    return ("## Where the landing is weaker\n\nMeasured cases where the latest forecast as published beats the "
            "landing:\n\n" + "\n".join(rows) + "\n\nSuggested next steps: for revenue and operating profit as booked, "
            "add a WIP estimate for the landing month (the WIP = 0 rule is the main error source); for lumpy BUs, "
            "lean on the latest forecast (raise its weight for the class) and keep the wide ranges.\n")


def render(m: pd.DataFrame, monthly: pd.DataFrame, info: dict) -> str:
    months = info["origins"]
    g_ens = _get(m, scope_type="group", measure="billing", method="ensemble", metric="wape")
    g_fc = _get(m, scope_type="group", measure="billing", method=E.BASELINE, metric="wape")
    cov_bu = _get(m, scope_type="org_level", scope_value="BU", measure="billing", metric="coverage_p10_p90")
    cov_g = _get(m, scope_type="group", measure="billing", metric="coverage_p10_p90")
    goal1 = np.isfinite(g_ens) and np.isfinite(g_fc) and g_ens < g_fc
    goal2 = np.isfinite(cov_bu) and 0.70 <= cov_bu <= 0.90
    L = []
    L.append("# Landing backtest report\n")
    L.append(f"Generated by `make backtest` (scripts/backtest_landing.py) with data as of {info['as_of']}. "
             f"The landing was recomputed for each of the last {len(months)} closed months "
             f"({ti.month_label(months[0])} to {ti.month_label(months[-1])}), as of the 15th of that month, using only "
             "the actuals of earlier months and the forecasts already published then. All numbers below are "
             "measured on the synthetic data of this prototype.\n")
    L.append("## Goals\n")
    L.append("| Goal | Measured | Met |\n|---|---|---|")
    L.append(f"| Ensemble beats the plain latest forecast on group billing WAPE | {_pct(g_ens, 2)} vs {_pct(g_fc, 2)} | "
             f"{'yes' if goal1 else 'no'} |")
    L.append(f"| P10-P90 coverage between 70% and 90% (BU billing) | {_pct(cov_bu)} | {'yes' if goal2 else 'no'} |")
    L.append(f"\nGroup-level billing coverage (one total per month, {len(months)} months): {_pct(cov_g)}.")
    if np.isfinite(cov_g) and not 0.70 <= cov_g <= 0.90:
        L.append(f"This is {'above' if cov_g > 0.9 else 'below'} the 70-90% band: at group level the P10-P90 range is "
                 f"{'wider' if cov_g > 0.9 else 'narrower'} than needed. With only {len(months)} monthly totals one "
                 "month moves coverage by about 4 points; a next step is to calibrate the common shock of the "
                 "simulation on group-level errors.")
    L.append("")
    if not goal1 or not goal2:
        L.append("**Shortfall and suggested improvements:** " + (
            "the ensemble does not beat the latest forecast at group level; consider weighting by forecast "
            "freshness (the latest forecast is strongest in the months right after FC3). " if not goal1 else "") + (
            "coverage is outside 70-90%; widen or narrow the empirical quantiles (for example per class and "
            "forecast type) and re-measure." if not goal2 else "") + "\n")
    L.append(_weaknesses(m, info))
    L.append("## Accuracy by method (billing, revenue, operating profit)\n")
    L.append("WAPE = sum of absolute errors / sum of actuals. Group = one total per month; BU = every BU and month. "
             "Operating profit is shown as booked and like-for-like: the landing rule sets WIP to 0 in the landing "
             "month, so the like-for-like view removes the month's WIP movement from the actuals and from the "
             "forecast before comparing.\n")
    L.append("| Method | Group billing | Group revenue | Group op. profit (as booked) | Group op. profit excl. WIP | "
             "BU billing | BU op. profit excl. WIP |")
    L.append("|---|---|---|---|---|---|---|")
    for meth in METHOD_ORDER:
        L.append(f"| {E.METHOD_LABEL[meth]} | "
                 f"{_pct(_get(m, scope_type='group', measure='billing', method=meth, metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='group', measure='revenue', method=meth, metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='group', measure='maop', method=meth, metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='group', measure='maop_xw', method=meth, metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='org_level', scope_value='BU', measure='billing', method=meth, metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='org_level', scope_value='BU', measure='maop_xw', method=meth, metric='wape'), 2)} |")
    L.append("\nRevenue is compared with actual revenue, which includes WIP; the landing assumes WIP = 0 in the "
             "landing month, so part of the revenue error is the month's actual WIP movement. WIP swings are large "
             "relative to operating profit (for example the December WIP release), which is why the as-booked "
             "operating profit error is much higher than the like-for-like error.\n")
    L.append("## By org level (ensemble vs latest forecast)\n")
    L.append("| Level | Billing WAPE | Billing MAPE | Op. profit excl. WIP WAPE | Margin on revenue MAE (excl. WIP) | "
             "Margin on production MAE (excl. WIP) | Margin on revenue MAE (as booked) | P10-P90 coverage |")
    L.append("|---|---|---|---|---|---|---|---|")
    for label, _ in LEVELS:
        def pair(measure, metric, fmt=_pct):
            a = _get(m, scope_type="org_level", scope_value=label, measure=measure, method="ensemble", metric=metric)
            b = _get(m, scope_type="org_level", scope_value=label, measure=measure, method=E.BASELINE, metric=metric)
            return f"{fmt(a)} vs {fmt(b)}"
        pp = lambda x: "n/a" if not np.isfinite(x) else f"{x:.2f} pp"  # noqa: E731
        L.append(f"| {label} | {pair('billing', 'wape')} | {pair('billing', 'mape')} | {pair('maop_xw', 'wape')} | "
                 f"{pair('maop_margin_revenue_xw', 'mae_pp', pp)} | {pair('maop_margin_production_xw', 'mae_pp', pp)} | "
                 f"{pair('maop_margin_revenue', 'mae_pp', pp)} | "
                 f"{_pct(_get(m, scope_type='org_level', scope_value=label, measure='billing', metric='coverage_p10_p90'))} |")
    L.append("\n## By product line (product-line totals, billing WAPE)\n")
    L.append("| Product line | Ensemble | Latest forecast | BU P10-P90 coverage |\n|---|---|---|---|")
    for pl in sorted(m[m.scope_type == "product_line"].scope_value.unique()):
        L.append(f"| {pl} | {_pct(_get(m, scope_type='product_line', scope_value=pl, measure='billing', method='ensemble', metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='product_line', scope_value=pl, measure='billing', method=E.BASELINE, metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='product_line', scope_value=pl, measure='billing', metric='coverage_p10_p90_bu'))} |")
    L.append("\n## By billing pattern class (BU level, billing WAPE)\n")
    L.append("| Pattern class | BUs | Ensemble | Latest forecast | Best single method | P10-P90 coverage |")
    L.append("|---|---|---|---|---|---|")
    for k in E.CLASSES:
        if k not in info["classes"]:
            continue
        best = min(E.METHODS, key=lambda x: _get(m, scope_type="pattern_class", scope_value=k, measure="billing",
                                                 method=x, metric="wape") if np.isfinite(_get(
                                                     m, scope_type="pattern_class", scope_value=k, measure="billing",
                                                     method=x, metric="wape")) else 9)
        L.append(f"| {E.CLASS_LABEL[k]} | {info['classes'][k]} | "
                 f"{_pct(_get(m, scope_type='pattern_class', scope_value=k, measure='billing', method='ensemble', metric='wape'), 2)} | "
                 f"{_pct(_get(m, scope_type='pattern_class', scope_value=k, measure='billing', method=E.BASELINE, metric='wape'), 2)} | "
                 f"{E.METHOD_LABEL[best]} ({_pct(_get(m, scope_type='pattern_class', scope_value=k, measure='billing', method=best, metric='wape'), 2)}) | "
                 f"{_pct(_get(m, scope_type='pattern_class', scope_value=k, measure='billing', metric='coverage_p10_p90'))} |")
    L.append("\n## Group billing by month\n")
    L.append("| Month | Latest forecast available | Actual (USD m) | Landing error | Latest forecast error |")
    L.append("|---|---|---|---|---|")
    for row in monthly.itertuples():
        L.append(f"| {row.month} | {row.forecast} | {row.actual / 1e6:,.1f} | "
                 f"{100 * (row.ensemble / row.actual - 1):+.2f}% | {100 * (row.latest_forecast / row.actual - 1):+.2f}% |")
    oc = info.get("open_check")
    if oc:
        L.append(f"\n## Open month check ({oc['month']}, one month only)\n")
        L.append("Because the data is synthetic, the generator also keeps the true month-end of the open month "
                 "(used only by tests and this report, never by the app). One month is not a measure of accuracy; "
                 "it is shown as a sanity check.\n")
        L.append(f"| | Value |\n|---|---|\n| Group billing, true month-end | USD {oc['truth'] / 1e6:,.2f}m |\n"
                 f"| Group billing, landing P50 | USD {oc['landing'] / 1e6:,.2f}m ({100 * (oc['landing'] / oc['truth'] - 1):+.2f}%) |\n"
                 f"| Group billing, latest forecast | USD {oc['forecast'] / 1e6:,.2f}m ({100 * (oc['forecast'] / oc['truth'] - 1):+.2f}%) |\n"
                 f"| BU billing WAPE, landing vs latest forecast | {_pct(oc['bu_wape'], 2)} vs {_pct(oc['bu_wape_fc'], 2)} |\n"
                 f"| BUs inside their P10-P90 range | {_pct(oc['bu_coverage'])} |")
    L.append("\n## Method notes\n")
    L.append(f"- Working-day elasticity estimated from history at the latest origin: {info['beta']:.2f}.")
    L.append("- Ensemble weights per BU: inverse WAPE over the previous 12 origins, shrunk toward the weights of the "
             "BU's pattern class; methods without enough history are left out.")
    L.append("- P10 / P90: empirical 10th / 90th percentiles of the ensemble's own past errors (per BU with at least "
             "18 past months, otherwise per pattern class); aggregates use a seeded simulation (common shock plus "
             "BU-specific error).")
    L.append(f"- Pattern classes at the latest origin: " + ", ".join(
        f"{E.CLASS_LABEL[k]} {v}" for k, v in sorted(info['classes'].items())) + ".")
    L.append(f"\nRun time: {info['seconds']:.0f} s for {info['n_bus']} BUs.\n")
    return "\n".join(L)


if __name__ == "__main__":
    out = run()
    m = out["metrics"]
    g = m[(m.scope_type == "group") & (m.measure == "billing") & (m.metric == "wape")]
    print(g[["method", "value", "n"]].to_string(index=False))
    print(f"Report written to {REPORT.relative_to(ROOT)}; {len(m)} metric rows saved.")
