#!/usr/bin/env python
"""Build the DuckDB file (same schema, same rows, same views) from the generated Parquet files.

DuckDB is the lightweight backend (DB_BACKEND=duckdb) used on a laptop
without SQL Server. Row-level security is enforced in Python in this mode.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import duckdb
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import TABLE_LOAD_ORDER, duckdb_path, metadata  # noqa: E402

DATA = ROOT / "data"


def tsql_views_to_duckdb(sql_text: str) -> list[str]:
    """Translate sql/views.sql (T-SQL) to DuckDB statements."""
    stmts = []
    for part in re.split(r"^\s*GO\s*$", sql_text, flags=re.MULTILINE | re.IGNORECASE):
        body = "\n".join(ln for ln in part.splitlines() if not ln.strip().startswith("--")).strip()
        if not body:
            continue
        body = body.replace("dbo.", "")
        body = re.sub(r"CREATE\s+OR\s+ALTER\s+VIEW", "CREATE OR REPLACE VIEW", body, flags=re.I)
        stmts.append(body)
    return stmts


def main() -> None:
    t0 = time.time()
    path = duckdb_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", ".wal"):
        p = Path(str(path) + suffix)
        if p.exists():
            p.unlink()
    engine = create_engine(f"duckdb:///{path}")
    metadata.create_all(engine)
    engine.dispose()

    con = duckdb.connect(str(path))
    for table in TABLE_LOAD_ORDER:
        cols = [c.name for c in metadata.tables[table].columns]
        col_list = ", ".join(cols)
        con.execute(
            f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM read_parquet(?)",
            [str(DATA / f"{table}.parquet")],
        )
    for stmt in tsql_views_to_duckdb((ROOT / "sql" / "views.sql").read_text()):
        con.execute(stmt)
    print(f"DuckDB file: {path}")
    for table in TABLE_LOAD_ORDER:
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<16} {n:>9,}")
    con.execute("CHECKPOINT")
    con.close()
    print(f"Export complete in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
