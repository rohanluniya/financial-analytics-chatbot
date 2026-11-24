"""Current-month landing (app/landing): working-day calendar, pattern classification, each method, bias
correction, ensemble weights, intervals, bottom-up reconciliation, the WIP rule, open-month-only answers,
YTD including the landing (fixture), RLS, the MTD flag and the hidden-truth boundary.

Database tests read the landing written by `make landing` for the data as-of date (config/settings.yaml).
"""
from __future__ import annotations

import ast
import re
from datetime import date
from types import SimpleNamespace

import holidays
import numpy as np
import pandas as pd
import pytest

from app.agent.graph import ask
from app.config import ROOT, data_as_of_date
from app.landing import engine as E

AS_OF = data_as_of_date()
OPEN = E.open_month(AS_OF)
COUNTRY_CODE = {"United States": "US", "Brazil": "BR", "Mexico": "MX", "Canada": "CA"}


@pytest.fixture(scope="module")
def snap(raw):
    rows = raw("SELECT MAX(snapshot_date) FROM landing_run WHERE month_key = :m", m=OPEN)
    if not rows or rows[0][0] is None:
        pytest.skip("no landing yet: run `make landing`")
    return rows[0][0]


def _evidence(ans) -> list[float]:
    out: list[float] = []

    def walk(o):
        if isinstance(o, bool) or o is None:
            return
        if isinstance(o, (int, float)):
            if o == o:
                out.append(float(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
    walk(ans.table)
    return out


def _has(values: list[float], target: float, rel: float = 1e-6) -> bool:
    return any(abs(v - target) <= max(rel * abs(target), 1e-9) for v in values)


# ------------------------------------------------------------------------------------------ calendar
@pytest.mark.parametrize("country,month", [("United States", 202611), ("Brazil", 202602), ("Mexico", 202609)])
def test_working_days_are_weekdays_minus_public_holidays(raw, country, month):
    y, m = divmod(month, 100)
    hol = holidays.country_holidays(COUNTRY_CODE[country], years=y)
    days = pd.date_range(date(y, m, 1), periods=40, freq="D")
    expected = sum(1 for d in days if d.month == m and d.weekday() < 5 and d.date() not in hol)
    got = raw("SELECT working_days FROM working_days WHERE month_key = :m AND country = :c", m=month, c=country)
    assert got and int(got[0][0]) == expected


def test_open_month_follows_the_close_calendar():
    assert E.open_month(date(2026, 11, 16)) == 202611        # October closed on 5 November
    assert E.open_month(date(2026, 11, 4)) == 202610         # before the close, October is still open
    assert E.open_month(date(2026, 9, 15)) == 202609


# ------------------------------------------------------------------------------------------ classification
def test_classification_rules():
    qe = np.array([0.30, 0.45, 0.47, 0.30, 0.30])
    dec = np.array([0.09, 0.12, 0.27, 0.09, 0.09])
    dec_vs_qe = np.array([1.0, 1.0, 4.0, 1.0, 1.0])
    cv = np.array([0.03, 0.03, 0.03, 0.03, 0.12])
    amp = np.array([0.05, 0.05, 0.05, 0.40, 0.05])
    assert list(E.classify(qe, dec, dec_vs_qe, cv, amp)) == ["steady", "quarter_end", "year_end", "seasonal", "lumpy"]


def test_profile_recognises_synthetic_shapes():
    months = [y * 100 + m for y in range(2022, 2026) for m in range(1, 13)]
    cal = np.array([k % 100 for k in months])
    steady = np.full(48, 100.0)
    quarter = np.where(np.isin(cal, [3, 6, 9, 12]), 260.0, 47.0)
    year_end = np.where(cal == 12, 400.0, 100.0)
    seasonal = 100.0 * (1 + 0.25 * np.where(cal == 3, 1, 0) - 0.25 * np.where(cal == 8, 1, 0))
    N = np.vstack([steady, quarter, year_end, seasonal])
    prof = E.profile_at(N, 48, months, np.array(["A"] * 4), 36)
    assert list(prof.cls) == ["steady", "quarter_end", "year_end", "seasonal"]
    assert np.allclose(prof.si.mean(axis=1), 1.0)


def test_pattern_classes_agree_with_the_generator(raw, snap):
    truth = pd.read_parquet(ROOT / "data" / "eval_truth_patterns.parquet")      # tests may read the hidden truth
    got = pd.DataFrame(raw("SELECT bu_id, pattern_class FROM landing_bu_profile WHERE snapshot_date = :s", s=snap),
                       columns=["bu_id", "pattern_class"])
    m = truth.merge(got, on="bu_id")
    assert len(m) == len(truth) and (m["pattern"] == m["pattern_class"]).mean() >= 0.9


# ------------------------------------------------------------------------------------------ methods
def test_m1_same_month_last_year_times_growth():
    t = np.arange(40)
    N = (100 * 1.10 ** (t / 12))[None, :]
    pred = E.m1_yoy(N, 36, np.ones(1))
    assert pred[0] == pytest.approx(100 * 1.10 ** 3, rel=0.01)


def test_m2_trailing_average_times_seasonal_index():
    si = np.array([[1.2, 0.8] * 6])
    cal = np.arange(36) % 12
    N = 100 * si[0, cal][None, :]
    pred = E.m2_seasonal(N, 36, np.ones(1), si, 0)       # flat level, January index 1.2
    assert pred[0] == pytest.approx(120.0, rel=1e-9)


def test_m3_bias_correction_shrinks_toward_one():
    A = np.full((1, 30), 90.0)
    F = np.full((1, 30), 100.0)                           # the BU's forecasts were 10% too optimistic
    pred, ratio = E.m3_forecast_bias(A, F, 30, np.array([100.0]), n0=6.0)
    assert ratio[0] == pytest.approx(1 - 24 / 30 * 0.10)  # 24 months of history, shrink n / (n + 6)
    assert pred[0] == pytest.approx(100 * ratio[0])
    _, r_short = E.m3_forecast_bias(A, F, 3, np.array([100.0]), n0=6.0)
    assert 1 - r_short[0] < 1 - ratio[0]                  # less history, closer to 1


def test_m4_ets_forecasts_a_seasonal_series():
    t = np.arange(48)
    y = 1000 * (1 + 0.2 * np.sin(2 * np.pi * t / 12)) * 1.003 ** t
    out = E.m4_ets({48: y[None, :]}, 36, workers=1)
    nxt = 1000 * (1 + 0.2 * np.sin(2 * np.pi * 48 / 12)) * 1.003 ** 48
    assert out[48][0] == pytest.approx(nxt, rel=0.05)


def test_ensemble_weights_inverse_wape_shrunk_to_the_class():
    wape = np.array([0.10, 0.20, np.nan, 0.05])
    inv_class = np.array([5.0, 5.0, 5.0, 5.0])
    avail = np.array([True, True, False, True])
    w0 = E.blend_weights(wape, inv_class, avail, n=0, n0=6)
    assert w0 == pytest.approx([1 / 3, 1 / 3, 0, 1 / 3])          # no own history: the class weights
    w = E.blend_weights(wape, inv_class, avail, n=600, n0=6)
    own, lam = np.array([10, 5, 0, 20]) / 35, 600 / 606
    assert w == pytest.approx(lam * own + (1 - lam) * np.array([1 / 3, 1 / 3, 0, 1 / 3]), rel=1e-9)
    assert w.sum() == pytest.approx(1.0) and w[2] == 0 and w[3] > w[0] > w[1]
    assert E.blend_weights(wape, inv_class, np.zeros(4, bool), 12, 6).sum() == 0


def test_margin_is_a_ratio_of_sums_and_na_for_bad_denominators():
    assert list(np.round(E.margin([10.0, 5.0, 3.0], [100.0, 0.0, -4.0]), 6)[:1]) == [0.1]
    assert np.isnan(E.margin([5.0], [0.0])[0]) and np.isnan(E.margin([3.0], [-4.0])[0])


def test_simulation_keeps_the_p50_and_spreads_with_past_errors():
    p50 = np.array([100.0, 50.0])
    flat = E.simulate(p50, np.zeros((2, 0)), 200, 7)
    assert np.allclose(flat, p50)
    R = np.log(np.array([[1.05, 0.95, 1.10, 0.92, 1.02, 0.97, 1.04, 0.99],
                         [0.90, 1.12, 1.01, 0.96, 1.08, 0.94, 1.00, 1.03]]))
    draws = E.simulate(p50, R, 1000, 7)
    lo, hi = np.quantile(draws.sum(axis=1), [0.1, 0.9])
    assert lo < p50.sum() < hi
    assert np.allclose(E.simulate(p50, R, 1000, 7), draws)        # seeded


def test_mtd_input_is_ignored_when_the_flag_is_off(monkeypatch):
    d = SimpleNamespace(mtd={1: 123.0})
    b50, q10, q90 = np.array([100.0]), np.array([-0.1]), np.array([0.1])
    assert E.cfg()["mtd_snapshot_enabled"] is False
    out = E.maybe_apply_mtd(d, 0, AS_OF, b50.copy(), q10.copy(), q90.copy())
    assert out[0][0] == 100.0 and out[3] is False
    original = E.cfg
    monkeypatch.setattr(E, "cfg", lambda: {**original(), "mtd_snapshot_enabled": True})
    monkeypatch.setattr(E, "apply_mtd", lambda *a: (np.array([111.0]), a[4], a[5], True))
    assert E.maybe_apply_mtd(d, 0, AS_OF, b50.copy(), q10.copy(), q90.copy())[3] is True


def test_no_mtd_snapshot_used_by_the_stored_landing(raw, snap):
    assert raw("SELECT COUNT(*) FROM landing_mtd_snapshot")[0][0] == 0
    used = raw("SELECT mtd_used FROM landing_run WHERE snapshot_date = :s", s=snap)[0][0]
    assert not bool(used)


# ------------------------------------------------------------------------------------------ stored landing
LINES_OF = {"billing": [1], "revenue": [1, 2], "production": [1, 2, 4, 5], "maop": [1, 2, 4, 5, 7, 8, 9, 10, 12]}


def test_every_bu_has_every_measure_for_the_open_month(raw, snap):
    n_bu = raw("SELECT COUNT(*) FROM dim_org")[0][0]
    rows = raw("SELECT measure, COUNT(DISTINCT bu_id) FROM fact_landing WHERE snapshot_date = :s AND month_key = :m "
               "GROUP BY measure", s=snap, m=OPEN)
    got = {r[0]: int(r[1]) for r in rows}
    for meas in ("billing", "revenue", "production", "personnel", "subcontracting", "other_cost",
                 "functional_neutralization", "functional_cost", "maop", "maop_margin_revenue", "maop_margin_production"):
        assert got.get(meas) == n_bu, meas
    other = raw("SELECT COUNT(*) FROM fact_landing WHERE snapshot_date = :s AND month_key <> :m", s=snap, m=OPEN)
    assert other[0][0] == 0                                         # only the open month


@pytest.mark.parametrize("measure", list(LINES_OF))
def test_bu_landing_reconciles_with_its_accounts(raw, snap, measure):
    lines = ", ".join(str(x) for x in LINES_OF[measure])
    rows = raw(f"""SELECT l.bu_id, l.p50, x.total FROM fact_landing l
                   JOIN (SELECT f.bu_id, SUM(f.amount_usd) AS total FROM fact_landing_leaf f
                         JOIN dim_account a ON a.account_id = f.account_id
                         WHERE f.snapshot_date = :s AND f.month_key = :m AND a.line_no IN ({lines})
                         GROUP BY f.bu_id) x ON x.bu_id = l.bu_id
                   WHERE l.snapshot_date = :s AND l.month_key = :m AND l.measure = :meas""", s=snap, m=OPEN, meas=measure)
    assert rows and all(abs(float(p) - float(t)) < 0.02 for _, p, t in rows)


def test_wip_is_zero_and_revenue_equals_billing(raw, snap):
    wip = raw("SELECT MAX(ABS(p50)) FROM fact_landing WHERE snapshot_date = :s AND measure = 'wip_ui'", s=snap)[0][0]
    leaf = raw("""SELECT COALESCE(MAX(ABS(f.amount_usd)), 0) FROM fact_landing_leaf f JOIN dim_account a
                  ON a.account_id = f.account_id WHERE f.snapshot_date = :s AND a.line_no = 2""", s=snap)[0][0]
    assert float(wip) == 0 and float(leaf) == 0
    diff = raw("""SELECT MAX(ABS(r.p50 - b.p50)) + MAX(ABS(r.p10 - b.p10)) + MAX(ABS(r.p90 - b.p90))
                  FROM fact_landing r JOIN fact_landing b ON b.snapshot_date = r.snapshot_date
                  AND b.bu_id = r.bu_id AND b.month_key = r.month_key
                  WHERE r.snapshot_date = :s AND r.measure = 'revenue' AND b.measure = 'billing'""", s=snap)[0][0]
    assert float(diff) < 1e-6


def test_group_landing_is_the_sum_of_bu_landings_with_a_range(raw, snap):
    from app.landing.query import LandingQuery
    from app.semantic.query_builder import SemanticLayer

    q = LandingQuery(SemanticLayer("group_cfo", AS_OF))
    w50, wD, info = q.landing_wide({})
    reg = q.sl.reg
    for measure in ("billing", "production", "maop"):
        p50, lo, hi = q.value_and_range("metric", reg.metrics[measure], w50, wD)
        bu_sum = raw("SELECT SUM(p50) FROM fact_landing WHERE snapshot_date = :s AND measure = :m", s=snap, m=measure)[0][0]
        assert p50 == pytest.approx(float(bu_sum), abs=0.05) and lo < p50 < hi, measure
    p50, lo, hi = q.value_and_range("ratio", reg.ratios["maop_margin_revenue"], w50, wD)
    maop = raw("SELECT SUM(p50) FROM fact_landing WHERE snapshot_date = :s AND measure = 'maop'", s=snap)[0][0]
    rev = raw("SELECT SUM(p50) FROM fact_landing WHERE snapshot_date = :s AND measure = 'revenue'", s=snap)[0][0]
    assert p50 == pytest.approx(float(maop) / float(rev), abs=1e-9)          # aggregate margin = ratio of sums


def test_hidden_truth_falls_inside_the_group_range(snap):
    """The generator's true November billing (tests only) lies inside the group P10-P90."""
    from app.landing.query import LandingQuery
    from app.semantic.query_builder import SemanticLayer

    truth = pd.read_parquet(ROOT / "data" / "eval_truth_open_month.parquet")
    q = LandingQuery(SemanticLayer("group_cfo", AS_OF))
    acc = q.sl.d.account
    billing_ids = set(acc[(acc["line_no"] == 1) & acc["is_leaf"]]["account_id"].astype(int))
    true_billing = truth[truth["account_id"].isin(billing_ids) & (truth["month_key"] == OPEN)]["amount_usd"].sum()
    w50, wD, _ = q.landing_wide({})
    p50, lo, hi = q.value_and_range("metric", q.sl.reg.metrics["billing"], w50, wD)
    assert lo <= true_billing <= hi


# ------------------------------------------------------------------------------------------ answers
def test_landing_answer_states_month_range_wip_and_monthly_data():
    ans, mem = ask("What's the November landing for the United States?", "group_cfo", model="rules", as_of=AS_OF)
    assert ans.status == "ok" and mem["tool"] == "get_landing"
    text = ans.answer_markdown
    assert "Nov 2026" in text and AS_OF.isoformat() in text and "P10-P90" in text
    notes = " ".join(ans.filters_used.get("notes") or [])
    assert "WIP is 0" in notes and "monthly history only" in notes
    assert ans.table and ans.chart_spec.type == "landing_trend"
    assert ans.filters_used.get("landing_snapshot") and ans.filters_used.get("landing_month") == "Nov 2026"


def test_closed_month_returns_actuals_and_future_month_the_forecast(raw):
    ans, _ = ask("What's the October landing for Canada?", "group_cfo", model="rules", as_of=AS_OF)
    assert ans.status == "ok" and "closed month" in ans.answer_markdown
    actual = raw("""SELECT SUM(f.amount_usd) FROM fact_pnl f JOIN dim_account a ON a.account_id = f.account_id
                    JOIN dim_org o ON o.bu_id = f.bu_id JOIN dim_version v ON v.version_id = f.version_id
                    WHERE v.name = 'Actual' AND f.month_key = 202610 AND a.line_no = 1 AND o.l3_country = 'Canada'""")[0][0]
    assert _has(_evidence(ans), float(actual))
    ans, _ = ask("What's the December landing for Canada?", "group_cfo", model="rules", as_of=AS_OF)
    assert ans.status == "ok" and "future" in ans.answer_markdown and "FC3" in ans.answer_markdown


def test_ytd_margin_including_the_landing_matches_the_fixture(raw, snap):
    """Acceptance criterion 8: Jan-Oct actuals + November landing for both margins, vs PY, Budget, latest FC."""
    ans, mem = ask("What will YTD MAOP margin be through November including the landing?", "group_cfo",
                   model="rules", as_of=AS_OF)
    assert ans.status == "ok" and mem["tool"] == "get_ytd_with_landing"

    def actual(lines: str, version: str, m0: int, m1: int) -> float:
        return float(raw(f"""SELECT SUM(f.amount_usd) FROM fact_pnl f JOIN dim_account a ON a.account_id = f.account_id
                             JOIN dim_version v ON v.version_id = f.version_id
                             WHERE v.name = :v AND f.month_key BETWEEN :a AND :b AND a.line_no IN ({lines})""",
                         v=version, a=m0, b=m1)[0][0])

    def landing(measure: str) -> float:
        return float(raw("SELECT SUM(p50) FROM fact_landing WHERE snapshot_date = :s AND measure = :m",
                         s=snap, m=measure)[0][0])
    maop_l, rev_l, prod_l = "1, 2, 4, 5, 7, 8, 9, 10, 12", "1, 2", "1, 2, 4, 5"
    fixture = {
        "revenue margin incl. landing": (actual(maop_l, "Actual", 202601, 202610) + landing("maop"))
        / (actual(rev_l, "Actual", 202601, 202610) + landing("revenue")),
        "production margin incl. landing": (actual(maop_l, "Actual", 202601, 202610) + landing("maop"))
        / (actual(prod_l, "Actual", 202601, 202610) + landing("production")),
        "PY": actual(maop_l, "Actual", 202501, 202511) / actual(rev_l, "Actual", 202501, 202511),
        "Budget": actual(maop_l, "Budget", 202601, 202611) / actual(rev_l, "Budget", 202601, 202611),
        "FC3": actual(maop_l, "FC3", 202601, 202611) / actual(rev_l, "FC3", 202601, 202611),
    }
    ev = _evidence(ans)
    for name, value in fixture.items():
        assert _has(ev, value, rel=1e-7), (name, value)
    text = ans.answer_markdown
    assert "Operating margin on revenue" in text and "Operating margin on production" in text
    assert f"{100 * fixture['revenue margin incl. landing']:.1f}%" in text


def test_landing_respects_row_level_security(raw, snap):
    ans, _ = ask("What's the November landing for Canada?", "us_country_head", model="rules", as_of=AS_OF)
    assert ans.status == "refusal" and not ans.table
    ans, _ = ask("What's the November landing?", "us_country_head", model="rules", as_of=AS_OF)
    us = raw("""SELECT SUM(l.p50) FROM fact_landing l JOIN dim_org o ON o.bu_id = l.bu_id
                WHERE l.snapshot_date = :s AND l.measure = 'billing' AND o.l3_country = 'United States'""", s=snap)[0][0]
    assert ans.status == "ok" and _has(_evidence(ans), float(us)) and "Canada" not in ans.answer_markdown


# ------------------------------------------------------------------------------------------ hidden truth boundary
def test_app_code_never_reads_the_hidden_truth():
    hits = [str(p.relative_to(ROOT)) for p in (ROOT / "app").rglob("*.py") if "eval_truth" in p.read_text()]
    assert hits == []
    from app.db import TABLE_LOAD_ORDER
    assert not any("eval_truth" in t for t in TABLE_LOAD_ORDER)
    for script in ("load_mssql.py", "export_duckdb.py", "run_landing.py", "export_data_manual.py"):
        assert "eval_truth" not in (ROOT / "scripts" / script).read_text(), script


def test_landing_vs_plan_question_gets_the_comparison_bar_chart():
    ans, _ = ask("What's the landing for Mexico this month vs the latest forecast?", "group_cfo", model="rules",
                 as_of=AS_OF)
    assert ans.status == "ok" and ans.chart_spec.type == "landing_bars"
    labels = [d["label"] for d in ans.chart_spec.data]
    assert labels[0] == "Landing (P50)" and "Budget" in labels and "PY" in labels and any(l.startswith("FC") for l in labels)
    first = ans.chart_spec.data[0]
    assert first["lo"] <= first["value"] <= first["hi"]


def _stub_planner(monkeypatch, call: dict):
    """The planner LLM returns `call`; the writer gets no text and the templated answer is used."""
    from app.agent import graph, llm
    fake = llm.LLMResult(content="", tool_calls=[call], native_tool_call=True)
    monkeypatch.setattr(graph.llm, "chat", lambda *a, **k: fake)


def test_landing_tool_without_landing_wording_goes_to_the_router(monkeypatch):
    # "latest forecast for the full year" is a forecast question; an LLM that picks the landing tool is overruled
    _stub_planner(monkeypatch, {"name": "get_ytd_with_landing",
                                "arguments": {"metric_or_ratio": "operating profit", "period_type": "FY"}})
    ans, mem = ask("What does the latest forecast say for the full year 2026 for the group?", "group_cfo",
                   model="ollama/stub", as_of=AS_OF)
    assert ans.status == "ok" and mem["tool"] in ("get_pnl", "compare_versions")
    assert "router_not_landing" in ans.diagnostics["tool_choice_source"]


def test_landing_tool_is_kept_for_a_landing_question(monkeypatch, snap):
    _stub_planner(monkeypatch, {"name": "get_ytd_with_landing",
                                "arguments": {"metric_or_ratio": "revenue", "through_month": "November"}})
    ans, mem = ask("What will YTD revenue be through November including the landing?", "group_cfo",
                   model="ollama/stub", as_of=AS_OF)
    assert ans.status == "ok" and mem["tool"] == "get_ytd_with_landing"
    assert "router" not in ans.diagnostics["tool_choice_source"]
