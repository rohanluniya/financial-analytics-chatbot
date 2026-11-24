#!/usr/bin/env python
"""Compute the current-month landing for an as-of date and store it (fact_landing and friends).

    make landing                    # as-of date from config/settings.yaml (or AS_OF_DATE in .env)
    make landing AS_OF=2026-09-15   # a past date: only data available on that date is used

Idempotent: re-running for the same as-of date replaces that snapshot. Monthly data only (actuals,
Budget, FC1-FC3); WIP is 0 in the landing month, so revenue = billing.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import as_of_date  # noqa: E402
from app.landing import engine as E  # noqa: E402
from app.landing.store import Timer, write_snapshot  # noqa: E402
from app.semantic import time_intel as ti  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="as-of date YYYY-MM-DD (default: settings / AS_OF_DATE)")
    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else as_of_date()
    if as_of > as_of_date():
        raise SystemExit(f"--as-of {as_of} is after the data as-of date {as_of_date()}")
    timer = Timer()
    key = E.open_month(as_of)
    print(f"Landing for {ti.month_label(key)} as of {as_of} (last closed month {ti.month_label(ti.add_months(key, -1))})")
    d = E.load_data(as_of)
    r = E.rolling(d, as_of)
    rows = E.landing_rows(d, r, as_of)
    counts = write_snapshot(rows, as_of, key, timer.seconds,
                            notes=f"forecast used: {rows['_meta']['version']}; working-day elasticity "
                                  f"{rows['_meta']['beta']:.2f}")
    fl = rows["fact_landing"]
    tot = fl.groupby("measure")["p50"].sum()
    print(f"  {fl.bu_id.nunique()} BUs, latest forecast used: {rows['_meta']['version']}, "
          f"MTD input: {'on' if rows['_meta']['mtd_used'] else 'off'}")
    o = r.live
    rwin = [k for k in r.origins if o - int(E.cfg()["residual_window"]) <= k < o]
    sims = E.simulate(r.p50[:, o], r.resid[:, rwin], int(E.cfg()["simulation_draws"]), seed=key).sum(axis=1)
    lo, hi = np.quantile(sims, [0.1, 0.9])
    print(f"  billing     P50 {tot['billing']:>16,.0f}  group P10-P90 {lo:,.0f} - {hi:,.0f}")
    for m in ("revenue", "production", "maop"):
        print(f"  {m:<11} P50 {tot[m]:>16,.0f}")
    print(f"  operating margin on revenue {100 * tot['maop'] / tot['revenue']:.2f}%, "
          f"on production {100 * tot['maop'] / tot['production']:.2f}% (ratios of sums)")
    print("  rows:", counts)
    print(f"Done in {timer.seconds:.1f}s")


if __name__ == "__main__":
    main()
