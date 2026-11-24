# What's the November landing for the United States?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.38 s
- **Tool:** `get_landing` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Landing for United States, Nov 2026 (open month; as of 2026-11-16, computed 2026-11-16): P50 is the expected month-end, P10-P90 the range.**

- Billing: P50 USD 35.2M (P10-P90 USD 34.5M - USD 36.7M); USD 1.4M (4.1%) above Budget Nov 2026 (USD 33.8M), favourable; USD 1.2M (3.3%) below FC3 Nov 2026 (USD 36.4M), unfavourable; USD 4.5M (14.8%) above PY (Nov 2025) (USD 30.6M), favourable
- Revenue: P50 USD 35.2M (P10-P90 USD 34.5M - USD 36.7M); USD 1.9M (5.7%) above Budget Nov 2026 (USD 33.3M), favourable; USD 662k (1.8%) below FC3 Nov 2026 (USD 35.8M), unfavourable; USD 4.9M (16.0%) above PY (Nov 2025) (USD 30.3M), favourable
- Production: P50 USD 35.5M (P10-P90 USD 34.8M - USD 37.0M); USD 1.9M (5.8%) above Budget Nov 2026 (USD 33.5M), favourable; USD 656k (1.8%) below FC3 Nov 2026 (USD 36.1M), unfavourable; USD 4.9M (16.1%) above PY (Nov 2025) (USD 30.6M), favourable
- Operating profit: P50 USD 6.3M (P10-P90 USD 5.7M - USD 7.4M); USD 1.5M (30.8%) above Budget Nov 2026 (USD 4.8M), favourable; USD 632k (9.2%) below FC3 Nov 2026 (USD 6.9M), unfavourable; USD 2.9M (87.6%) above PY (Nov 2025) (USD 3.3M), favourable
- Operating margin on revenue: P50 17.8% (P10-P90 16.6% - 20.3%); 3.4 pp above Budget Nov 2026 (14.4%), favourable; 1.4 pp below FC3 Nov 2026 (19.2%), unfavourable; 6.8 pp above PY (Nov 2025) (11.0%), favourable
- Operating margin on production: P50 17.6% (P10-P90 16.5% - 20.1%); 3.4 pp above Budget Nov 2026 (14.3%), favourable; 1.4 pp below FC3 Nov 2026 (19.1%), unfavourable; 6.7 pp above PY (Nov 2025) (10.9%), favourable

_WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data. Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time._

## Table

| Measure | Landing (P50) | P10 | P90 | Budget | vs Budget | FC3 | vs FC3 | PY | vs PY | Actual Oct 2026 |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Billing | 35,167 | 34,465 | 36,674 | 33,793 | 1,374 | 36,386 | (1,218) | 30,646 | 4,521 | 35,483 |
| Revenue | 35,167 | 34,465 | 36,674 | 33,278 | 1,889 | 35,829 | (662) | 30,314 | 4,853 | 35,269 |
| Production | 35,489 | 34,777 | 37,014 | 33,547 | 1,942 | 36,144 | (656) | 30,575 | 4,914 | 35,590 |
| Operating profit | 6,260 | 5,729 | 7,437 | 4,785 | 1,474 | 6,892 | (632) | 3,336 | 2,924 | 6,577 |
| Operating margin on revenue | 17.8% | 16.6% | 20.3% | 14.4% | 3.4 pp | 19.2% | (1.4 pp) | 11.0% | 6.8 pp | 18.6% |
| Operating margin on production | 17.6% | 16.5% | 20.1% | 14.3% | 3.4 pp | 19.1% | (1.4 pp) | 10.9% | 6.7 pp | 18.5% |

_USD k · Landing = expected month-end of Nov 2026. WIP is 0 in the landing month, so the revenue landing equals the billing landing. Margins in %, variances in pp. Green / red = favourable / unfavourable vs the comparison._

## Chart

`landing_trend` - Billing 2026: actuals, Nov 2026 landing (P10-P90), PY and Budget - United States ([interactive chart](23_what_s_the_november_landing_for_the_united_state_chart.html))

## Filters, version and period used

- Scope: United States
- Period: Nov 2026 (Nov 2026 (landing, open month))
- Versions: Landing (P50, P10-P90)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)
- Note: WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data.
- Note: Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time.

## Follow-up questions

1. Which BUs in United States are expected to miss budget this month?
2. What will YTD operating margin be through Nov including the landing for United States?
3. Explain the landing for United States

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_landing",
      "arguments": {
        "org": "United States",
        "measures": [],
        "month": "2026-11"
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
    "preprocess": 0.009,
    "plan": 0.0,
    "act": 0.371,
    "write#1": 0.0
  }
}
```
