# What happened to WIP in Mexico Buildings & Infrastructure this year?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.13 s
- **Tool:** `get_trend` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**WIP & deferred income monthly trend for Mexico · Buildings & Infrastructure, Jan 2026 - Oct 2026 (series: Actual, PY, Budget), USD.**

- Pattern of Actual: Jan 2026 - Jun 2026 total +USD 861k (positive every month); Jul 2026 - Oct 2026 total -USD 823k (negative every month)
- Total Actual over Jan 2026 - Oct 2026: USD 39k; USD 155k below PY for the same months (USD 194k), unfavourable; USD 146k below Budget for the same months (USD 185k), unfavourable
- Latest month Oct 2026: Actual -USD 6k, PY -USD 2k, Budget -USD 6k

## Table

| Month | Actual | PY | Budget |
|:---|---:|---:|---:|
| Jan 2026 | 84 | (4) | (13) |
| Feb 2026 | 161 | 27 | 32 |
| Mar 2026 | 186 | 34 | 32 |
| Apr 2026 | 120 | 24 | 28 |
| May 2026 | 139 | 26 | 22 |
| Jun 2026 | 171 | 27 | 25 |
| Jul 2026 | (276) | 23 | 22 |
| Aug 2026 | (285) | 23 | 27 |
| Sep 2026 | (256) | 16 | 17 |
| Oct 2026 | (6) | (2) | (6) |

_USD k_

## Chart

`line` - WIP & deferred income - Mexico · Buildings & Infrastructure (Jan 2026 - Oct 2026) ([interactive chart](08_what_happened_to_wip_in_mexico_buildings_infrast_chart.html))

## Filters, version and period used

- Scope: Mexico · Buildings & Infrastructure
- Period: Jan 2026 - Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual, PY, Budget
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why did WIP & deferred income change vs last year for Mexico · Buildings & Infrastructure?
2. Rank businesses in Mexico · Buildings & Infrastructure by WIP & deferred income this year
3. Compare Budget vs FC3 vs Actual for Mexico · Buildings & Infrastructure

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_trend",
      "arguments": {
        "metric_or_ratio": "wip_ui",
        "org": "Mexico \u00b7 Buildings & Infrastructure",
        "start": "2026-01",
        "end": "",
        "versions": [
          "Actual",
          "PY",
          "Budget"
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
    "preprocess": 0.009,
    "plan": 0.0,
    "act": 0.116,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.month_key, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Mexico') AND dim_org.l4_product_line IN (N'Buildings & Infrastructure') GROUP BY fact_pnl.month_key, fact_pnl.account_id
```

```sql
SELECT fact_pnl.month_key, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Mexico') AND dim_org.l4_product_line IN (N'Buildings & Infrastructure') GROUP BY fact_pnl.month_key, fact_pnl.account_id
```

```sql
SELECT fact_pnl.month_key, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Mexico') AND dim_org.l4_product_line IN (N'Buildings & Infrastructure') GROUP BY fact_pnl.month_key, fact_pnl.account_id
```
