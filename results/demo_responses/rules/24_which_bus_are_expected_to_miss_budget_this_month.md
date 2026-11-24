# Which BUs are expected to miss budget this month?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 2.61 s
- **Tool:** `rank_landing` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Billing landing for Nov 2026 by BU in RL Group: 52 of 106 BUs land below budget at P50 (computed 2026-11-16).**

Expected to miss budget (largest shortfall first): 1. CA-ENV-VAN-01 USD 1.4M (P10-P90 USD 1.2M - USD 1.5M), USD 355k (20.4%) below budget (USD 1.7M), unfavourable; 2. PE-BNI-AQP-01 USD 1.3M (P10-P90 USD 1.0M - USD 1.7M), USD 338k (20.4%) below budget (USD 1.7M), unfavourable; 3. CA-ENV-CAL-02 USD 1.4M (P10-P90 USD 1.2M - USD 1.4M), USD 286k (17.3%) below budget (USD 1.7M), unfavourable; 4. CA-BNI-VAN-01 USD 2.4M (P10-P90 USD 2.2M - USD 2.5M), USD 283k (10.7%) below budget (USD 2.6M), unfavourable; 5. CA-ENV-MTL-01 USD 1.1M (P10-P90 USD 976k - USD 1.2M), USD 271k (19.4%) below budget (USD 1.4M), unfavourable; 6. CA-ENV-TOR-01 USD 983k (P10-P90 USD 843k - USD 1.0M), USD 254k (20.5%) below budget (USD 1.2M), unfavourable; 7. CA-BNI-TOR-01 USD 947k (P10-P90 USD 693k - USD 1.8M), USD 235k (19.9%) below budget (USD 1.2M), unfavourable; 8. BR-MMI-CWB-02 USD 1.1M (P10-P90 USD 859k - USD 1.4M), USD 220k (16.6%) below budget (USD 1.3M), unfavourable; 9. CL-MMI-ANF-03 USD 1.5M (P10-P90 USD 1.0M - USD 2.4M), USD 160k (9.6%) below budget (USD 1.7M), unfavourable; 10. CA-ENV-CAL-01 USD 742k (P10-P90 USD 635k - USD 779k), USD 135k (15.4%) below budget (USD 877k), unfavourable.

- Rank 1: CA-ENV-VAN-01 USD 1.4M (P10-P90 USD 1.2M - USD 1.5M), USD 355k (20.4%) below budget (USD 1.7M), unfavourable
- Rank 2: PE-BNI-AQP-01 USD 1.3M (P10-P90 USD 1.0M - USD 1.7M), USD 338k (20.4%) below budget (USD 1.7M), unfavourable
- Rank 3: CA-ENV-CAL-02 USD 1.4M (P10-P90 USD 1.2M - USD 1.4M), USD 286k (17.3%) below budget (USD 1.7M), unfavourable
- Rank 4: CA-BNI-VAN-01 USD 2.4M (P10-P90 USD 2.2M - USD 2.5M), USD 283k (10.7%) below budget (USD 2.6M), unfavourable
- Rank 5: CA-ENV-MTL-01 USD 1.1M (P10-P90 USD 976k - USD 1.2M), USD 271k (19.4%) below budget (USD 1.4M), unfavourable

_WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data. Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time._

## Table

| BU | Landing (P50) | P10 | P90 | Budget | Gap vs budget | Gap % vs budget | FC3 | Gap vs FC3 | Billing pattern |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CA-ENV-VAN-01 | 1,391 | 1,226 | 1,462 | 1,746 | (355) | (20.4%) | 1,468 | (77) | Steady |
| PE-BNI-AQP-01 | 1,317 | 1,022 | 1,679 | 1,655 | (338) | (20.4%) | 1,387 | (70) | Lumpy (project billing) |
| CA-ENV-CAL-02 | 1,365 | 1,234 | 1,434 | 1,651 | (286) | (17.3%) | 1,318 | 47 | Seasonal (March peak, August dip) |
| CA-BNI-VAN-01 | 2,358 | 2,163 | 2,522 | 2,641 | (283) | (10.7%) | 2,454 | (96) | Steady |
| CA-ENV-MTL-01 | 1,124 | 976 | 1,172 | 1,395 | (271) | (19.4%) | 1,130 | (6) | Seasonal (March peak, August dip) |
| CA-ENV-TOR-01 | 983 | 843 | 1,043 | 1,236 | (254) | (20.5%) | 1,031 | (49) | Steady |
| CA-BNI-TOR-01 | 947 | 693 | 1,826 | 1,183 | (235) | (19.9%) | 988 | (41) | Lumpy (project billing) |
| BR-MMI-CWB-02 | 1,103 | 859 | 1,356 | 1,323 | (220) | (16.6%) | 1,173 | (70) | Lumpy (project billing) |
| CL-MMI-ANF-03 | 1,500 | 1,033 | 2,398 | 1,659 | (160) | (9.6%) | 1,502 | (3) | Lumpy (project billing) |
| CA-ENV-CAL-01 | 742 | 635 | 779 | 877 | (135) | (15.4%) | 744 | (2) | Seasonal (March peak, August dip) |

_USD k · Billing landing for Nov 2026 (P50 with P10-P90) vs budget and FC3. WIP is 0 in the landing month, so the revenue landing equals the billing landing._

## Chart

`hbar` - Billing landing vs budget, Nov 2026 - RL Group ([interactive chart](24_which_bus_are_expected_to_miss_budget_this_month_chart.html))

## Filters, version and period used

- Scope: RL Group
- Period: Nov 2026 (landing) (Nov 2026)
- Versions: Landing (P50, P10-P90)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)
- Note: WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data.
- Note: Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time.

## Follow-up questions

1. Explain the landing for CA-ENV-VAN-01
2. What's the Nov landing for CA-ENV-VAN-01?
3. Revenue YTD till Nov with landing vs budget for RL Group

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "rank_landing",
      "arguments": {
        "metric": "billing",
        "org_level": "l6_bu",
        "parent_filter": "",
        "top_n": 10,
        "sort_by": "gap_vs_budget"
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
    "preprocess": 0.011,
    "plan": 0.0,
    "act": 2.6,
    "write#1": 0.0
  }
}
```
