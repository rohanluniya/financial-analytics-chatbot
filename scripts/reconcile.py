#!/usr/bin/env python
"""Reconciliation report.

1. Row counts per table and per version.
2. 50 random BU x month x version samples: subtotals (Revenue, Production, Gross profit, Operating
   profit, EBIT, Net income)
   computed by the semantic layer == independent raw-SQL leaf sums == the generator's intended
   control totals.
3. Integrity checks: facts only on leaf accounts, no Actuals for open months, forecast actual
   months identical to Actuals, identical totals in SQL Server and DuckDB (when both exist), employee
   totals (headcount, FTE, hours) identical to the BU statistics, one hire/leave flag per employee.
Writes results/reconcile_report.md and exits non-zero on any mismatch.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import backend, data_as_of_date, settings  # noqa: E402
from app.db import TABLE_LOAD_ORDER, duckdb_path, get_engine  # noqa: E402
from app.semantic import time_intel as ti  # noqa: E402
from app.semantic.dims import dims  # noqa: E402
from app.semantic.query_builder import SemanticLayer  # noqa: E402

SUBTOTALS = {"revenue": ("L3", [1, 2]), "production": ("L6", [1, 2, 4, 5]),
             "gross_profit": ("L11", [1, 2, 4, 5, 7, 8, 9, 10]),
             "maop": ("L13", [1, 2, 4, 5, 7, 8, 9, 10, 12]),
             "management_op": ("L18", [1, 2, 4, 5, 7, 8, 9, 10, 12, 17]),
             "net_income": ("L21", [1, 2, 4, 5, 7, 8, 9, 10, 12, 17, 19, 20])}
TOL_SQL = 0.005       # semantic layer vs raw SQL (same stored cents)
TOL_CTRL = 0.15       # vs generator intent (rounding of up to 37 leaves to cents)


def raw_engine():
    return get_engine(admin=True) if backend() == "mssql" else get_engine("__reconcile__")


def q(conn, sql: str, **params):
    return conn.execute(text(sql), params).fetchall()


def main(n_samples: int = 50) -> int:
    lines_out: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines_out.append(s)

    eng = raw_engine()
    d = dims()
    vname = dict(zip(d.version["version_id"].astype(int), d.version["name"]))
    out(f"# Reconciliation report ({backend()} backend)\n")
    with eng.connect() as conn:
        out("## Row counts per table\n")
        out("| Table | Rows |\n|---|---:|")
        for t in TABLE_LOAD_ORDER:
            out(f"| {t} | {q(conn, f'SELECT COUNT(*) FROM {t}')[0][0]:,} |")
        out("\n## fact_pnl rows and totals per version\n")
        out("| Version | Rows | Months | Sum of signed amounts (USD) |\n|---|---:|---:|---:|")
        per_version = q(conn, "SELECT version_id, COUNT(*), COUNT(DISTINCT month_key), SUM(amount_usd) "
                              "FROM fact_pnl GROUP BY version_id ORDER BY version_id")
        for vid, cnt, months, total in per_version:
            out(f"| {vname[int(vid)]} | {cnt:,} | {months} | {float(total):,.2f} |")

        # integrity checks
        checks = []
        non_leaf = q(conn, "SELECT COUNT(*) FROM fact_pnl f JOIN dim_account a ON a.account_id = f.account_id "
                           "WHERE a.is_leaf = :f", f=False)[0][0]
        checks.append(("Fact rows on non-leaf (subtotal/header) accounts", non_leaf, 0))
        open_actuals = q(conn, "SELECT COUNT(*) FROM fact_pnl f JOIN dim_period p ON p.month_key = f.month_key "
                               "WHERE f.version_id = 1 AND p.close_date > :d", d=data_as_of_date())[0][0]
        checks.append(("Actual rows for months not yet closed", open_actuals, 0))
        fc_months = {k: int(v["actual_months"]) for k, v in settings()["forecasts"].items()}
        diff_cnt = 0
        for fc, k in fc_months.items():
            fid = int(d.version.loc[d.version["name"] == fc, "version_id"].iloc[0])
            rows = q(conn, "SELECT a.month_key, a.s, b.s FROM "
                           "(SELECT month_key, SUM(amount_usd) s FROM fact_pnl WHERE version_id = 1 GROUP BY month_key) a "
                           "JOIN (SELECT month_key, SUM(amount_usd) s FROM fact_pnl WHERE version_id = :fid GROUP BY month_key) b "
                           "ON a.month_key = b.month_key", fid=fid)
            for mkey, s_act, s_fc in rows:
                if int(mkey) % 100 <= k and abs(float(s_act) - float(s_fc)) > 0.005:
                    diff_cnt += 1
        checks.append(("Forecast actual-months differing from Actual (month totals)", diff_cnt, 0))

        # employees: monthly totals per BU must equal the Actual BU statistics
        emp_mism = q(conn, """
            SELECT COUNT(*) FROM fact_stats s
            LEFT JOIN (SELECT bu_id, month_key, COUNT(*) AS hc, SUM(fte) AS fte, SUM(available_hours) AS av,
                              SUM(billable_hours) AS bi, SUM(overtime_hours) AS ot
                       FROM fact_employee_month GROUP BY bu_id, month_key) e
              ON e.bu_id = s.bu_id AND e.month_key = s.month_key
            WHERE s.version_id = 1 AND (e.hc IS NULL OR ABS(s.headcount - e.hc) > 0.005 OR ABS(s.fte - e.fte) > 0.005
                  OR ABS(s.available_hours - e.av) > 0.05 OR ABS(s.billable_hours - e.bi) > 0.05
                  OR ABS(s.overtime_hours - e.ot) > 0.05)""")[0][0]
        checks.append(("BU-months where employee totals differ from the Actual BU statistics", emp_mism, 0))
        open_emp = q(conn, "SELECT COUNT(*) FROM fact_employee_month f JOIN dim_period p ON p.month_key = f.month_key "
                           "WHERE p.close_date > :d", d=data_as_of_date())[0][0]
        checks.append(("Employee rows for months not yet closed", open_emp, 0))
        multi = q(conn, "SELECT COUNT(*) FROM (SELECT employee_id FROM fact_employee_month GROUP BY employee_id "
                        "HAVING SUM(CASE WHEN is_leaver = 1 THEN 1 ELSE 0 END) > 1 "
                        "OR SUM(CASE WHEN is_hire = 1 THEN 1 ELSE 0 END) > 1) x")[0][0]
        checks.append(("Employees with more than one hire or leave month", multi, 0))

        # samples
        ctrl = pd.read_parquet(ROOT / "data" / "control_totals.parquet")
        rng = random.Random(int(settings()["seed"]))
        idx = rng.sample(range(len(ctrl)), n_samples)
        sl = SemanticLayer("group_cfo")
        bu_name = dict(zip(d.org["bu_id"].astype(int), d.org["l6_bu"]))
        mism = 0
        detail = []
        for i in idx:
            r = ctrl.iloc[i]
            bu, mkey, vid = int(r.bu_id), int(r.month_key), int(r.version_id)
            raw = dict((int(a), float(b)) for a, b in q(conn,
                "SELECT a.line_no, SUM(f.amount_usd) FROM fact_pnl f JOIN dim_account a ON a.account_id = f.account_id "
                "WHERE f.bu_id = :b AND f.month_key = :m AND f.version_id = :v GROUP BY a.line_no", b=bu, m=mkey, v=vid))
            series = ti.Series(vname[vid], vname[vid], ti.Period("MONTH", mkey), (mkey,))
            w = sl.frame([series], {"l6_bu": [bu_name[bu]]}).iloc[0]
            ok_all = True
            for name, (col, lines) in SUBTOTALS.items():
                sem = float(w[col])
                sql_sum = sum(raw.get(ln, 0.0) for ln in lines)
                ctl = float(r[name])
                ok = abs(sem - sql_sum) <= TOL_SQL and abs(sem - ctl) <= TOL_CTRL
                ok_all &= ok
                if not ok:
                    mism += 1
            detail.append((bu_name[bu], mkey, vname[vid], float(w["L6"]), float(w["L13"]), ok_all))
        sl.sql_log.clear()

    out("\n## Integrity checks\n")
    out("| Check | Found | Expected | Status |\n|---|---:|---:|---|")
    failed = 0
    for name, found, exp in checks:
        status = "OK" if found == exp else "FAIL"
        failed += status != "OK"
        out(f"| {name} | {found} | {exp} | {status} |")

    # cross-backend
    if backend() == "mssql" and duckdb_path().exists():
        con = duckdb.connect(str(duckdb_path()), read_only=True)
        ddb = {int(v): (int(c), float(s)) for v, c, s in con.execute(
            "SELECT version_id, COUNT(*), SUM(amount_usd) FROM fact_pnl GROUP BY version_id").fetchall()}
        con.close()
        same = all(ddb.get(int(v)) == (int(c), round(float(t), 2)) or
                   (ddb.get(int(v)) and ddb[int(v)][0] == int(c) and abs(ddb[int(v)][1] - float(t)) < 0.005)
                   for v, c, _, t in per_version)
        out(f"\nSQL Server vs DuckDB (rows and totals per version): {'identical' if same else 'DIFFERENT'}")
        failed += not same

    out(f"\n## Subtotal reconciliation: {n_samples} random BU x month x version samples\n")
    out("Each sample checks Revenue, Production, Gross profit, Operating profit, EBIT and Net income three ways: semantic layer "
        f"vs raw SQL leaf sums (tolerance USD {TOL_SQL}) and vs generator control totals (tolerance USD {TOL_CTRL}).\n")
    out("| BU | Month | Version | Production (USD) | Operating profit (USD) | Status |\n|---|---|---|---:|---:|---|")
    for bu, mkey, ver, prod, maop, ok in detail[:12]:
        out(f"| {bu} | {mkey} | {ver} | {prod:,.2f} | {maop:,.2f} | {'OK' if ok else 'MISMATCH'} |")
    out(f"| ... {len(detail) - 12} more samples | | | | | |")
    out(f"\n**Mismatches: {mism}** (subtotal checks: {n_samples * len(SUBTOTALS)}), "
        f"integrity check failures: {failed}")
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / f"reconcile_report_{backend()}.md").write_text("\n".join(lines_out) + "\n")
    return 1 if (mism or failed) else 0


if __name__ == "__main__":
    sys.exit(main())
