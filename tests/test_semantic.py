"""Semantic layer tests: schema, subtotal reconciliation, sign logic, favourability, time
intelligence, entity resolution, row-level security (Python + native SQL Server)."""
from __future__ import annotations

import re
from datetime import date

import pytest
import sqlglot
from sqlglot import exp

from app.config import ROOT, backend, env
from app.db import metadata
from app.semantic import time_intel as ti
from app.semantic.access import check_access
from app.semantic.dims import dims
from app.semantic.entity_resolver import resolve
from app.semantic.query_builder import SemanticLayer

AS_OF = date(2026, 11, 12)
LEAF_SUM = {"L3": [1, 2], "L6": [1, 2, 4, 5], "L11": [1, 2, 4, 5, 7, 8, 9, 10],
            "L13": [1, 2, 4, 5, 7, 8, 9, 10, 12], "L18": [1, 2, 4, 5, 7, 8, 9, 10, 12, 17],
            "L21": [1, 2, 4, 5, 7, 8, 9, 10, 12, 17, 19, 20]}


# --------------------------------------------------------------------------- schema
def test_schema_sql_matches_metadata():
    sql = (ROOT / "sql" / "schema.sql").read_text().split("-- @@POST_LOAD@@")[0]
    # Parse only the CREATE TABLE statements (sqlglot does not support T-SQL `SELECT @v += ...`).
    creates = re.findall(r"CREATE TABLE .*?\n\);", sql, flags=re.S)
    found = {}
    for stmt in sqlglot.parse(";\n".join(creates), read="tsql"):
        if isinstance(stmt, exp.Create) and stmt.kind == "TABLE":
            name = stmt.this.this.name
            found[name] = [c.name for c in stmt.this.expressions if isinstance(c, exp.ColumnDef)]
    for table in metadata.sorted_tables:
        assert table.name in found, f"{table.name} missing in schema.sql"
        assert [c.name for c in table.columns] == found[table.name], table.name


def test_facts_only_on_leaf_accounts(raw):
    n = raw("SELECT COUNT(*) FROM fact_pnl f JOIN dim_account a ON a.account_id = f.account_id WHERE a.is_leaf = :f",
            f=False)[0][0]
    assert n == 0


# --------------------------------------------------------------------------- subtotals
@pytest.mark.parametrize("org,months,version", [
    ({"l3_country": ["United States"]}, (202601, 202610), "Actual"),
    ({"l2_region": ["BPU"]}, (202501, 202512), "Budget"),
    ({"l4_product_line": ["Environmental Lab Testing"]}, (202601, 202612), "FC2"),
    ({"l3_country": ["Mexico"], "l4_product_line": ["Buildings & Infrastructure"]}, (202607, 202609), "Actual"),
])
def test_subtotals_equal_leaf_sums(raw, org, months, version):
    sl = SemanticLayer("group_cfo", AS_OF)
    p = ti.Period("RANGE", months[1], months[0])
    w = sl.frame([ti.Series(version, version, p, tuple(p.months()))], org).iloc[0]
    level, values = next(iter(org.items()))
    extra = " AND ".join(f"o.{lvl} = :v{i}" for i, lvl in enumerate(org))
    params = {f"v{i}": vals[0] for i, (lvl, vals) in enumerate(org.items())}
    rows = dict(raw(f"""SELECT a.line_no, SUM(f.amount_usd) FROM fact_pnl f
                       JOIN dim_account a ON a.account_id = f.account_id JOIN dim_org o ON o.bu_id = f.bu_id
                       JOIN dim_version v ON v.version_id = f.version_id
                       WHERE v.name = :ver AND f.month_key BETWEEN :m0 AND :m1 AND {extra}
                       GROUP BY a.line_no""", ver=version, m0=months[0], m1=months[1], **params))
    for col, lines in LEAF_SUM.items():
        expected = float(sum(rows.get(ln, 0) for ln in lines))
        assert abs(float(w[col]) - expected) < 0.01, (col, float(w[col]), expected)


# --------------------------------------------------------------------------- signs
def test_sign_convention_and_display(raw):
    by_line = dict(raw("""SELECT a.line_no, SUM(f.amount_usd) FROM fact_pnl f JOIN dim_account a
                         ON a.account_id = f.account_id WHERE f.version_id = 1 AND f.month_key BETWEEN 202501 AND 202512
                         GROUP BY a.line_no"""))
    assert by_line[1] > 0 and by_line[4] > 0                    # revenue-type lines positive
    for ln in (5, 7, 8, 9, 12, 20):
        assert by_line[ln] < 0, ln                               # costs negative in storage
    sl = SemanticLayer("group_cfo", AS_OF)
    res = sl.ratio("personnel_to_revenue", {}, ti.Period("FY", 202512), [])
    assert res.df["Personnel costs"].iloc[0] > 0                 # display value = magnitude
    assert 0.3 < res.df["Personnel costs / Revenue"].iloc[0] < 0.7


def test_favourability_rules():
    assert ti.is_favorable(100, "up") is True
    assert ti.is_favorable(-100, "up") is False
    assert ti.is_favorable(100, "down") is False                 # cost went up
    assert ti.is_favorable(-100, "down") is True
    assert ti.is_favorable(5, "neutral") is None
    d, p = ti.variance(110, 100)
    assert d == 10 and abs(p - 0.10) < 1e-12
    d, p = ti.variance(-110, -100)                               # signed cost: -10 profit impact
    assert d == -10 and abs(p + 0.10) < 1e-12


def test_pnl_variances_are_profit_impact():
    sl = SemanticLayer("group_cfo", AS_OF)
    res = sl.pnl({"l3_country": ["Canada"]}, ti.Period("YTD", 202610), ["Actual", "PY", "Budget"])
    row = res.df.set_index("_code").loc["7"]                    # personnel (signed, negative)
    assert row["Actual"] < 0
    assert row["_fav_PY"] == (row["Var vs PY"] > 0)


# --------------------------------------------------------------------------- time intelligence
def test_calendar_and_periods():
    assert ti.last_closed_month(AS_OF) == 202610
    assert ti.last_closed_month(date(2026, 11, 4)) == 202609      # Oct closes on Nov 5
    assert ti.default_period(AS_OF).months() == list(range(202601, 202611))
    assert ti.Period("QTD", 202610).months() == [202610]
    assert ti.Period("R12M", 202610).months()[0] == 202511
    assert ti.Period("QUARTER", 202509).months() == [202507, 202508, 202509]
    assert ti.Period("YTD", 202610).shift_years(-1).months() == list(range(202501, 202511))
    assert ti.Period("FY", 202612).truncate(202610).months() == list(range(202601, 202611))


@pytest.mark.parametrize("text,ptype,start,end", [
    ("Q3 2025", "QUARTER", 202507, 202509), ("March 2025", "MONTH", 202503, 202503),
    ("last month", "MONTH", 202610, 202610), ("FY2025", "FY", 202501, 202512),
    ("since 2023", "RANGE", 202301, 202610), ("YTD", "YTD", 202601, 202610),
    ("rolling 12 months", "R12M", 202511, 202610), ("this year", "YTD", 202601, 202610),
    ("2025-03", "MONTH", 202503, 202503), ("H1 2026", "RANGE", 202601, 202606),
    ("MTD", None, None, None),
])
def test_period_parsing(text, ptype, start, end):
    p = ti.parse_period_text(text, AS_OF).period
    if ptype is None:
        return
    assert p is not None and p.period_type == ptype
    assert p.months()[0] == start and p.months()[-1] == end


def test_latest_forecast_rule():
    assert ti.latest_forecast(2026, AS_OF) == "FC3"
    assert ti.latest_forecast(2026, date(2026, 6, 1)) == "FC1"
    assert ti.latest_forecast(2026, date(2026, 5, 4)) is None   # April closes on May 5
    assert ti.latest_forecast(2025, AS_OF) == "FC3"
    series, notes = ti.resolve_series("Actual", ti.Period("YTD", 202610), ["LatestFC"], AS_OF)
    assert [s.label for s in series] == ["Actual", "FC3"]


# --------------------------------------------------------------------------- entity resolver
@pytest.mark.parametrize("q,expected", [
    ("MAOP for Mexico B&I", {"l3_country": ["Mexico"], "l4_product_line": ["Buildings & Infrastructure"]}),
    ("lifts in the US", {"l3_country": ["United States"], "l4_product_line": ["Elevators & Pressure Vessels"]}),
    ("env lab Canda last month", {"l3_country": ["Canada"], "l4_product_line": ["Environmental Lab Testing"]}),
    ("How is US & Canada doing?", {"l2_region": ["US & Canada"]}),
    ("MAOP in South America", {"l2_region": ["Northern South America", "Southern South America", "BPU"]}),
    ("Chile metals and minerals", {"l3_country": ["Chile"], "l4_product_line": ["Metals & Minerals"]}),
])
def test_org_resolution(q, expected):
    r = resolve(q, dims().org, AS_OF)
    assert r.org_filter == expected, r.org_filter


def test_py_is_prior_year_not_paraguay():
    r = resolve("Subcontracting cost by product line YTD vs PY", dims().org, AS_OF)
    assert "PY" in r.comparisons and "l3_country" not in r.org_filter
    assert r.level_hint == "l4_product_line" and r.metric == "subcontracting"


def test_metric_and_ratio_resolution():
    org = dims().org
    assert resolve("personnel/billing for Canada", org, AS_OF).ratio == "personnel_to_billing"
    assert resolve("staff cost as % of revenue", org, AS_OF).ratio == "personnel_to_revenue"
    assert resolve("direct labor cost over production", org, AS_OF).ratio == "direct_labor_to_production"
    assert resolve("utilisation in Mexico", org, AS_OF).ratio == "utilization_rate"
    assert resolve("MOP YTD", org, AS_OF).metric == "maop"
    assert resolve("net income 2025", org, AS_OF).metric == "net_income"


def test_corrections_drop_the_negated_part():
    org = dims().org
    r = resolve("not YTD, full year 2025", org, AS_OF)
    assert r.period["type"] == "FY" and r.period["end"] == 202512 and r.negated == ["YTD"]
    assert resolve("No, not operating profit, net income", org, AS_OF).metric == "net_income"
    assert resolve("operating profit instead of net income", org, AS_OF).metrics == ["maop"]
    assert resolve("use Q3 2026 rather than YTD", org, AS_OF).period["type"] == "QUARTER"
    r = resolve("Which BUs did not meet budget this year?", org, AS_OF)      # a verb is negated, not a correction
    assert "Budget" in r.versions and r.negated == []


def test_compare_with_last_year_is_a_comparison():
    r = resolve("how does that compare with last year?", dims().org, AS_OF)
    assert r.comparisons == ["PY"] and r.period is None


def test_ambiguous_city_triggers_clarification():
    cities = dims().org.groupby("city")["l5_business"].nunique()
    city = cities[cities > 1].index[0]
    r = resolve(f"How is the {city} business doing?", dims().org, AS_OF)
    assert r.ambiguous and len(r.ambiguous[0]["options"]) > 1


# --------------------------------------------------------------------------- RLS
def test_access_decisions():
    assert check_access("us_country_head", {"l3_country": ["Brazil"]}).status == "denied"
    d = check_access("us_country_head", {"l2_region": ["US & Canada"]})
    assert d.status == "narrowed" and d.org_filter.get("l3_country") == ["United States"]
    assert check_access("env_pl_leader", {"l4_product_line": ["Environmental Lab Testing"]}).status == "ok"
    assert check_access("group_cfo", {"l3_country": ["Brazil"]}).status == "ok"
    assert check_access("unknown_user", {}).status == "denied"


def test_rls_scope_in_semantic_layer(raw):
    """A restricted user querying the whole group only ever sees their own BUs."""
    p = ti.Period("YTD", 202610)
    s = ti.Series("Actual", "Actual", p, tuple(p.months()))
    us_head = SemanticLayer("us_country_head", AS_OF).frame([s], {}).iloc[0]["L6"]
    cfo_us = SemanticLayer("group_cfo", AS_OF).frame([s], {"l3_country": ["United States"]}).iloc[0]["L6"]
    assert abs(us_head - cfo_us) < 0.01


@pytest.mark.skipif(backend() != "mssql", reason="native RLS only on SQL Server")
def test_native_sql_server_rls():
    from sqlalchemy import create_engine, text

    from app.db import mssql_url
    eng = create_engine(mssql_url(admin=False))
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM fact_pnl")).scalar() == 0          # no session context
        c.execute(text("EXEC sp_set_session_context @key=N'user_id', @value=N'us_country_head', @read_only=1"))
        countries = [r[0] for r in c.execute(text(
            "SELECT DISTINCT o.l3_country FROM fact_pnl f JOIN dim_org o ON o.bu_id = f.bu_id")).fetchall()]
        assert countries == ["United States"]
        n_stats = c.execute(text("SELECT COUNT(DISTINCT bu_id) FROM fact_stats")).scalar()
        assert n_stats == int((dims().org["l3_country"] == "United States").sum())
    eng.dispose()


def test_cockpit_has_all_kpis():
    res = SemanticLayer("group_cfo", AS_OF).cockpit({"l3_country": ["Canada"]})
    assert len(res.df) == 11 and res.df["YTD"].notna().all()
    util = res.df.set_index("_code").loc["utilization_rate", "YTD"]
    assert 0.6 < util < 0.95


# --------------------------------------------------------------------------- neutral labels
def test_labels_are_generic():
    sl = SemanticLayer("group_cfo", AS_OF)
    labels = [r["label"] for r in sl.pnl_rows(3)]
    assert {"OPERATING PROFIT", "EBIT", "Direct staff costs", "Indirect staff costs", "Direct staff bonus"} <= set(labels)
    assert not any(re.search(r"\d", lab) for lab in labels), "P&L labels must not show line numbers or account codes"
    chile = set(dims().org.loc[dims().org["l3_country"] == "Chile", "city"])
    assert "Calama" in chile and chile <= {"Calama", "Antofagasta", "Concepcion"}


def test_environmental_lab_only_in_canada_and_us():
    env = dims().org[dims().org["l4_product_line"] == "Environmental Lab Testing"]
    assert set(env["l3_country"]) == {"Canada", "United States"}
    assert (env["l3_country"] == "Canada").sum() > (env["l3_country"] == "United States").sum()


# --------------------------------------------------------------------------- employee records
def test_employee_records_add_up_to_bu_stats(raw):
    emp = raw("""SELECT f.bu_id, f.month_key, COUNT(*), SUM(f.fte), SUM(f.billable_hours), SUM(f.available_hours)
                 FROM fact_employee_month f WHERE f.month_key BETWEEN 202501 AND 202512
                 GROUP BY f.bu_id, f.month_key""")
    stats = raw("""SELECT s.bu_id, s.month_key, s.headcount, s.fte, s.billable_hours, s.available_hours
                   FROM fact_stats s JOIN dim_version v ON v.version_id = s.version_id
                   WHERE v.name = 'Actual' AND s.month_key BETWEEN 202501 AND 202512""")
    st = {(r[0], r[1]): r[2:] for r in stats}
    assert len(emp) == len(st)
    for r in emp:
        s = st[(r[0], r[1])]
        assert abs(float(r[2]) - float(s[0])) < 1e-6 and abs(float(r[3]) - float(s[1])) < 0.01
        assert abs(float(r[4]) - float(s[2])) < 0.5 and abs(float(r[5]) - float(s[3])) < 0.5


def test_workforce_matches_stats_and_counts_leavers(raw):
    sl = SemanticLayer("group_cfo", AS_OF)
    org = {"l3_country": ["Canada"], "l4_product_line": ["Environmental Lab Testing"]}
    res = sl.workforce(org, ti.Period("YTD", 202610), "role", "attrition")
    total = res.df.iloc[0]
    assert total["_kind"] == "subtotal" and res.meta["has_py"]
    p = ti.Period("YTD", 202610)
    w = sl.frame([ti.Series("Actual", "Actual", p, tuple(p.months()))], org, with_stats=True).iloc[0]
    assert abs(total["Avg headcount"] - w["headcount_sum"] / w["n_months"]) < 1e-6
    assert abs(total["Utilization"] - w["billable_hours_sum"] / w["available_hours_sum"]) < 1e-6
    leavers = raw("""SELECT COUNT(*) FROM fact_employee_month f JOIN dim_org o ON o.bu_id = f.bu_id
                     WHERE f.is_leaver = :t AND f.month_key BETWEEN 202601 AND 202610
                     AND o.l3_country = 'Canada' AND o.l4_product_line = 'Environmental Lab Testing'""", t=True)[0][0]
    assert total["Leavers"] == leavers
    assert abs(total["Attrition"] - leavers * 12 / 10 / total["Avg headcount"]) < 1e-9
    assert abs(res.df.iloc[1:]["Leavers"].sum() - leavers) < 1e-9          # roles add up to the total


@pytest.mark.skipif(backend() != "mssql", reason="native RLS only on SQL Server")
def test_native_rls_on_employee_tables():
    from sqlalchemy import create_engine, text

    from app.db import mssql_url
    eng = create_engine(mssql_url(admin=False))
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM dim_employee")).scalar() == 0         # no session context
        c.execute(text("EXEC sp_set_session_context @key=N'user_id', @value=N'us_country_head', @read_only=1"))
        countries = [r[0] for r in c.execute(text(
            "SELECT DISTINCT o.l3_country FROM fact_employee_month f JOIN dim_org o ON o.bu_id = f.bu_id")).fetchall()]
        assert countries == ["United States"]
    eng.dispose()
