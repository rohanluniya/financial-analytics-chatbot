# What will YTD MAOP margin be through November including the landing?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.33 s
- **Tool:** `get_ytd_with_landing` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**YTD Nov 2026 incl. landing for RL Group: closed months Jan 2026 to Oct 2026 are actuals, Nov 2026 is the landing (P50, computed 2026-11-16).**

- Operating margin on revenue YTD Nov 2026 incl. landing: 14.8% (P10-P90 14.7% - 14.9%); 0.8 pp above PY (YTD Nov 2025) (14.0%), favourable; 0.5 pp below Budget (same months) (15.3%), unfavourable; in line with FC3 (same months) (14.8%)
- Operating margin on production YTD Nov 2026 incl. landing: 14.7% (P10-P90 14.6% - 14.9%); 0.8 pp above PY (YTD Nov 2025) (13.9%), favourable; 0.5 pp below Budget (same months) (15.2%), unfavourable; in line with FC3 (same months) (14.7%)

_WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data. Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time._

## Table

| Measure | YTD Nov 2026 incl. landing | P10 | P90 | YTD to Oct 2026 (Actual) | Nov 2026 landing (P50) | PY | vs PY | Budget | vs Budget | FC3 | vs FC3 |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Operating margin on revenue | 14.8% | 14.7% | 14.9% | 14.9% | 13.7% | 14.0% | 0.8 pp | 15.3% | (0.5 pp) | 14.8% | 0.0 pp |
| Operating margin on production | 14.7% | 14.6% | 14.9% | 14.8% | 13.7% | 13.9% | 0.8 pp | 15.2% | (0.5 pp) | 14.7% | 0.0 pp |

_USD k · YTD Nov 2026 incl. landing: closed-month actuals plus the Nov 2026 landing (P50, P10-P90). WIP is 0 in the landing month, so the revenue landing equals the billing landing. Margins in %, variances in pp._

## Chart

`ytd_bars` - Operating margin on revenue by month: YTD Nov 2026 incl. landing - RL Group ([interactive chart](26_what_will_ytd_maop_margin_be_through_november_in_chart.html))

## Filters, version and period used

- Scope: RL Group
- Period: YTD Nov 2026 incl. landing (Jan 2026 - Nov 2026)
- Versions: Landing (P50, P10-P90)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)
- Note: WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data.
- Note: Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time.

## Follow-up questions

1. What's the Nov landing for RL Group?
2. Which BUs in RL Group are expected to miss budget this month?
3. What is the full-year outlook for RL Group?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_ytd_with_landing",
      "arguments": {
        "metric_or_ratio": "operating_margins",
        "org": "",
        "through_month": "",
        "period_type": "YTD",
        "comparisons": [
          "PY",
          "Budget",
          "LatestFC"
        ]
      }
    }
  ],
  "llm_calls": [],
  "guardrail": {
    "ok": true,
    "template": true,
    "history": [
      {
        "attempt": 1,
        "ok": false,
        "unsupported": [
          "<empty>"
        ],
        "checked": 0,
        "problems": [
          "the answer was empty"
        ],
        "draft": ""
      }
    ],
    "unsupported": [
      "<empty>"
    ]
  },
  "errors": [],
  "timings": {
    "preprocess": 0.006,
    "plan": 0.0,
    "act": 0.322,
    "write#1": 0.0
  }
}
```
