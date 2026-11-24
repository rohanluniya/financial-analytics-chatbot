"""Shared pytest fixtures. Tests run against the configured backend (DB_BACKEND in .env);
run `DB_BACKEND=duckdb make test` to test the DuckDB backend."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import backend  # noqa: E402
from app.db import get_engine  # noqa: E402


@pytest.fixture(scope="session")
def raw():
    """Run raw SQL with full visibility (SQL Server admin = dbo bypasses RLS; DuckDB read-only)."""
    eng = get_engine(admin=True) if backend() == "mssql" else get_engine("__tests__")

    def _q(sql: str, **params):
        with eng.connect() as c:
            return c.execute(text(sql), params).fetchall()
    return _q


@pytest.fixture(scope="session")
def is_mssql() -> bool:
    return backend() == "mssql"
