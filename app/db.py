"""Database access for both backends (SQL Server via pyodbc / DuckDB) with SQLAlchemy 2 Core.

* `metadata` mirrors sql/schema.sql (a test checks they stay consistent).
* `get_engine(user_id)` returns a per-user engine. On SQL Server every new connection runs
  `sp_set_session_context @key=N'user_id'` (read-only) so the native SECURITY POLICY in
  sql/rls.sql filters fact rows. On DuckDB the identical filter is applied in Python
  (see app.semantic.query_builder).
"""
from __future__ import annotations

import threading
from functools import lru_cache

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    Table,
    Unicode,
    create_engine,
    event,
)
from sqlalchemy.engine import URL, Engine

from app.config import ROOT, backend, env

metadata = MetaData()

dim_org = Table(
    "dim_org", metadata,
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("bu_name", Unicode(50), nullable=False),
    Column("l6_bu", Unicode(50), nullable=False),
    Column("l5_business", Unicode(100), nullable=False),
    Column("l4_product_line", Unicode(100), nullable=False),
    Column("l3_country", Unicode(50), nullable=False),
    Column("l2_region", Unicode(50), nullable=False),
    Column("l1_group", Unicode(50), nullable=False),
    Column("business_type", Unicode(30), nullable=False),
    Column("city", Unicode(50), nullable=False),
    Column("valid_from", Date, nullable=False),
    Column("valid_to", Date, nullable=False),
)

dim_account = Table(
    "dim_account", metadata,
    Column("account_id", Integer, primary_key=True, autoincrement=False),
    Column("line_no", Integer, nullable=False),
    Column("l1_name", Unicode(100), nullable=False),
    Column("l2_code", Unicode(10), nullable=False),
    Column("l2_name", Unicode(100), nullable=False),
    Column("l3_code", Unicode(10), nullable=False),
    Column("l3_name", Unicode(100), nullable=False),
    Column("is_leaf", Boolean, nullable=False),
    Column("is_subtotal", Boolean, nullable=False),
    Column("natural_sign", SmallInteger, nullable=False),
    Column("display_order", Integer, nullable=False),
    Column("favorable_direction", Unicode(4), nullable=False),
)

dim_version = Table(
    "dim_version", metadata,
    Column("version_id", Integer, primary_key=True, autoincrement=False),
    Column("name", Unicode(20), nullable=False),
    Column("actual_months", Integer, nullable=False),
    Column("is_forecast", Boolean, nullable=False),
)

dim_period = Table(
    "dim_period", metadata,
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("year", Integer, nullable=False),
    Column("quarter", Integer, nullable=False),
    Column("month", Integer, nullable=False),
    Column("month_name", Unicode(10), nullable=False),
    Column("close_date", Date, nullable=False),
    Column("is_closed", Boolean, nullable=False),
)

fact_pnl = Table(
    "fact_pnl", metadata,
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("account_id", Integer, primary_key=True, autoincrement=False),
    Column("version_id", Integer, primary_key=True, autoincrement=False),
    Column("amount_usd", Numeric(18, 2), nullable=False),
)

fact_stats = Table(
    "fact_stats", metadata,
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("version_id", Integer, primary_key=True, autoincrement=False),
    Column("fte", Numeric(10, 2), nullable=False),
    Column("headcount", Numeric(10, 2), nullable=False),
    Column("direct_fte", Numeric(10, 2), nullable=False),
    Column("billable_hours", Numeric(12, 1), nullable=False),
    Column("available_hours", Numeric(12, 1), nullable=False),
    Column("overtime_hours", Numeric(12, 1), nullable=False),
)

app_user = Table(
    "app_user", metadata,
    Column("user_id", Unicode(50), primary_key=True),
    Column("display_name", Unicode(100), nullable=False),
    Column("role", Unicode(50), nullable=False),
)

user_org_access = Table(
    "user_org_access", metadata,
    Column("user_id", Unicode(50), primary_key=True),
    Column("org_level", Unicode(30), primary_key=True),
    Column("org_value", Unicode(100), primary_key=True),
)

# Fictional employees (codes only, no names) and their monthly hours (Actual months)
dim_employee = Table(
    "dim_employee", metadata,
    Column("employee_id", Integer, primary_key=True, autoincrement=False),
    Column("employee_code", Unicode(12), nullable=False),
    Column("bu_id", Integer, nullable=False),
    Column("role", Unicode(40), nullable=False),
    Column("grade", Unicode(4), nullable=False),
    Column("staff_type", Unicode(10), nullable=False),
    Column("fte_pct", Numeric(4, 2), nullable=False),
    Column("hire_date", Date, nullable=False),
    Column("leave_date", Date, nullable=True),
    Column("leave_reason", Unicode(20), nullable=True),
)

fact_employee_month = Table(
    "fact_employee_month", metadata,
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("employee_id", Integer, primary_key=True, autoincrement=False),
    Column("bu_id", Integer, nullable=False),
    Column("fte", Numeric(4, 2), nullable=False),
    Column("available_hours", Numeric(8, 1), nullable=False),
    Column("billable_hours", Numeric(8, 1), nullable=False),
    Column("overtime_hours", Numeric(8, 1), nullable=False),
    Column("is_hire", Boolean, nullable=False),
    Column("is_leaver", Boolean, nullable=False),
)

# Working-day calendar (public holidays per country)
dim_calendar = Table(
    "dim_calendar", metadata,
    Column("date", Date, primary_key=True),
    Column("country", Unicode(50), primary_key=True),
    Column("is_working_day", Boolean, nullable=False),
)

working_days = Table(
    "working_days", metadata,
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("country", Unicode(50), primary_key=True),
    Column("working_days", Integer, nullable=False),
)

# Current-month landing (written by `make landing`, read under RLS)
fact_landing = Table(
    "fact_landing", metadata,
    Column("snapshot_date", Date, primary_key=True),
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("measure", Unicode(40), primary_key=True),
    Column("p10", Numeric(18, 6), nullable=True),
    Column("p50", Numeric(18, 6), nullable=True),
    Column("p90", Numeric(18, 6), nullable=True),
    Column("method_weights_json", Unicode(400), nullable=True),
    Column("pattern_class", Unicode(20), nullable=False),
)

fact_landing_leaf = Table(
    "fact_landing_leaf", metadata,
    Column("snapshot_date", Date, primary_key=True),
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("account_id", Integer, primary_key=True, autoincrement=False),
    Column("amount_usd", Numeric(18, 2), nullable=False),
)

landing_method = Table(
    "landing_method", metadata,
    Column("snapshot_date", Date, primary_key=True),
    Column("month_key", Integer, primary_key=True, autoincrement=False),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("method", Unicode(30), primary_key=True),
    Column("prediction", Numeric(18, 2), nullable=True),
    Column("weight", Numeric(9, 6), nullable=True),
    Column("backtest_wape", Numeric(9, 6), nullable=True),
    Column("detail_json", Unicode(400), nullable=True),
)

landing_bu_profile = Table(
    "landing_bu_profile", metadata,
    Column("snapshot_date", Date, primary_key=True),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("pattern_class", Unicode(20), nullable=False),
    Column("n_months", Integer, nullable=False),
    Column("quarter_end_share", Numeric(9, 6), nullable=True),
    Column("december_share", Numeric(9, 6), nullable=True),
    Column("cv", Numeric(9, 6), nullable=True),
    Column("seasonal_amplitude", Numeric(9, 6), nullable=True),
    Column("shrink_weight", Numeric(9, 6), nullable=True),
    Column("seasonal_index_json", Unicode(300), nullable=True),
)

landing_residual = Table(
    "landing_residual", metadata,
    Column("snapshot_date", Date, primary_key=True),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("origin_month_key", Integer, primary_key=True, autoincrement=False),
    Column("log_error", Numeric(12, 8), nullable=False),
)

landing_run = Table(
    "landing_run", metadata,
    Column("snapshot_date", Date, primary_key=True),
    Column("month_key", Integer, nullable=False),
    Column("run_at", DateTime, nullable=False),
    Column("n_bus", Integer, nullable=False),
    Column("seconds", Numeric(9, 2), nullable=False),
    Column("mtd_used", Boolean, nullable=False),
    Column("notes", Unicode(400), nullable=True),
)

landing_backtest_metric = Table(
    "landing_backtest_metric", metadata,
    Column("run_date", Date, primary_key=True),
    Column("scope_type", Unicode(20), primary_key=True),
    Column("scope_value", Unicode(100), primary_key=True),
    Column("measure", Unicode(40), primary_key=True),
    Column("method", Unicode(30), primary_key=True),
    Column("metric", Unicode(20), primary_key=True),
    Column("value", Numeric(12, 6), nullable=True),
    Column("n", Integer, nullable=False),
)

landing_mtd_snapshot = Table(
    "landing_mtd_snapshot", metadata,
    Column("snapshot_date", Date, primary_key=True),
    Column("bu_id", Integer, primary_key=True, autoincrement=False),
    Column("mtd_billing", Numeric(18, 2), nullable=False),
)

LANDING_TABLES = ["fact_landing", "fact_landing_leaf", "landing_method", "landing_bu_profile", "landing_residual",
                  "landing_run", "landing_backtest_metric", "landing_mtd_snapshot"]

TABLE_LOAD_ORDER = [
    "dim_org", "dim_account", "dim_version", "dim_period",
    "app_user", "user_org_access", "fact_pnl", "fact_stats",
    "dim_employee", "fact_employee_month", "dim_calendar", "working_days",
]

QUERY_TIMEOUT_SECONDS = 30


def mssql_url(admin: bool = False, database: str | None = None) -> URL:
    user = env("MSSQL_SA_USER", "sa") if admin else env("MSSQL_APP_USER", "iris_reader")
    password = env("MSSQL_SA_PASSWORD") if admin else env("MSSQL_APP_PASSWORD")
    query = {
        "driver": env("ODBC_DRIVER", "ODBC Driver 18 for SQL Server"),
        "Encrypt": "yes",
        "TrustServerCertificate": env("MSSQL_TRUST_SERVER_CERT", "yes"),
    }
    return URL.create(
        "mssql+pyodbc",
        username=user,
        password=password,
        host=env("DB_HOST", "localhost"),
        port=int(env("DB_PORT", "1433")),
        database=database if database is not None else env("DB_NAME", "iris"),
        query=query,
    )


def duckdb_path():
    return ROOT / env("DUCKDB_PATH", "data/iris.duckdb")


@lru_cache(maxsize=32)
def get_engine(user_id: str | None = None, admin: bool = False) -> Engine:
    """Engine per (user, admin). App code always passes the persona's user_id."""
    if backend() == "duckdb":
        return create_engine(
            f"duckdb:///{duckdb_path()}",
            connect_args={"read_only": not admin},
        )

    engine = create_engine(
        mssql_url(admin=admin),
        pool_pre_ping=True,
        pool_size=4,
        max_overflow=4,
        fast_executemany=True,
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):  # pragma: no cover - needs SQL Server
        dbapi_conn.timeout = QUERY_TIMEOUT_SECONDS
        if user_id and not admin:
            cur = dbapi_conn.cursor()
            cur.execute(
                "EXEC sp_set_session_context @key=N'user_id', @value=?, @read_only=1;",
                user_id,
            )
            cur.close()

    return engine


def run_with_timeout(conn, fn, seconds: int):
    """Run fn() and interrupt DuckDB if it exceeds `seconds` (SQL Server uses pyodbc timeout)."""
    if backend() != "duckdb":
        raw = conn.connection.dbapi_connection
        previous = getattr(raw, "timeout", 0)
        raw.timeout = seconds
        try:
            return fn()
        finally:
            raw.timeout = previous
    raw = conn.connection.dbapi_connection
    timer = threading.Timer(seconds, lambda: raw.interrupt())
    timer.start()
    try:
        return fn()
    finally:
        timer.cancel()
