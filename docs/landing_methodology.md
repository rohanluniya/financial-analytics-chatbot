# Landing methodology

The landing is the expected month-end result of the **open month**: the month after the last closed month.
Months close on the 5th of the following month, so with an as-of date of 2026-11-16 the last closed month is
October 2026 and the landing month is November 2026. A closed month has no landing (its actuals are
shown) and a future month has none either (the latest forecast is shown).

The landing is calculated by a deterministic Python engine (`app/landing/engine.py`), never by the language
model. It uses **monthly data only**: closed-month actuals, the Budget and the forecasts FC1-FC3 that were
published by the as-of date. There are no daily billing tables and no intra-month curves.

## What is estimated

For every BU, and by adding up for every higher level (business, product line, country, region, group):

| Measure | How |
|---|---|
| Billing | Weighted ensemble of four methods (below), with P10 / P50 / P90 |
| WIP & deferred income | 0 in the landing month (fixed rule), so **revenue = billing** |
| Intragroup revenue and subcontracting | Ratio to billing for the same calendar month in the last two years |
| Personnel costs | Run-rate of the last three months x the seasonal factor of that calendar month (carries the March bonus) |
| External subcontracting, other costs | Ratio to billing, half recent months and half the same month last year |
| Functional cost recharges, functional costs | Latest forecast for the month |
| Production, gross profit, operating profit | The semantic layer's formulas on the landed lines |
| Operating margin on revenue / on production | Ratios of the sums (never averages of BU margins) |

Each line's P50 is split over its leaf accounts with shares from recent months (personnel uses the same
month last year), rounded to cents so that leaves add up exactly to the line. The landing therefore
reconciles bottom-up: every BU's measures equal the sum of its accounts, and every higher level equals the
sum of its BUs.

## Billing methods

All methods work on billing adjusted for working days. Working days per country come from the public
holiday calendar (`dim_calendar`, `working_days`, built with the `holidays` package); the working-day
elasticity is estimated from history (year-on-year changes of billing against year-on-year changes of
working days, per BU and demeaned).

| Method | Forecast for the open month |
|---|---|
| M1 Same month last year x recent growth | Same month last year x the average of the 3-month and 6-month year-on-year growth (bounded) |
| M2 Trailing 12 months x seasonal index | Average of the last 12 months x the BU's seasonal index for the month x half a year of trend |
| M3 Latest forecast x the BU's forecast accuracy | Latest forecast (FC3 > FC2 > FC1 > Budget) x the BU's actual / forecast ratio over the last 24 months, shrunk toward 1 by n / (n + 6) |
| M4 Exponential smoothing | Damped-trend, multiplicative-season ETS (`statsmodels`) on the last 48 months, BUs with at least 36 months |

## Profiles and pattern classes

Each BU is profiled from up to four years of history: the seasonal index, the share of billing in quarter-end
months and in December, the size of a March-vs-August swing, and the volatility left after removing the
seasonal shape. Rules on these measures classify the BU as steady, quarter-end loaded, year-end loaded,
seasonal or lumpy. The seasonal index is shrunk toward the product line's index when the history is short
or noisy (lumpy BUs are shrunk more).

## Ensemble weights

For each BU the weight of a method is its inverse WAPE over the previous 12 months, shrunk toward the
inverse WAPE of the same method across the BU's pattern class by n / (n + 6), where n is the number of
months in the BU's window. Methods without a prediction get weight 0. The weights are stored per BU
(`landing_method`, `fact_landing.method_weights_json`) and shown by *Explain the landing*.

## Ranges (P10 / P90)

The range comes from the engine's own past errors: the 10th and 90th percentiles of log(actual / P50) over
the previous 24 months, per BU when it has at least 18 past errors and otherwise per pattern class. For any
total above the BU (a business, a country, the group), the P50 is the exact sum of the BU P50s and the
range comes from a seeded simulation with 1,000 draws: a common shock (the size-weighted average error of a
random past month) plus a BU-specific error of another random past month. Margin ranges are computed from
the same draws, as ratios of the simulated sums.

## Optional month-to-date input

`landing.mtd_snapshot_enabled` in `config/settings.yaml` is **false**. When it is true and month-to-date
billing exists in `landing_mtd_snapshot`, the elapsed working-day share of the month is taken from the
snapshot and the rest from the model, and the range narrows accordingly. With the flag off (the default)
the table is ignored; this prototype has no month-to-date data.

## Running it

```bash
make landing                    # landing for the data as-of date (writes one snapshot; idempotent)
make landing AS_OF=2026-09-15   # landing as it would have been on another date
make backtest                   # last 24 closed months; writes docs/landing_backtest_report.md
make k8s-cronjob                # optional private CronJob that refreshes the landing daily
```

A run replaces the whole snapshot of its as-of date in one transaction. The tables are `fact_landing`
(BU x measure, P10 / P50 / P90, method weights, pattern class), `fact_landing_leaf` (P50 per leaf
account), `landing_method`, `landing_bu_profile`, `landing_residual`, `landing_run` and
`landing_backtest_metric`. All tables with a BU carry the same row-level security as the P&L facts.

In the semantic layer the landing is the virtual version **LANDING**: closed months come from `fact_pnl`
and the open month from `fact_landing_leaf`, so "YTD including the landing" (January-October actuals plus
the November landing) and the full-year outlook (actuals + landing + latest forecast) use the same
formulas as every other answer.

## Backtest

`scripts/backtest_landing.py` recomputes the landing for each of the last 24 closed months as of the 15th of
that month, with only the actuals of earlier months and the forecasts published by then. It reports WAPE
and MAPE for billing, revenue and operating profit, the mean absolute error in percentage points for both
margins, and the share of actuals inside P10-P90, by organisation level, product line and pattern class, for
each method, the ensemble and the latest forecast as published. The measured results are in
[landing_backtest_report.md](landing_backtest_report.md) and in the table `landing_backtest_metric`, which the
Data Catalog page and the landing answers read. No other accuracy figure is quoted anywhere.

Two effects of the WIP rule are reported rather than hidden: revenue and operating profit *as booked*
include the month's WIP movement, which the landing sets to 0, so the backtest also shows them
like-for-like (WIP removed from the actuals and from the forecast).

## Limits

- One open month at a time; no intra-month data.
- Lumpy project BUs remain hard to land: their ranges are wide and the latest forecast can be as accurate as
  the ensemble (see the pattern-class table in the backtest report).
- The group-level range is wider than the 70-90% coverage band (see the report); the BU-level coverage is
  inside it.
- The synthetic data has known patterns and planner biases; accuracy on real data must be measured again
  with the same backtest.
