#!/usr/bin/env python
"""Wait until SQL Server accepts connections and make sure the database exists."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import env  # noqa: E402
from app.db import mssql_url  # noqa: E402


def main(timeout_s: int = 300) -> None:
    db = env("DB_NAME", "iris")
    eng = create_engine(mssql_url(admin=True, database="master"), isolation_level="AUTOCOMMIT")
    start = time.time()
    while True:
        try:
            with eng.connect() as c:
                version = c.execute(text("SELECT @@VERSION")).scalar()
                c.execute(text(f"IF DB_ID(N'{db}') IS NULL CREATE DATABASE [{db}]"))
            print(version.splitlines()[0])
            print(f"database [{db}] ready")
            return
        except Exception as exc:  # noqa: BLE001
            if time.time() - start > timeout_s:
                raise SystemExit(f"SQL Server not reachable after {timeout_s}s: {exc}")
            print("waiting for SQL Server ...")
            time.sleep(5)


if __name__ == "__main__":
    main()
