"""Guardrail tests: SQL guard (read-only, whitelist, limits, RLS injection) and numeric guardrail."""
from __future__ import annotations

import pytest

from app.agent.guardrails import (SqlGuardError, _month_mentions, canonical_terms, check_answer, check_numbers,
                                   drop_ungrounded, execute_readonly, extract_numbers, validate_sql)
from app.agent.tools import ToolOutput
from app.config import backend
from app.db import get_engine


@pytest.mark.parametrize("sql", [
    "INSERT INTO v_org VALUES (1)",
    "UPDATE fact_pnl SET amount_usd = 0",
    "DELETE FROM v_pnl",
    "DROP TABLE fact_pnl",
    "EXEC sp_who",
    "SELECT 1; DROP TABLE dim_org",
    "SELECT * INTO hack FROM v_pnl",
    "SELECT * FROM fact_pnl",                       # base tables are not whitelisted
    "SELECT * FROM dim_org",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM otherdb.dbo.v_pnl",
    "TRUNCATE TABLE fact_pnl",
    "WAITFOR DELAY '00:00:10'",
])
@pytest.mark.parametrize("dialect", ["tsql", "duckdb"])
def test_sql_guard_rejects(sql, dialect):
    with pytest.raises(SqlGuardError):
        validate_sql(sql, dialect=dialect)


@pytest.mark.parametrize("dialect", ["tsql", "duckdb"])
def test_sql_guard_accepts_and_limits(dialect):
    out = validate_sql("SELECT l3_country, SUM(amount_usd) AS v FROM v_pnl WHERE line_no = 13 GROUP BY l3_country",
                       dialect=dialect)
    assert ("TOP 1000" in out.upper()) if dialect == "tsql" else ("LIMIT 1000" in out.upper())
    capped = validate_sql("SELECT * FROM v_pnl_leaf LIMIT 50000", dialect="duckdb")
    assert "LIMIT 1000" in capped.upper()
    cte = validate_sql("WITH x AS (SELECT * FROM v_org) SELECT * FROM x", dialect=dialect)
    assert "v_org" in cte


def test_sql_guard_injects_rls_in_duckdb_mode():
    out = validate_sql("SELECT SUM(amount_usd) FROM v_pnl p WHERE line_no = 6", allowed_bu_ids={1, 2, 3},
                       dialect="duckdb")
    assert "bu_id IN (1, 2, 3)" in out


def test_readonly_execution_respects_limit_and_rls():
    eng = get_engine("us_country_head")
    allowed = None
    if backend() == "duckdb":
        from app.semantic.access import allowed_bus
        allowed = allowed_bus("us_country_head")
    safe = validate_sql("SELECT DISTINCT l3_country FROM v_pnl", allowed_bu_ids=allowed)
    df = execute_readonly(eng, safe)
    assert df.iloc[:, 0].tolist() == ["United States"]
    big = execute_readonly(eng, validate_sql("SELECT * FROM v_pnl_leaf", allowed_bu_ids=allowed))
    assert len(big) == 1000


def test_employee_views_are_readable_and_scoped():
    with pytest.raises(SqlGuardError):
        validate_sql("SELECT * FROM dim_employee", dialect="tsql")         # base table: not whitelisted
    eng = get_engine("us_country_head")
    allowed = None
    if backend() == "duckdb":
        from app.semantic.access import allowed_bus
        allowed = allowed_bus("us_country_head")
    df = execute_readonly(eng, validate_sql("SELECT DISTINCT l3_country FROM v_employee_month WHERE month_key = 202610",
                                            allowed_bu_ids=allowed))
    assert df.iloc[:, 0].tolist() == ["United States"]


def _out(facts, data=None):
    return ToolOutput(tool="t", kind="pnl", facts=facts, data=data or [])


def test_numeric_guard_accepts_supported_numbers():
    outs = [_out(["Operating profit: USD 23.1M; PY USD 21.6M, difference +USD 1.5M (+6.7%, favourable)",
                  "Operating margin (on revenue): 11.2%; PY 11.0% (+0.2 pp, favourable)"])]
    answer = ("Operating profit for YTD Oct 2026 (Actual) reached USD 23.1M, up USD 1.5M (+6.7%) on PY (USD 21.6M). "
              "The margin improved to 11.2%, +0.2 pp vs last year, in 2026 for the 3 regions.")
    g = check_numbers(answer, outs, "How is operating profit YTD vs last year?")
    assert g.ok, g.unsupported


def test_numeric_guard_flags_invented_numbers():
    outs = [_out(["Operating profit: USD 23.1M; PY USD 21.6M"])]
    g = check_numbers("Operating profit was USD 25.4M, 17.5% above plan.", outs)
    assert not g.ok and "USD 25.4M".split()[1] in " ".join(g.unsupported) or "25.4M" in " ".join(g.unsupported)
    assert any("17.5" in u for u in g.unsupported)


def test_numeric_guard_uses_table_values():
    outs = [_out([], data=[{"Line": "Operating profit", "Actual": 1457687.0}])]
    assert check_numbers("Operating profit came in at USD 1,457,687 and USD 1.5M rounded.", outs).ok


def test_number_extraction_units():
    toks = {t.raw: t.value for t in extract_numbers("USD 23.1M, 845k, 11.6%, +4.8 pp, FC2, 7A1 and 2026")}
    assert abs(toks["23.1M"] - 23.1e6) < 1
    assert abs(toks["845k"] - 845e3) < 1
    assert abs(toks["11.6%"] - 0.116) < 1e-9
    assert abs(toks["+4.8 pp"] - 0.048) < 1e-9
    assert not any(k.startswith("2") and "FC" in k for k in toks)


def test_redaction_drops_only_sentences_with_unsupported_numbers():
    from app.agent.graph import redact_sentences
    text = "Operating profit is USD 54.4M, USD 3.5M above PY. The gap vs budget is USD 9.9M. Costs rose faster than revenue."
    assert redact_sentences(text, ["9.9M"]) == "Operating profit is USD 54.4M, USD 3.5M above PY. Costs rose faster than revenue."
    assert redact_sentences(text, ["<empty>"]) == ""
    # The headline sentence itself is unsupported: use the template instead of a dangling remainder.
    assert redact_sentences(text, ["54.4M"]) == ""


# ------------------------------------------------------------------------------------------ narrative checks
WF_FACTS = ["Scope Canada · Environmental Lab Testing, YTD Oct 2026: workforce from fictional employee records (Actual).",
            "Attrition rate (annualised): 33.6%; 23.6 pp above PY (10.1%), unfavourable.",
            "Leavers: 99 (37 voluntary, 62 restructuring); PY 32 (29 voluntary, 3 restructuring).",
            "Month with the most leavers: Apr 2026 (63, of which 60 restructuring)."]


def _scoped(facts, org="Canada · Environmental Lab Testing", period="YTD Oct 2026", months="Jan 2026 - Oct 2026",
            kind="workforce"):
    return ToolOutput(tool="t", kind=kind, facts=facts,
                      filters_used={"org": org, "period": period, "months": months})


def test_month_mentions_tell_single_months_from_period_bounds():
    assert _month_mentions("62 in Apr 2026") == [("Apr 2026", True)]
    assert _month_mentions("in April 2026") == [("Apr 2026", True)]
    assert _month_mentions("YTD Oct 2026") == [("Oct 2026", False)]
    assert _month_mentions("Jan–Jun 2026") == [("Jun 2026", False)]
    assert [s for _, s in _month_mentions("from 390 in Apr 2026 to 327 in May 2026")] == [False, True]


def test_month_binding_flags_a_number_tied_to_the_wrong_month():
    outs = [_scoped(WF_FACTS)]
    bad = "Attrition is 33.6%, driven by restructuring leavers (62 in Apr 2026)."
    assert check_numbers(bad, outs).ok                  # 62 exists in the data, so the number check alone passes
    g = check_answer(bad, outs)
    assert not g.ok and "62" in g.unsupported and any("Apr 2026" in p for p in g.problems)
    good = "Attrition is 33.6%, 23.6 pp above PY (10.1%). Leavers peaked in April 2026 at 63, of which 60 were restructuring."
    assert check_answer(good, outs).ok
    # right month, wrong leaver type: April had 63 leavers, 60 of them restructuring
    g = check_answer("Attrition is 33.6%, with 63 restructuring leavers in Apr 2026.", outs)
    assert not g.ok and any("Apr 2026 restructuring" in p for p in g.problems)


def test_small_counts_stated_as_a_difference_are_checked():
    outs = [_scoped(WF_FACTS + ["Restructuring leavers: 62; 59 more than PY (3)."])]
    assert not check_numbers("Canada had 62 restructuring leavers, 30 above PY (32).", outs).ok
    assert check_numbers("Canada had 62 restructuring leavers, 59 more than PY (3), across 5 BUs.", outs).ok


def test_counts_must_keep_their_leaver_type():
    outs = [_scoped(WF_FACTS)]
    g = check_answer("Canada Environmental Lab Testing had 99 restructuring leavers this year.", outs)
    assert not g.ok and any("restructuring figure" in p for p in g.problems)
    assert check_answer("Canada Environmental Lab Testing had 62 restructuring and 37 voluntary leavers this year.", outs).ok
    # a year total and a monthly figure in one sentence: only the number next to the month is tied to it
    assert check_answer("Leavers totalled 99 this year, with a peak of 63 in April 2026.", outs).ok
    # the change in all leavers (67) given to one leaver type
    typed = [_scoped(["Leavers: 99; 67 (209.4%) more than PY (32); of these 37 voluntary and 62 restructuring "
                      "(PY 29 voluntary and 3 restructuring).", "Restructuring leavers: 62; 59 more than PY (3).",
                      "Voluntary leavers: 37; 8 (27.6%) more than PY (29)."])]
    g = check_answer("Leavers rose, with restructuring accounting for 67 (209.4%) more leavers than PY (32).", typed)
    assert not g.ok and any("change in restructuring leavers" in p for p in g.problems)
    assert check_answer("Canada Environmental Lab Testing had 62 restructuring leavers, 59 more than PY (3).", typed).ok


def test_month_binding_ignores_the_question_period():
    outs = [_scoped(["Scope United States · Elevators & Pressure Vessels, Mar 2025: Actual vs PY.",
                     "Direct staff costs: Actual USD 1.6M, USD 342k (27.0%) higher than PY (USD 1.3M), unfavourable."],
                    org="United States · Elevators & Pressure Vessels", period="Mar 2025",
                    months="Mar 2025 - Mar 2025", kind="drivers")]
    text = "Direct staff costs for US Elevators & Pressure Vessels in March 2025 were USD 1.6M, USD 342k (27.0%) higher than PY."
    assert check_answer(text, outs, "Break down direct staff costs for US Elevators & Pressure Vessels in March 2025").ok


def test_scope_named_too_broadly_is_flagged():
    outs = [_scoped(["Attrition rate (annualised): 15.5%; 3.5 pp above PY (12.0%), unfavourable."],
                    org="United States · Environmental Lab Testing")]
    g = check_answer("The attrition rate in the United States is 15.5%, 3.5 pp above PY (12.0%).", outs)
    assert not g.ok and any("name the scope" in p for p in g.problems)
    for text in ("The attrition rate for United States Environmental Lab Testing is 15.5%, 3.5 pp above PY (12.0%).",
                 "The attrition rate in the US Env Lab unit is 15.5%, 3.5 pp above PY (12.0%).",
                 "The attrition rate is 15.5%, 3.5 pp above PY (12.0%)."):
        assert check_answer(text, outs).ok, text


def test_causes_not_in_the_data_are_dropped():
    outs = [_out(["Operating profit: Actual USD 59.2M; USD 3.2M (5.8%) above PY (USD 55.9M), favourable.",
                  "Operating profit vs PY: increase of USD 3.2M driven by Production (USD 14.8M higher, favourable)."])]
    text = ("Operating profit is USD 59.2M, USD 3.2M (5.8%) above PY. Production was USD 14.8M higher. "
            "This reflects higher sales volumes and improved cost management.")
    assert check_answer(text, outs).ok
    kept, dropped = drop_ungrounded(text, outs)
    assert kept == "Operating profit is USD 59.2M, USD 3.2M (5.8%) above PY. Production was USD 14.8M higher."
    assert len(dropped) == 1
    g = check_answer("Strong demand lifted operating profit to USD 59.2M.", outs)
    assert not g.ok and any("reasons that are not in FACTS" in p for p in g.problems)


def test_customer_terms_are_written_with_generic_names():
    assert canonical_terms("The MAOP margin for Paraguay is 11.3%. MAOP rose; management OP fell.") == \
        "The operating margin for Paraguay is 11.3%. Operating profit rose; EBIT fell."


def test_causes_must_name_something_in_the_data():
    rank = [ToolOutput(tool="t", kind="ranking", facts=["1. Argentina 9.5% (PY 9.5%, +0.0 pp)"],
                       data=[{"Rank": 1, "Country": "Argentina", "Actual": 0.095}])]
    text = "Argentina has the lowest operating margin this year at 9.5%. The decline is driven by higher costs and lower revenue growth."
    kept, dropped = drop_ungrounded(text, rank)
    assert kept == "Argentina has the lowest operating margin this year at 9.5%." and len(dropped) == 1
    pnl = [ToolOutput(tool="t", kind="pnl", facts=["Operating profit: Actual USD 59.2M."],
                      data=[{"Line": "Production"}, {"Line": "Personnel costs"}])]
    grounded = "Operating profit is USD 59.2M. The increase is driven by higher Production, partly offset by Personnel costs."
    assert drop_ungrounded(grounded, pnl) == (grounded, [])
    g = check_answer("Operating profit is USD 59.2M, due to strong client momentum.", pnl)
    assert not g.ok and any("reasons that are not in FACTS" in p for p in g.problems)
