#!/usr/bin/env python
"""Load the generated Parquet files into SQL Server 2022 (ODBC Driver 18 + pyodbc fast_executemany).

Steps: create database -> sql/schema.sql -> bulk insert -> post-load indexes -> sql/views.sql
-> sql/rls.sql -> least-privilege app login (password from .env) -> row counts.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pandas as pd
import pyodbc
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import env  # noqa: E402
from app.db import TABLE_LOAD_ORDER, metadata, mssql_url  # noqa: E402

DATA = ROOT / "data"
CHUNK = 50_000


def batches(sql_text: str) -> list[str]:
    parts = re.split(r"^\s*GO\s*$", sql_text, flags=re.MULTILINE | re.IGNORECASE)
    return [p.strip() for p in parts if p.strip() and not all(
        ln.strip().startswith("--") or not ln.strip() for ln in p.splitlines())]


def run_script(raw_conn: pyodbc.Connection, sql_text: str, label: str) -> None:
    cur = raw_conn.cursor()
    for b in batches(sql_text):
        cur.execute(b)
        while cur.nextset():
            pass
    raw_conn.commit()
    print(f"  executed {label}")


def wait_for_server(timeout_s: int = 180) -> None:
    eng = create_engine(mssql_url(admin=True, database="master"))
    start = time.time()
    while True:
        try:
            with eng.connect() as c:
                c.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            if time.time() - start > timeout_s:
                raise SystemExit(f"SQL Server not reachable: {exc}")
            time.sleep(5)


def ensure_database() -> None:
    db = env("DB_NAME", "iris")
    eng = create_engine(mssql_url(admin=True, database="master"), isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(text(f"IF DB_ID(N'{db}') IS NULL CREATE DATABASE [{db}]"))
    print(f"  database [{db}] ready")


def bulk_insert(raw_conn: pyodbc.Connection, table: str, df: pd.DataFrame) -> None:
    cols = [c.name for c in metadata.tables[table].columns]
    df = df[cols]
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO dbo.{table} ({', '.join(cols)}) VALUES ({placeholders})"
    cur = raw_conn.cursor()
    cur.fast_executemany = True
    columns = [df[c].tolist() for c in cols]
    rows = list(zip(*columns))
    for i in range(0, len(rows), CHUNK):
        cur.executemany(sql, rows[i:i + CHUNK])
    raw_conn.commit()


def ensure_app_login(raw_conn: pyodbc.Connection) -> None:
    user = env("MSSQL_APP_USER", "iris_reader")
    pwd = env("MSSQL_APP_PASSWORD")
    if not pwd:
        raise SystemExit("MSSQL_APP_PASSWORD is not set")
    if not re.fullmatch(r"[A-Za-z0-9_]+", user):
        raise SystemExit("MSSQL_APP_USER must be alphanumeric")
    pwd_sql = pwd.replace("'", "''")
    cur = raw_conn.cursor()
    cur.execute(
        f"IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'{user}') "
        f"EXEC(N'CREATE LOGIN [{user}] WITH PASSWORD = N''{pwd_sql.replace(chr(39), chr(39) * 2)}'', CHECK_POLICY = OFF') "
        f"ELSE EXEC(N'ALTER LOGIN [{user}] WITH PASSWORD = N''{pwd_sql.replace(chr(39), chr(39) * 2)}''')"
    )
    cur.execute(
        f"IF DATABASE_PRINCIPAL_ID(N'{user}') IS NULL CREATE USER [{user}] FOR LOGIN [{user}];"
    )
    cur.execute(f"ALTER ROLE iris_app_role ADD MEMBER [{user}];")
    raw_conn.commit()
    print(f"  app login [{user}] ready (SELECT-only, subject to RLS)")


def main() -> None:
    t0 = time.time()
    print("Waiting for SQL Server ...")
    wait_for_server()
    ensure_database()
    engine = create_engine(mssql_url(admin=True))
    schema_sql = (ROOT / "sql" / "schema.sql").read_text()
    pre, post = schema_sql.split("-- @@POST_LOAD@@")
    raw = engine.raw_connection()
    try:
        run_script(raw.driver_connection, pre, "schema.sql (tables)")
        for table in TABLE_LOAD_ORDER:
            df = pd.read_parquet(DATA / f"{table}.parquet")
            t1 = time.time()
            bulk_insert(raw.driver_connection, table, df)
            print(f"  loaded {table:<16} {len(df):>9,} rows in {time.time() - t1:5.1f}s")
        run_script(raw.driver_connection, post, "schema.sql (post-load FKs + columnstore)")
        run_script(raw.driver_connection, (ROOT / "sql" / "views.sql").read_text(), "views.sql")
        run_script(raw.driver_connection, (ROOT / "sql" / "rls.sql").read_text(), "rls.sql")
        run_script(raw.driver_connection, (ROOT / "sql" / "app_tables.sql").read_text(),
                   "app_tables.sql (conversation history, kept across reloads)")
        ensure_app_login(raw.driver_connection)
        cur = raw.driver_connection.cursor()
        print("Row counts (as dbo, RLS bypassed for admin):")
        for table in TABLE_LOAD_ORDER:
            n = cur.execute(f"SELECT COUNT_BIG(*) FROM dbo.{table}").fetchone()[0]
            print(f"  {table:<16} {n:>9,}")
    finally:
        raw.close()
    print(f"Load complete in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
