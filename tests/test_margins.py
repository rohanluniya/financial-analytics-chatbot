"""Operating margins: one definition each in metrics.yaml, "profit %" without a base returns both, a named
base returns one, aggregates are ratios of sums, and zero or negative denominators give n/a."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
import yaml

from app.agent.graph import ask
from app.config import ROOT
from app.semantic.dims import dims
from app.semantic.entity_resolver import resolve
from app.semantic.query_builder import safe_ratio
from app.semantic.registry import registry

AS_OF = date(2026, 11, 16)
GENERIC = ["profit %", "MAOP %", "MOP %", "profit percentage", "profit margin", "margin", "EBIT-like margin"]


def test_each_margin_is_defined_once_and_there_is_no_third_definition():
    defs = yaml.safe_load((ROOT / "app" / "semantic" / "metrics.yaml").read_text())
    ratios = defs["ratios"]
    margin_defs = {k: v for k, v in ratios.items() if v.get("num") == "maop"}
    assert set(margin_defs) == {"maop_margin_revenue", "maop_margin_production"}
    assert margin_defs["maop_margin_revenue"]["den"] == "revenue"
    assert margin_defs["maop_margin_production"]["den"] == "production"
    assert margin_defs["maop_margin_revenue"]["name"] == "Operating margin on revenue"
    assert margin_defs["maop_margin_production"]["name"] == "Operating margin on production"
    assert all(v["favorable"] == "up" for v in margin_defs.values())
    # the generic phrases point to the pair, never to a ratio of their own
    pair = defs["ratio_pairs"]["operating_margins"]
    assert pair["members"] == ["maop_margin_revenue", "maop_margin_production"]
    all_syn = {s.lower() for v in ratios.values() for s in v.get("synonyms", [])}
    for g in GENERIC:
        assert g.lower() not in all_syn and g.lower() in {s.lower() for s in pair["synonyms"]}, g


@pytest.mark.parametrize("phrase", GENERIC)
def test_generic_margin_words_resolve_to_both_margins(phrase):
    res = resolve(f"What is the {phrase} of Mexico YTD?", dims().org, AS_OF)
    assert res.both_margins, phrase


@pytest.mark.parametrize("phrase,ratio", [("margin on revenue", "maop_margin_revenue"),
                                          ("MAOP/revenue", "maop_margin_revenue"),
                                          ("margin on production", "maop_margin_production"),
                                          ("MAOP/production", "maop_margin_production")])
def test_a_named_base_resolves_to_one_margin(phrase, ratio):
    res = resolve(f"What is the {phrase} of Mexico YTD?", dims().org, AS_OF)
    assert not res.both_margins and res.ratio == ratio


def test_safe_ratio_gives_na_for_zero_or_negative_denominators():
    out = safe_ratio(pd.Series([10.0, 5.0, 3.0, -2.0]), pd.Series([100.0, 0.0, -4.0, 50.0]))
    assert out.iloc[0] == pytest.approx(0.1) and np.isnan(out.iloc[1]) and np.isnan(out.iloc[2])
    assert out.iloc[3] == pytest.approx(-0.04)                     # a loss on positive revenue is a real margin


def test_profit_pct_answer_shows_both_margins_as_ratios_of_sums(raw):
    ans, mem = ask("What is our profit % YTD?", "group_cfo", model="rules", as_of=AS_OF)
    assert ans.status == "ok" and mem["tool"] == "get_ratio"
    text = ans.answer_markdown
    assert "Operating margin on revenue" in text and "Operating margin on production" in text and "both" in text

    def total(lines: str) -> float:
        return float(raw(f"""SELECT SUM(f.amount_usd) FROM fact_pnl f JOIN dim_account a ON a.account_id = f.account_id
                             JOIN dim_version v ON v.version_id = f.version_id
                             WHERE v.name = 'Actual' AND f.month_key BETWEEN 202601 AND 202610
                             AND a.line_no IN ({lines})""")[0][0])
    maop = total("1, 2, 4, 5, 7, 8, 9, 10, 12")
    for den in ("1, 2", "1, 2, 4, 5"):
        expected = maop / total(den)                               # group margin = sum / sum, not an average
        assert f"{100 * expected:.1f}%" in text


def test_margin_variances_are_in_percentage_points():
    ans, _ = ask("What is the operating margin on revenue for Mexico YTD vs budget?", "group_cfo", model="rules",
                 as_of=AS_OF)
    assert ans.status == "ok" and " pp " in ans.answer_markdown


def test_registry_pair_lookup():
    reg = registry()
    assert reg.pair_for("profit %") is not None
    assert reg.pair_for("margin on revenue") is None


def test_both_margins_keep_values_and_reason_when_the_llm_names_one():
    """An LLM narrative may mention one margin only; the key-figure lines give both actual values and the note
    says why both are shown. The templated answer already says it, so the note is not repeated there."""
    from app.agent.graph import assemble_answer, template_answer
    from app.agent.tools import ToolContext, run_tool
    from app.agent.tools_landing import MARGIN_PAIR_NOTE

    q = "What is the MOP % of the United States vs budget this year?"
    out = run_tool("get_ratio", {"ratio_name": "maop_margin_revenue", "org": "United States", "period": "YTD",
                                 "comparison": "Budget"},
                   ToolContext(user_id="group_cfo", as_of=AS_OF, question=q, resolution=resolve(q, dims().org, AS_OF)))
    assert out.ok and out.kind == "ratio_pair"
    rows = {r["Version"]: r for r in out.data}
    rev, prod = rows["Actual"]["Operating margin on revenue"], rows["Actual"]["Operating margin on production"]
    assert out.bullets[0].startswith(f"Operating margin on revenue: Actual {100 * rev:.1f}%")
    assert out.bullets[1].startswith(f"Operating margin on production: Actual {100 * prod:.1f}%")
    assert "Budget" in out.bullets[1] and " pp " in out.bullets[1]
    llm_text = assemble_answer(f"Operating margin on revenue is {100 * rev:.1f}%, above budget.", [out])
    assert f"{100 * prod:.1f}%" in llm_text and MARGIN_PAIR_NOTE in llm_text
    rules_text = assemble_answer(template_answer([out]), [out])
    assert rules_text.count("No margin base was named") == 1
