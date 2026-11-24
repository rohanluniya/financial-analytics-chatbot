# Demo stories

The synthetic data contains business stories that a demo can find in the numbers. Figures for stories
1-5 are read from the generated tables (`data/stories.json`, written by `scripts/generate_data.py`);
landing figures come from the landing engine (`make landing`) for the as-of date 2026-11-16, so the last
closed month is October 2026 and the landing month is November 2026. USD at a constant budget rate.

## Billing patterns and forecast bias

Each BU has a billing pattern and a planning bias, so the landing has realistic shapes to learn:

| Pattern | What it looks like | BUs |
|---|---|---:|
| Steady | Billing spread evenly through the year, mild seasonality | 23 |
| Quarter-end loaded | A large share of billing in March, June, September and December | 44 |
| Year-end loaded | A large share in December (annual fees and audits) | 11 |
| Seasonal | A March peak and an August dip | 9 |
| Lumpy | Project billing: large, irregular months | 19 |

Planning bias per BU: 57 neutral, 34 optimistic (forecasts above the eventual actuals) and 15
conservative. Working days per country come from the public-holiday calendar of the `holidays` package,
and billing moves with them. The engine classifies every BU from its own history; its classes agree with
the generator for all 106 BUs (`landing_bu_profile` vs `data/eval_truth_patterns.parquet`, which only
tests read).

## Landing stories (November 2026)

| # | Where | Story | Question to ask |
|---|---|---|---|
| L-a | United States · Industry & Energy (5 BUs) | Year-on-year momentum: the landing is above budget | What's the November landing for US Industry & Energy? |
| L-b | Canada · Industry & Energy (2 BUs) | Optimistic forecast: bias correction lands below FC3 | What's the landing for Canada Industry & Energy this month vs the latest forecast? |
| L-c | MX-CPS-MTY-01 (Mexico · Consumer Products) | Genuine shortfall from a downward trend | Which BUs are expected to miss budget this month? |
| L-d | US-BNI-LAX-01 (United States · Buildings & Infrastructure) | Lumpy project billing: a wide P10-P90 | Explain the landing for US-BNI-LAX-01 |

Billing landing, November 2026 (P50 with the P10-P90 range), against the plan and last year. The last
column is the generator's hidden month-end value, which the app never reads; tests use it to check the
engine.

| Story | Landing P50 | P10-P90 | Budget | FC3 | PY (Nov 2025) | Hidden actual |
|---|---:|---:|---:|---:|---:|---:|
| L-a US Industry & Energy | USD 17.76M | 17.33M - 18.93M | 16.14M | 18.51M | 14.80M | 17.80M |
| L-b Canada Industry & Energy | USD 2.53M | 2.33M - 2.62M | 2.58M | 2.83M | 2.38M | 2.37M |
| L-c MX-CPS-MTY-01 | USD 656k | 626k - 684k | 712k | 624k | 645k | 654k |
| L-d US-BNI-LAX-01 | USD 1.16M | 842k - 1.78M | 1.20M | 1.16M | 817k | 1.28M |
| Group (106 BUs) | USD 120.46M | 118.63M - 124.27M | 121.03M | 121.86M | 112.15M | 121.08M |

- **L-a:** the landing is 10.1% above budget and 20.0% above November 2025; the budget was set before the
  growth showed.
- **L-b:** both BUs' forecasts have run above their actuals. The forecast-accuracy method scales FC3 down
  (CA-IND-TOR-01: FC3 USD 1.65M, corrected 1.58M; CA-IND-CAL-01: 1.18M, corrected 1.11M), and the
  history-based methods sit lower still, so the landing is 10.9% below FC3.
- **L-c:** billing has drifted down; the landing is 7.9% below budget.
- **L-d:** the methods disagree (from USD 706k to 1.31M), so the P10-P90 range is about 80% of the P50,
  against 4.7% for the group.

## 1. US Elevators & Pressure Vessels: bonus spike (March 2025)

| Item | March 2025 | March 2024 |
|---|---:|---:|
| Direct staff bonus | USD 469.3k | USD 151.5k |
| Direct staff costs | USD 1.61M | USD 1.26M |

- The March 2025 bonus is 3.1x March 2024; the other months of 2025 average USD 99.6k.
- The bonus explains 89.8% of the USD 354k increase in direct staff costs vs PY.
- Ask: *Break down direct staff costs for US Elevators & Pressure Vessels in March 2025.*

## 2. Canada Environmental Lab Testing: lost contract (2026)

| YTD October | 2026 Actual | 2025 Actual (PY) | 2026 Budget |
|---|---:|---:|---:|
| Production | USD 53.3M | USD 62.2M | USD 67.3M |
| Personnel costs | USD 27.1M | USD 28.7M | USD 30.8M |
| Operating profit | USD 1.31M | USD 7.45M | USD 8.57M |
| Operating margin on revenue | 2.5% | 12.1% | |
| Utilization rate | 67.4% | 73.7% | |

- Production is 14.2% below PY and 20.7% below budget.
- Personnel costs adjust from May 2026 (about USD 2.9-3.1M a month in January-April, about USD 2.5M from
  May), three months after the volume loss.
- A one-off restructuring charge of USD 1.44M (other operating expenses) is booked in May 2026.

The employee records tell the same story:

| YTD October | 2026 | 2025 (PY) |
|---|---:|---:|
| Average headcount | 353 | 382 |
| Hires | 47 | 47 |
| Leavers (voluntary / restructuring) | 93 (32 / 61) | 36 (34 / 2) |
| Attrition rate, annualised | 31.7% | 11.3% |

- 58 of the 61 restructuring leavers leave in April 2026.
- Utilization by role, YTD 2026: lab analyst 67.6%, chemist 67.6%, lab technician 67.3%.
- Ask: *Why did Canada Environmental Lab Testing margin drop in 2026?* and *Attrition by role for Canada
  Environmental Lab Testing this year vs last year.*

## 3. Mexico Buildings & Infrastructure: WIP build-up and reversal (2026)

| Period | Work-in-progress change |
|---|---:|
| January-June 2026 (build-up) | +USD 873k |
| July-September 2026 (reversal) | -USD 829k |
| YTD October 2026 | +USD 35k |
| YTD October 2025 | +USD 194k |

Billing averages USD 817k a month in January-June and USD 1.22M a month in July-October, when the work in
progress is invoiced. The P&L line "WIP & deferred income" (work-in-progress change plus deferred income
change) shows the same build-up and reversal. Ask: *What happened to WIP in Mexico Buildings &
Infrastructure this year?*

## 4. Chile Metals & Minerals: subcontracting above budget (2026)

| YTD October | Value |
|---|---:|
| External subcontracting, Actual 2026 | USD 2.91M |
| External subcontracting, Budget 2026 | USD 2.17M (Actual is 34.3% above budget) |
| External subcontracting, Actual 2025 | USD 2.05M (2026 is 41.8% above PY) |
| Subcontracting as % of production | 5.3% (2026) vs 4.0% (2025) |
| Operating profit, Actual vs Budget | USD 8.09M vs USD 8.26M |

Ask: *Why is Chile Metals & Minerals subcontracting above budget?*

## 5. Canada Power & Utilities: margin improvement

| Operating margin on revenue | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|
| YTD October | 9.5% | 9.5% | 13.2% | 13.1% | 15.1% |
| Full year | 9.7% | 9.9% | 13.0% | 13.5% | |

Ask: *How has the operating margin of Canada Power & Utilities developed since 2022?*
