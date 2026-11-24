"""Persist landing results (batch job with admin rights). Idempotent: a snapshot is replaced as a whole."""
from __future__ import annotations

import time
from datetime import date, datetime

import pandas as pd
from sqlalchemy import delete, insert

from app.config import backend
from app.db import get_engine, metadata

SNAPSHOT_TABLES = ("fact_landing", "fact_landing_leaf", "landing_method", "landing_bu_profile", "landing_residual")


def _records(df: pd.DataFrame) -> list[dict]:
    clean = df.astype(object).where(pd.notna(df), None)
    return clean.to_dict(orient="records")


def write_snapshot(rows: dict[str, pd.DataFrame], snapshot: date, month_key: int, seconds: float,
                   engine=None, notes: str = "") -> dict[str, int]:
    """Replace every landing row of `snapshot` in one transaction."""
    eng = engine or get_engine(admin=True)
    counts = {}
    with eng.begin() as conn:
        for name in (*SNAPSHOT_TABLES, "landing_run"):
            conn.execute(delete(metadata.tables[name]).where(metadata.tables[name].c.snapshot_date == snapshot))
        for name in SNAPSHOT_TABLES:
            df = rows.get(name)
            if df is None or df.empty:
                counts[name] = 0
                continue
            recs = _records(df)
            table = metadata.tables[name]
            step = 2000 if backend() == "mssql" else 20000
            for i in range(0, len(recs), step):
                conn.execute(insert(table), recs[i:i + step])
            counts[name] = len(recs)
        meta = rows.get("_meta") or {}
        conn.execute(insert(metadata.tables["landing_run"]), [{
            "snapshot_date": snapshot, "month_key": month_key, "run_at": datetime.now().replace(microsecond=0),
            "n_bus": int(rows["fact_landing"]["bu_id"].nunique()), "seconds": round(seconds, 2),
            "mtd_used": bool(meta.get("mtd_used", False)), "notes": notes[:400] or None}])
    return counts


def write_backtest_metrics(df: pd.DataFrame, run_date: date, engine=None) -> int:
    eng = engine or get_engine(admin=True)
    table = metadata.tables["landing_backtest_metric"]
    with eng.begin() as conn:
        conn.execute(delete(table).where(table.c.run_date == run_date))
        recs = _records(df.assign(run_date=run_date))
        for i in range(0, len(recs), 2000):
            conn.execute(insert(table), recs[i:i + 2000])
    return len(df)


class Timer:
    def __init__(self):
        self.t0 = time.time()

    @property
    def seconds(self) -> float:
        return time.time() - self.t0
