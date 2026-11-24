"""Landing engine: profiles, methods, ensemble, intervals, cost lines and leaf allocation.

Every origin (an open month in the past, or today's open month) is computed with the data that
existed at that time: actuals of earlier months and the forecast versions already published at the
origin's as-of date. The same code serves `make landing` (today's open month) and `make backtest`.

Billing methods (per BU):
  M1_yoy            same month last year x trailing year-on-year growth (3 and 6 months)
  M2_seasonal       trailing 12-month average x seasonal index (shrunk toward the product line)
  M3_forecast_bias  latest forecast (FC3 > FC2 > FC1 > Budget) x the BU's actual / forecast ratio,
                    shrunk toward 1
  M4_ets            exponential smoothing (damped trend, multiplicative seasonality), >= 36 months
All methods work on working-day adjusted series (elasticity estimated from history).
Ensemble weights per BU = inverse backtest WAPE, shrunk toward the weights of the BU's pattern class.
P10 / P90 = empirical quantiles of past ensemble errors (per BU with enough history, else per class);
aggregates use a seeded simulation (common shock + BU-specific error, 1,000 draws).
Cost lines: intragroup lines as a ratio to billing for that calendar month; personnel = seasonality
adjusted run-rate of the last 3 months; subcontracting and other costs = ratio to billing (recent
months blended with the same month last year); functional recharges and costs = latest forecast.
Subtotals and margins use the semantic layer's formulas (WIP = 0, so revenue = billing).
"""
from __future__ import annotations

import json
import os
import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import func, select

from app.ui import branding as B
from app.config import as_of_date, settings
from app.db import dim_account, dim_org, dim_version, fact_pnl, get_engine, landing_mtd_snapshot
from app.db import working_days as working_days_table
from app.semantic import time_intel as ti

METHODS = ("M1_yoy", "M2_seasonal", "M3_forecast_bias", "M4_ets")
BASELINE = "latest_forecast"
METHOD_LABEL = {
    "M1_yoy": "Same month last year x recent growth",
    "M2_seasonal": "Trailing 12 months x seasonal index",
    "M3_forecast_bias": "Latest forecast x the BU's forecast accuracy",
    "M4_ets": "Exponential smoothing (ETS)",
    "latest_forecast": "Latest forecast as published",
    "ensemble": f"{B.APP_NAME} landing (weighted ensemble)",
}
CLASSES = ("steady", "quarter_end", "year_end", "seasonal", "lumpy")
CLASS_LABEL = {"steady": "Steady", "quarter_end": "Quarter-end loaded", "year_end": "Year-end loaded",
               "seasonal": "Seasonal (March peak, August dip)", "lumpy": "Lumpy (project billing)"}
LANDING_LINES = (1, 2, 4, 5, 7, 8, 9, 10, 12)          # billing .. functional costs (landing scope)
LINE_MEASURE = {1: "billing", 2: "wip_ui", 4: "intragroup_revenue", 5: "intragroup_subcontracting",
                7: "personnel", 8: "subcontracting", 9: "other_cost", 10: "functional_neutralization",
                12: "functional_cost"}
DERIVED_MEASURES = ("revenue", "production", "gross_profit", "maop", "maop_margin_revenue",
                    "maop_margin_production")
FIRST_ORIGIN_INDEX = 12                                  # first origin with a full year of history


def cfg() -> dict:
    d = {"backtest_months": 24, "weight_window": 12, "residual_window": 24, "min_bu_residuals": 18,
         "shrink_origins": 6, "profile_min_months": 36, "ets_min_months": 36, "simulation_draws": 1000,
         "mtd_snapshot_enabled": False}
    d.update(settings().get("landing") or {})
    return d


def open_month(as_of: date | None = None) -> int:
    """The landing month: the month after the last closed month (months close on the 5th)."""
    return ti.add_months(ti.last_closed_month(as_of or as_of_date()), 1)


def latest_version(year: int, as_of: date) -> str:
    """Latest forecast published for `year` at `as_of` (FC3 > FC2 > FC1), else the Budget."""
    return ti.latest_forecast(year, as_of) or "Budget"


# ------------------------------------------------------------------------------------------
# Data
# ------------------------------------------------------------------------------------------
@dataclass
class Data:
    bu_ids: np.ndarray
    org: pd.DataFrame                              # one row per BU (same order as bu_ids)
    months: list[int]                              # month keys; index t
    act: dict[int, np.ndarray]                     # line -> (B, T) Actual, NaN where not closed
    ver: dict[str, dict[int, np.ndarray]]          # version -> line -> (B, T)
    leaf: dict[str, np.ndarray]                    # leaf code -> (B, T) Actual
    leaf_line: dict[str, int]
    leaf_id: dict[str, int]
    wd: np.ndarray                                 # (B, T) working days of the BU's country
    wd_typical: np.ndarray                         # (B, 12) average working days per calendar month
    mtd: dict[int, float] = field(default_factory=dict)

    @property
    def B(self) -> int:
        return len(self.bu_ids)

    def idx(self, key: int) -> int:
        return self.months.index(key)

    def cal(self, t: int) -> int:
        return self.months[t] % 100 - 1


def load_data(as_of: date | None = None, engine=None, mask_from: int | None = None) -> Data:
    """Read monthly history with full visibility (batch job; the app reads results under RLS).

    Actuals of months >= `mask_from` (default: the open month at `as_of`) are hidden, so a past
    as-of date sees exactly the closed months of that time.
    """
    as_of = as_of or as_of_date()
    eng = engine or get_engine(admin=True)
    with eng.connect() as conn:
        org = pd.read_sql(select(dim_org), conn).sort_values("bu_id").reset_index(drop=True)
        acc = pd.read_sql(select(dim_account.c.account_id, dim_account.c.line_no, dim_account.c.l3_code,
                                 dim_account.c.is_leaf), conn)
        f, v = fact_pnl, dim_version
        act = pd.read_sql(select(f.c.bu_id, f.c.month_key, f.c.account_id, f.c.amount_usd)
                          .select_from(f.join(v, f.c.version_id == v.c.version_id)).where(v.c.name == "Actual"),
                          conn)
        a2 = dim_account
        other = pd.read_sql(
            select(v.c.name.label("version"), f.c.bu_id, f.c.month_key, a2.c.line_no,
                   func.sum(f.c.amount_usd).label("amount_usd"))
            .select_from(f.join(v, f.c.version_id == v.c.version_id).join(a2, f.c.account_id == a2.c.account_id))
            .where(v.c.name != "Actual").group_by(v.c.name, f.c.bu_id, f.c.month_key, a2.c.line_no), conn)
        wdf = pd.read_sql(select(working_days_table), conn)
        mtd = {}
        if bool(cfg()["mtd_snapshot_enabled"]):
            m = pd.read_sql(select(landing_mtd_snapshot).where(landing_mtd_snapshot.c.snapshot_date == as_of), conn)
            mtd = {int(r.bu_id): float(r.mtd_billing) for r in m.itertuples()}
    first, last = ti.data_bounds()
    months = ti.month_range(first, last)
    T, bu_ids = len(months), org["bu_id"].to_numpy()
    B = len(bu_ids)
    bpos = {int(b): i for i, b in enumerate(bu_ids)}
    tpos = {k: i for i, k in enumerate(months)}
    leaves = acc[acc["is_leaf"].astype(bool)]
    leaf_id = dict(zip(leaves["l3_code"].astype(str), leaves["account_id"].astype(int)))
    leaf_line = dict(zip(leaves["l3_code"].astype(str), leaves["line_no"].astype(int)))
    code_of = {v_: k for k, v_ in leaf_id.items()}
    mask_from = mask_from if mask_from is not None else open_month(as_of)

    leaf = {c: np.full((B, T), np.nan) for c in leaf_id}
    act = act[act["month_key"] < mask_from]
    bi = act["bu_id"].map(bpos).to_numpy()
    ti_ = act["month_key"].map(tpos).to_numpy()
    for aid, grp in act.groupby("account_id"):
        code = code_of.get(int(aid))
        if code is None:
            continue
        idx = grp.index
        arr = leaf[code]
        arr[act.loc[idx, "bu_id"].map(bpos).to_numpy(), act.loc[idx, "month_key"].map(tpos).to_numpy()] = (
            grp["amount_usd"].astype(float).to_numpy())
    del bi, ti_
    lines = sorted(set(leaf_line.values()))
    act_lines = {ln: np.nansum(np.stack([leaf[c] for c in leaf if leaf_line[c] == ln]), axis=0) for ln in lines}
    closed = np.array([k < mask_from for k in months])
    for ln in act_lines:
        act_lines[ln][:, ~closed] = np.nan
    ver: dict[str, dict[int, np.ndarray]] = {}
    for (vname, ln), grp in other.groupby(["version", "line_no"]):
        arr = np.full((B, T), np.nan)
        g = grp.groupby(["bu_id", "month_key"])["amount_usd"].sum().reset_index()
        arr[g["bu_id"].map(bpos).to_numpy(), g["month_key"].map(tpos).to_numpy()] = g["amount_usd"].astype(float)
        ver.setdefault(str(vname), {})[int(ln)] = arr
    wdp = wdf.pivot_table(index="country", columns="month_key", values="working_days")
    countries = org["l3_country"].tolist()
    wd = np.array([[float(wdp.loc[c, k]) if k in wdp.columns else np.nan for k in months] for c in countries])
    typ = np.zeros((B, 12))
    for c in range(12):
        cols = [t for t, k in enumerate(months) if k % 100 == c + 1]
        typ[:, c] = np.nanmean(wd[:, cols], axis=1)
    return Data(bu_ids=bu_ids, org=org, months=months, act=act_lines, ver=ver, leaf=leaf, leaf_line=leaf_line,
                leaf_id=leaf_id, wd=wd, wd_typical=typ, mtd=mtd)


# ------------------------------------------------------------------------------------------
# Profiles and pattern classes
# ------------------------------------------------------------------------------------------
@dataclass
class Profile:
    cls: np.ndarray            # (B,) class names
    si: np.ndarray             # (B, 12) seasonal index (mean 1), shrunk toward the product line
    qe_share: np.ndarray
    dec_share: np.ndarray
    cv: np.ndarray
    amplitude: np.ndarray
    n_months: int
    shrink_w: np.ndarray


def classify(qe_share, dec_share, dec_vs_qe, cv, amplitude) -> np.ndarray:
    """Rules on the BU's own shares (order matters): lumpy, year-end, quarter-end, seasonal, steady."""
    out = np.full(len(cv), "steady", dtype=object)
    seasonal = amplitude >= 0.30
    qe = qe_share >= 0.39
    ye = (dec_share >= 0.125) & (dec_vs_qe >= 1.35)
    out[seasonal] = "seasonal"
    out[qe] = "quarter_end"
    out[ye] = "year_end"
    out[cv >= 0.08] = "lumpy"
    return out


def profile_at(N: np.ndarray, o: int, months: list[int], pl: np.ndarray, min_months: int) -> Profile:
    """Profile each BU from the (working-day adjusted) months before origin `o` (up to 4 years)."""
    B = N.shape[0]
    n_win = min(4, o // 12)
    if n_win == 0:
        ones = np.ones((B, 12))
        z = np.zeros(B)
        return Profile(np.full(B, "steady", dtype=object), ones, z + 0.25, z + 1 / 12, z, z, o, z)
    shares, fitted_err = [], []
    for k in range(n_win):
        lo, hi = o - 12 * (k + 1), o - 12 * k
        win = N[:, lo:hi]
        tot = np.nansum(win, axis=1, keepdims=True)
        s = win / np.where(tot > 0, tot, np.nan)
        cal = [months[t] % 100 - 1 for t in range(lo, hi)]
        sc = np.zeros((B, 12))
        sc[:, cal] = s
        shares.append(sc)
    S = np.nanmean(np.stack(shares), axis=0)
    si_raw = 12 * S
    for k in range(n_win):
        lo, hi = o - 12 * (k + 1), o - 12 * k
        win = N[:, lo:hi]
        mean = np.nanmean(win, axis=1, keepdims=True)
        cal = [months[t] % 100 - 1 for t in range(lo, hi)]
        fitted_err.append(win / (mean * si_raw[:, cal]) - 1)
    cv = np.nanstd(np.concatenate(fitted_err, axis=1), axis=1)
    qe_share = S[:, [2, 5, 8, 11]].sum(axis=1)
    dec_share = S[:, 11]
    dec_vs_qe = S[:, 11] / np.maximum(S[:, [2, 5, 8]].mean(axis=1), 1e-9)
    amplitude = si_raw[:, 2] - si_raw[:, 7]
    cls = classify(qe_share, dec_share, dec_vs_qe, cv, amplitude)
    n_months = min(o, 48)
    k0 = np.where(cls == "lumpy", 3.0, 1.0 if n_months >= min_months else 2.0)
    w = n_win / (n_win + k0)
    si_pl = np.zeros_like(si_raw)
    for p in np.unique(pl):
        sel = pl == p
        si_pl[sel] = np.nanmean(si_raw[sel], axis=0)
    si = w[:, None] * si_raw + (1 - w[:, None]) * si_pl
    si = si / si.mean(axis=1, keepdims=True)
    return Profile(cls, si, qe_share, dec_share, cv, amplitude, n_months, w)


# ------------------------------------------------------------------------------------------
# Methods
# ------------------------------------------------------------------------------------------
def wd_beta(A: np.ndarray, wd: np.ndarray, o: int) -> float:
    """Working-day elasticity from history: year-on-year log changes of billing vs of working days,
    demeaned per BU (removes growth). Falls back to 0.5 when the calendar barely moves."""
    lo = max(12, o - 36)
    if o - lo < 6:
        return 0.5
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.log(A[:, lo:o] / A[:, lo - 12:o - 12])
        x = np.log(wd[:, lo:o] / wd[:, lo - 12:o - 12])
    ok = np.isfinite(y) & np.isfinite(x)
    y = np.where(ok, y, np.nan)
    x = np.where(ok, x, np.nan)
    y = y - np.nanmean(y, axis=1, keepdims=True)
    x = x - np.nanmean(x, axis=1, keepdims=True)
    sxx = np.nansum(x * x)
    if sxx < 1e-4:
        return 0.5
    return float(np.clip(np.nansum(x * y) / sxx, 0.0, 1.5))


def wd_factor(d: Data, beta: float) -> np.ndarray:
    """(working days / typical working days for that calendar month) ** beta, shape (B, T)."""
    cal = np.array([k % 100 - 1 for k in d.months])
    return (d.wd / d.wd_typical[:, cal]) ** beta


def m1_yoy(N: np.ndarray, o: int, f_o: np.ndarray) -> np.ndarray:
    if o < 15:
        return np.full(N.shape[0], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        g3 = N[:, o - 3:o].sum(axis=1) / N[:, o - 15:o - 12].sum(axis=1)
        g6 = N[:, o - 6:o].sum(axis=1) / N[:, o - 18:o - 12].sum(axis=1) if o >= 18 else g3
    g = np.where(np.isfinite(g6), 0.5 * (g3 + g6), g3)
    return N[:, o - 12] * np.clip(g, 0.6, 1.6) * f_o


def m2_seasonal(N: np.ndarray, o: int, f_o: np.ndarray, si: np.ndarray, c: int) -> np.ndarray:
    if o < 12:
        return np.full(N.shape[0], np.nan)
    t12 = N[:, o - 12:o].mean(axis=1)
    g = np.ones(N.shape[0])
    if o >= 24:
        with np.errstate(divide="ignore", invalid="ignore"):
            g = np.clip(N[:, o - 12:o].sum(axis=1) / N[:, o - 24:o - 12].sum(axis=1), 0.7, 1.4)
    return t12 * si[:, c] * g ** (6.5 / 12) * f_o


def m3_forecast_bias(A: np.ndarray, Fh: np.ndarray, o: int, F_o: np.ndarray, n0: float,
                     same_type: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Latest forecast x the BU's actual / forecast ratio over the last 24 origins (same forecast type
    when there are at least 4 such months), shrunk toward 1 by n / (n + n0)."""
    lo = max(0, o - 24)
    a, f = A[:, lo:o], Fh[:, lo:o]
    ok = np.isfinite(a) & np.isfinite(f) & (f > 0)
    if same_type is not None:
        st = same_type[lo:o][None, :] & ok
        use = np.where(st.sum(axis=1, keepdims=True) >= 4, st, ok)
    else:
        use = ok
    n = use.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(n > 0, np.nansum(np.where(use, a, 0), axis=1) / np.nansum(np.where(use, f, 0), axis=1), 1.0)
    ratio = np.clip(ratio, 0.5, 1.5)
    r = 1 + n / (n + n0) * (ratio - 1)
    return F_o * r, r


def _ets_one(args) -> float:
    y, = args
    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # noqa: WPS433 (heavy import, batch only)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal="mul", seasonal_periods=12,
                                       initialization_method="estimated").fit(optimized=True)
            val = float(fit.forecast(1)[0])
        return val if np.isfinite(val) else np.nan
    except Exception:  # noqa: BLE001
        return np.nan


def m4_ets(series_by_origin: dict[int, np.ndarray], min_months: int, workers: int | None = None) -> dict[int, np.ndarray]:
    """1-step ETS forecasts of each origin's adjusted series for every BU with enough history."""
    jobs, keys = [], []
    for o, N in series_by_origin.items():
        if o < min_months:
            continue
        for b in range(N.shape[0]):
            y = N[b, max(0, o - 48):o]
            if np.all(np.isfinite(y)) and np.all(y > 0):
                jobs.append((y,))
                keys.append((o, b))
    out = {o: np.full(N.shape[0], np.nan) for o, N in series_by_origin.items()}
    if not jobs:
        return out
    n = workers or min(12, os.cpu_count() or 2)
    if n > 1 and len(jobs) > 50:
        with ProcessPoolExecutor(max_workers=n) as ex:
            vals = list(ex.map(_ets_one, jobs, chunksize=16))
    else:
        vals = [_ets_one(j) for j in jobs]
    for (o, b), v in zip(keys, vals):
        N = series_by_origin[o]
        lo = np.nanmean(N[b, max(0, o - 12):o])
        out[o][b] = float(np.clip(v, 0.3 * lo, 3.0 * lo)) if np.isfinite(v) else np.nan
    return out


def blend_weights(wape_bu: np.ndarray, inv_class: np.ndarray, avail: np.ndarray, n: float, n0: float) -> np.ndarray:
    """Ensemble weights of one BU over METHODS: inverse trailing WAPE of the BU's own methods, shrunk toward
    its pattern class (inverse class WAPE) by n / (n + n0), where n = months in the BU's error window.
    Methods without a prediction get weight 0; the weights sum to 1 (all 0 if no method is available)."""
    avail = np.asarray(avail, dtype=bool)
    if not avail.any():
        return np.zeros(len(avail))
    inv_bu = np.where(np.isfinite(wape_bu), 1 / np.maximum(wape_bu, 0.01), 0.0)
    wb = np.where(avail, inv_bu, 0.0)
    wc = np.where(avail, inv_class, 0.0)
    wb = wb / wb.sum() if wb.sum() > 0 else None
    wc = wc / wc.sum() if wc.sum() > 0 else None
    lam = n / (n + n0)
    if wb is None and wc is None:
        wv = avail / avail.sum()
    elif wb is None:
        wv = wc
    elif wc is None:
        wv = wb
    else:
        wv = lam * wb + (1 - lam) * wc
    return wv / wv.sum()


# ------------------------------------------------------------------------------------------
# Rolling run over origins
# ------------------------------------------------------------------------------------------
@dataclass
class Rolling:
    origins: list[int]                         # origin indices (t)
    live: int                                  # index of the open month of the run
    pred: dict[str, np.ndarray]                # method -> (B, T) billing predictions
    p50: np.ndarray                            # (B, T) ensemble
    q10: np.ndarray                            # (B, T) log quantiles used for P10 / P90
    q90: np.ndarray
    resid: np.ndarray                          # (B, T) log(actual / P50)
    weights: dict[int, np.ndarray]             # origin -> (B, M) weights over METHODS
    wape: dict[int, np.ndarray]                # origin -> (B, M) trailing WAPE per method
    profiles: dict[int, Profile]
    beta: dict[int, float]
    fversion: dict[int, str]                   # origin -> forecast version used
    bias_ratio: dict[int, np.ndarray]


def origin_as_of(key: int, live_key: int, as_of: date) -> date:
    return as_of if key == live_key else date(key // 100, key % 100, 15)


def rolling(d: Data, as_of: date | None = None, first_origin: int = FIRST_ORIGIN_INDEX,
            workers: int | None = None) -> Rolling:
    as_of = as_of or as_of_date()
    c = cfg()
    live_key = open_month(as_of)
    live = d.idx(live_key)
    origins = list(range(first_origin, live + 1))
    A = d.act[1]
    B, T = A.shape
    pl = d.org["l4_product_line"].to_numpy()
    # forecast available at each origin for its own month (history for M3 and the plain baseline)
    fversion = {t: latest_version(d.months[t] // 100, origin_as_of(d.months[t], live_key, as_of)) for t in range(T)}
    Fh = np.full((B, T), np.nan)
    for t in range(T):
        Fh[:, t] = d.ver[fversion[t]][1][:, t]
    pred = {m: np.full((B, T), np.nan) for m in (*METHODS, BASELINE)}
    profiles, betas, bias_ratio, Ns = {}, {}, {}, {}
    for o in origins:
        beta = wd_beta(A, d.wd, o)
        f = wd_factor(d, beta)
        N = A / f
        Ns[o] = N
        prof = profile_at(N, o, d.months, pl, int(c["profile_min_months"]))
        cm = d.cal(o)
        same_type = np.array([fversion[t] == fversion[o] for t in range(T)])
        pred["M1_yoy"][:, o] = m1_yoy(N, o, f[:, o])
        pred["M2_seasonal"][:, o] = m2_seasonal(N, o, f[:, o], prof.si, cm)
        pred["M3_forecast_bias"][:, o], bias_ratio[o] = m3_forecast_bias(A, Fh, o, Fh[:, o], float(c["shrink_origins"]),
                                                                         same_type)
        pred[BASELINE][:, o] = Fh[:, o]
        profiles[o], betas[o] = prof, beta
    # ETS on each origin's own adjusted series (one batch for all origins)
    ets_jobs = {o: Ns[o] for o in origins if o >= int(c["ets_min_months"])}
    if ets_jobs:
        ets = m4_ets(ets_jobs, int(c["ets_min_months"]), workers)
        for o, v in ets.items():
            f = wd_factor(d, betas[o])
            pred["M4_ets"][:, o] = v * f[:, o]
    # ensemble, residuals and intervals in time order (weights only use earlier origins)
    M = len(METHODS)
    P = np.stack([pred[m] for m in METHODS], axis=-1)            # (B, T, M)
    p50 = np.full((B, T), np.nan)
    resid = np.full((B, T), np.nan)
    q10 = np.full((B, T), np.nan)
    q90 = np.full((B, T), np.nan)
    weights, wapes = {}, {}
    ww, rw, n0 = int(c["weight_window"]), int(c["residual_window"]), float(c["shrink_origins"])
    for o in origins:
        win = [k for k in origins if o - ww <= k < o]
        avail = np.isfinite(P[:, o, :])
        wape = np.full((B, M), np.nan)
        cnt = np.zeros((B, M))
        if win:
            a = A[:, win][:, :, None]
            e = np.abs(a - P[:, win, :])
            ok = np.isfinite(e)
            cnt = ok.sum(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                wape = np.where(cnt >= 3, np.nansum(np.where(ok, e, 0), axis=1)
                                / np.nansum(np.where(ok, np.abs(a), 0), axis=1), np.nan)
        cls = profiles[o].cls
        w_cls = np.zeros((B, M))
        for k in CLASSES:
            sel = cls == k
            if not sel.any() or not win:
                continue
            a = A[sel][:, win][:, :, None]
            e = np.abs(a - P[sel][:, win, :])
            ok = np.isfinite(e) & np.isfinite(a)
            with np.errstate(divide="ignore", invalid="ignore"):
                cw = np.nansum(np.where(ok, e, 0), axis=(0, 1)) / np.nansum(np.where(ok, np.abs(a), 0), axis=(0, 1))
            inv = np.where(np.isfinite(cw) & (ok.sum(axis=(0, 1)) >= 3), 1 / np.maximum(cw, 0.01), 0.0)
            w_cls[sel] = inv
        w = np.zeros((B, M))
        for b in range(B):
            n = float(np.nanmax(np.where(avail[b], cnt[b], 0))) if win else 0.0
            w[b] = blend_weights(wape[b], w_cls[b], avail[b], n, n0)
        weights[o], wapes[o] = w, wape
        p50[:, o] = np.nansum(np.where(avail, P[:, o, :] * w, 0.0), axis=1)
        p50[~avail.any(axis=1), o] = np.nan
        # P10 / P90 from earlier ensemble errors (per BU with enough history, else the BU's class)
        rwin = [k for k in origins if o - rw <= k < o]
        R = resid[:, rwin] if rwin else np.full((B, 0), np.nan)
        nb = np.isfinite(R).sum(axis=1)
        for k in CLASSES:
            sel = cls == k
            pool = R[sel][np.isfinite(R[sel])]
            if pool.size >= 10:
                lo_c, hi_c = np.quantile(pool, [0.1, 0.9])
            else:
                allp = R[np.isfinite(R)]
                lo_c, hi_c = (np.quantile(allp, [0.1, 0.9]) if allp.size >= 10 else (-0.08, 0.08))
            q10[sel, o], q90[sel, o] = lo_c, hi_c
        for b in np.where(nb >= int(c["min_bu_residuals"]))[0]:
            r = R[b][np.isfinite(R[b])]
            q10[b, o], q90[b, o] = np.quantile(r, [0.1, 0.9])
        q10[:, o] = np.minimum(q10[:, o], 0.0)
        q90[:, o] = np.maximum(q90[:, o], 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            resid[:, o] = np.log(A[:, o] / p50[:, o])
    return Rolling(origins=origins, live=live, pred=pred, p50=p50, q10=q10, q90=q90, resid=resid, weights=weights,
                   wape=wapes, profiles=profiles, beta=betas, fversion=fversion, bias_ratio=bias_ratio)


# ------------------------------------------------------------------------------------------
# Cost lines at an origin
# ------------------------------------------------------------------------------------------
def _safe_div(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(b) > 1e-9, a / b, np.nan)


def cost_lines(d: Data, o: int, version: str) -> dict:
    """Ratios to billing and fixed amounts per BU (signed, like the ledger) for origin `o`."""
    L = d.act
    B = d.B

    def same_month_ratio(line: int) -> np.ndarray:
        vals = [_safe_div(L[line][:, o - j], L[1][:, o - j]) for j in (12, 24) if o - j >= 0]
        r = np.nanmean(np.stack(vals), axis=0) if vals else np.full(B, np.nan)
        recent = _safe_div(np.nansum(L[line][:, o - 3:o], axis=1), np.nansum(L[1][:, o - 3:o], axis=1))
        return np.where(np.isfinite(r), r, recent)

    def blended_ratio(line: int) -> np.ndarray:
        recent = _safe_div(np.nansum(L[line][:, o - 3:o], axis=1), np.nansum(L[1][:, o - 3:o], axis=1))
        py = _safe_div(L[line][:, o - 12], L[1][:, o - 12]) if o >= 12 else recent
        return np.where(np.isfinite(py), 0.5 * recent + 0.5 * py, recent)

    base7 = np.nanmean(L[7][:, o - 3:o], axis=1)
    sfs = [_safe_div(L[7][:, o - j], np.nanmean(L[7][:, o - j - 3:o - j], axis=1))
           for j in (12, 24) if o - j - 3 >= 0]
    sf = np.nanmean(np.stack(sfs), axis=0) if sfs else np.ones(B)
    sf = np.where(np.isfinite(sf), sf, 1.0)
    fv = d.ver.get(version) or d.ver["Budget"]
    return {"r4": same_month_ratio(4), "r5": same_month_ratio(5), "r8": blended_ratio(8), "r9": blended_ratio(9),
            "L7": base7 * sf, "L7_sf": sf, "L10": fv[10][:, o], "L12": fv[12][:, o]}


def measures_from_billing(b, cl: dict, idx=None) -> dict:
    """Landing measures for billing value(s) b (signed amounts; WIP = 0 so revenue = billing)."""
    g = (lambda k: cl[k]) if idx is None else (lambda k: cl[k][idx])
    r4, r5, r8, r9 = g("r4"), g("r5"), g("r8"), g("r9")
    L7, L10, L12 = g("L7"), g("L10"), g("L12")
    rev = b
    l4, l5, l8, l9 = r4 * b, r5 * b, r8 * b, r9 * b
    prod = rev + l4 + l5
    gp = prod + L7 + l8 + l9 + L10
    maop = gp + L12
    return {"billing": b, "wip_ui": 0 * b, "revenue": rev, "intragroup_revenue": l4,
            "intragroup_subcontracting": l5, "production": prod, "personnel": L7 + 0 * b, "subcontracting": l8,
            "other_cost": l9, "functional_neutralization": L10 + 0 * b, "gross_profit": gp,
            "functional_cost": L12 + 0 * b, "maop": maop}


def margin(num, den):
    """Ratio of sums; n/a (NaN) when the denominator is zero or negative (never divides by zero)."""
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)


# ------------------------------------------------------------------------------------------
# Simulation for aggregates (P50 = exact sum of BU P50s; P10 / P90 from draws)
# ------------------------------------------------------------------------------------------
def simulate(p50: np.ndarray, resid: np.ndarray, draws: int, seed: int) -> np.ndarray:
    """Billing draws (D, B): common shock of a random past origin + BU-specific error of another random
    past origin (keeps the correlation between BUs while smoothing the distribution). The common shock is
    the size-weighted average error of the BUs in scope at that origin."""
    B = len(p50)
    rng = np.random.default_rng(seed)
    R = np.asarray(resid, dtype=float).reshape(B, -1)
    if R.shape[1] == 0 or not np.isfinite(R).any():
        return np.tile(p50, (draws, 1))
    w = np.abs(np.asarray(p50, dtype=float))
    w = w / w.sum() if w.sum() > 0 else np.full(B, 1.0 / B)
    fin = np.isfinite(R)
    with np.errstate(invalid="ignore", divide="ignore"):
        common = np.where(fin.any(axis=0), np.nansum(np.where(fin, R * w[:, None], 0.0), axis=0)
                          / np.maximum((fin * w[:, None]).sum(axis=0), 1e-12), np.nan)   # (W,)
    good_t = np.where(np.isfinite(common))[0]
    idio = R - common[None, :]
    t1 = rng.choice(good_t, size=draws)
    out = np.empty((draws, B))
    pool = idio[np.isfinite(idio)]
    for b in range(B):
        valid = np.where(np.isfinite(idio[b]))[0]
        if valid.size >= 6:
            e = idio[b, rng.choice(valid, size=draws)]
        elif pool.size:
            e = rng.choice(pool, size=draws)
        else:
            e = np.zeros(draws)
        out[:, b] = p50[b] * np.exp(common[t1] + e)
    return out


def quantiles(x: np.ndarray, axis=0) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = np.nanquantile(x, [0.1, 0.9], axis=axis)
    return lo, hi


# ------------------------------------------------------------------------------------------
# Today's landing (one origin) -> rows for the landing tables
# ------------------------------------------------------------------------------------------
def allocate_leaves(d: Data, o: int, line_vals: dict[int, np.ndarray]) -> dict[str, np.ndarray]:
    """Split each line's P50 (cents) over its leaf accounts; shares from recent months (personnel from the
    same month last year, which carries the March bonus). Leaves add up exactly to the line."""
    out = {}
    for ln, total in line_vals.items():
        codes = [c for c in d.leaf if d.leaf_line[c] == ln]
        if ln == 2:
            for c in codes:
                out[c] = np.zeros(d.B)
            continue
        if len(codes) == 1:
            out[codes[0]] = total.copy()
            continue
        src = [o - 12] if (ln == 7 and o >= 12) else list(range(max(0, o - 3), o))
        if ln == 1:
            src = list(range(max(0, o - 12), o))
        mat = np.stack([np.nansum(d.leaf[c][:, src], axis=1) for c in codes], axis=1)
        tot = mat.sum(axis=1, keepdims=True)
        share = np.where(np.abs(tot) > 1e-9, mat / np.where(np.abs(tot) > 1e-9, tot, 1.0), 1.0 / len(codes))
        vals = np.round(share * total[:, None], 2)
        vals[:, -1] = np.round(total - vals[:, :-1].sum(axis=1), 2)
        for i, c in enumerate(codes):
            out[c] = vals[:, i]
    return out


def landing_rows(d: Data, r: Rolling, as_of: date) -> dict[str, pd.DataFrame]:
    """Rows for fact_landing, fact_landing_leaf, landing_method, landing_bu_profile, landing_residual."""
    o = r.live
    key = d.months[o]
    version = r.fversion[o]
    cl = cost_lines(d, o, version)
    b50 = r.p50[:, o].copy()
    q10, q90 = r.q10[:, o].copy(), r.q90[:, o].copy()
    b50, q10, q90, mtd_used = maybe_apply_mtd(d, o, as_of, b50, q10, q90)
    b50 = np.round(b50, 2)
    # line P50s in cents; derived measures from the rounded lines (exact reconciliation)
    lines = {1: b50, 2: np.zeros(d.B), 4: np.round(cl["r4"] * b50, 2), 5: np.round(cl["r5"] * b50, 2),
             7: np.round(cl["L7"], 2), 8: np.round(cl["r8"] * b50, 2), 9: np.round(cl["r9"] * b50, 2),
             10: np.round(cl["L10"], 2), 12: np.round(cl["L12"], 2)}
    leaves = allocate_leaves(d, o, lines)
    b10, b90 = b50 * np.exp(q10), b50 * np.exp(q90)
    m10, m50, m90 = measures_from_billing(b10, cl), None, measures_from_billing(b90, cl)
    m50 = {"billing": lines[1], "wip_ui": lines[2], "revenue": lines[1], "intragroup_revenue": lines[4],
           "intragroup_subcontracting": lines[5], "personnel": lines[7], "subcontracting": lines[8],
           "other_cost": lines[9], "functional_neutralization": lines[10], "functional_cost": lines[12]}
    m50["production"] = lines[1] + lines[4] + lines[5]
    m50["gross_profit"] = m50["production"] + lines[7] + lines[8] + lines[9] + lines[10]
    m50["maop"] = m50["gross_profit"] + lines[12]
    for name, den in (("maop_margin_revenue", "revenue"), ("maop_margin_production", "production")):
        m10[name] = margin(m10["maop"], m10[den])
        m90[name] = margin(m90["maop"], m90[den])
        m50[name] = margin(m50["maop"], m50[den])
    prof = r.profiles[o]
    w = r.weights[o]
    rows, mrows, prow, rrows, lrows = [], [], [], [], []
    snap = as_of
    for b in range(d.B):
        bu = int(d.bu_ids[b])
        wj = json.dumps({m: round(float(w[b, i]), 4) for i, m in enumerate(METHODS) if w[b, i] > 0})
        cls = str(prof.cls[b])
        for meas in (*LINE_MEASURE.values(), *DERIVED_MEASURES):
            v50 = m50[meas][b]
            lo, hi = sorted([float(m10[meas][b]), float(m90[meas][b])]) if np.isfinite(m10[meas][b]) else (np.nan, np.nan)
            v50f = float(v50)
            if np.isfinite(v50f) and np.isfinite(lo):
                lo, hi = min(lo, v50f), max(hi, v50f)
            rows.append({"snapshot_date": snap, "month_key": key, "bu_id": bu, "measure": meas,
                         "p10": _num(lo), "p50": _num(v50f), "p90": _num(hi), "method_weights_json": wj,
                         "pattern_class": cls})
        for i, m in enumerate((*METHODS, BASELINE)):
            val = r.pred[m][b, o]
            detail = {}
            if m == "M3_forecast_bias":
                detail = {"forecast": version, "ratio": round(float(r.bias_ratio[o][b]), 4)}
            elif m == BASELINE:
                detail = {"forecast": version}
            mrows.append({"snapshot_date": snap, "month_key": key, "bu_id": bu, "method": m,
                          "prediction": _num(val, 2),
                          "weight": _num(w[b, i], 6) if i < len(METHODS) else 0.0,
                          "backtest_wape": _num(r.wape[o][b, i], 6) if i < len(METHODS) else None,
                          "detail_json": json.dumps(detail) if detail else None})
        prow.append({"snapshot_date": snap, "bu_id": bu, "pattern_class": cls, "n_months": int(prof.n_months),
                     "quarter_end_share": _num(prof.qe_share[b], 6), "december_share": _num(prof.dec_share[b], 6),
                     "cv": _num(prof.cv[b], 6), "seasonal_amplitude": _num(prof.amplitude[b], 6),
                     "shrink_weight": _num(prof.shrink_w[b], 6),
                     "seasonal_index_json": json.dumps([round(float(x), 4) for x in prof.si[b]])})
        for t in r.origins:
            if t < o and o - int(cfg()["residual_window"]) <= t and np.isfinite(r.resid[b, t]):
                rrows.append({"snapshot_date": snap, "bu_id": bu, "origin_month_key": d.months[t],
                              "log_error": round(float(r.resid[b, t]), 8)})
        for code, vals in leaves.items():
            lrows.append({"snapshot_date": snap, "month_key": key, "bu_id": bu, "account_id": d.leaf_id[code],
                          "amount_usd": float(vals[b])})
    return {"fact_landing": pd.DataFrame(rows), "fact_landing_leaf": pd.DataFrame(lrows),
            "landing_method": pd.DataFrame(mrows), "landing_bu_profile": pd.DataFrame(prow),
            "landing_residual": pd.DataFrame(rrows), "_meta": {"mtd_used": mtd_used, "version": version,
                                                               "month_key": key, "beta": r.beta[o]}}


def maybe_apply_mtd(d, o: int, as_of: date, b50, q10, q90):
    """The month-to-date input is used only when landing.mtd_snapshot_enabled is true and snapshots exist;
    otherwise the model landing is returned unchanged (the default: no MTD data in this prototype)."""
    if bool(cfg()["mtd_snapshot_enabled"]) and getattr(d, "mtd", None):
        return apply_mtd(d, o, as_of, b50, q10, q90)
    return b50, q10, q90, False


def apply_mtd(d: Data, o: int, as_of: date, b50, q10, q90):
    """Optional month-to-date input (off by default): blend the run-rate of the elapsed working days with
    the model P50, and narrow the interval by the share of the month still open."""
    from app.db import dim_calendar  # noqa: WPS433

    eng = get_engine(admin=True)
    y, m = d.months[o] // 100, d.months[o] % 100
    with eng.connect() as conn:
        cal = pd.read_sql(select(dim_calendar).where(dim_calendar.c.date >= date(y, m, 1)), conn)
    cal = cal[pd.to_datetime(cal["date"]).dt.month == m]
    used = False
    for b, bu in enumerate(d.bu_ids):
        if int(bu) not in d.mtd:
            continue
        country = d.org.loc[b, "l3_country"]
        cc = cal[cal["country"] == country]
        tot = cc["is_working_day"].sum()
        done = cc[pd.to_datetime(cc["date"]).dt.date < as_of]["is_working_day"].sum()
        f = float(done) / float(tot) if tot else 0.0
        if f <= 0:
            continue
        mtd = d.mtd[int(bu)]
        b50[b] = mtd + (1 - f) * b50[b]
        q10[b] *= (1 - f)
        q90[b] *= (1 - f)
        used = True
    return b50, q10, q90, used


def _num(x, nd: int = 6):
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    return round(xf, nd) if np.isfinite(xf) else None
