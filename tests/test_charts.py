"""Chart rendering checks that need no database."""
from __future__ import annotations

from app.viz.charts import figure, waterfall_range


def _bridge(values: list[float]) -> dict:
    measures = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]
    rows = [{"label": f"s{i}", "value": v, "measure": m} for i, (v, m) in enumerate(zip(values, measures))]
    return {"type": "waterfall", "title": "t", "fmt": "eur", "x": "label", "y": ["value"], "data": rows,
            "meta": {"favorable": "up"}}


def test_small_step_bridge_zooms_axis():
    # Operating profit PY 51.0M, steps of a few M, Actual 54.5M: the axis must not start at zero.
    values = [51.0e6, 3.5e6, -2.0e6, 1.0e6, 1.0e6, 54.5e6]
    rng = figure(_bridge(values)).layout.yaxis.range
    assert rng is not None
    lo, hi = rng
    assert 0 < lo < 51.0                      # axis in USD M; below the lowest running level
    assert hi > 54.5                          # headroom above the highest level for the labels


def test_large_drop_bridge_keeps_zero_axis():
    # Production 1,325M down to Operating profit 187M: steps are large, keep the default axis.
    values = [1325e6, -600e6, -300e6, -238e6, 187e6]
    assert figure(_bridge(values)).layout.yaxis.range is None
    assert waterfall_range([1325.0, -600.0, -300.0, -238.0, 187.0],
                           ["absolute", "relative", "relative", "relative", "total"]) is None


def test_negative_levels_keep_default_axis():
    assert waterfall_range([2.0, -5.0, -3.0], ["absolute", "relative", "total"]) is None
