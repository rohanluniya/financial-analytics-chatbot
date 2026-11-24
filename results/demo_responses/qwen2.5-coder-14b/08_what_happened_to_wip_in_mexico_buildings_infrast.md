# What happened to WIP in Mexico Buildings & Infrastructure this year?

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 24.44 s
- **Tool:** `get_trend` (chosen by `llm_text`) · **numeric guardrail:** passed

## Answer

USD 108k, USD 556k below PY (USD 663k), unfavourable; USD 617k below Budget (USD 725k), unfavourable. The decline in WIP is driven by a significant negative trend from July to October 2026, where every month shows a decrease, contrasting with the positive trend from January to June 2026.

- Pattern of Actual: Jan 2026 - Jun 2026 total +USD 3.4M (positive every month); Jul 2026 - Oct 2026 total -USD 3.3M (negative every month)
- Total Actual over Jan 2026 - Oct 2026: USD 108k; USD 556k below PY for the same months (USD 663k), unfavourable; USD 617k below Budget for the same months (USD 725k), unfavourable
- Latest month Oct 2026: Actual -USD 26k, PY -USD 34k, Budget -USD 25k

## Table

| Month | Actual | PY | Budget |
|:---|---:|---:|---:|
| Jan 2026 | 329 | (41) | (54) |
| Feb 2026 | 584 | 100 | 137 |
| Mar 2026 | 645 | 110 | 111 |
| Apr 2026 | 591 | 130 | 118 |
| May 2026 | 607 | 94 | 100 |
| Jun 2026 | 617 | 54 | 82 |
| Jul 2026 | (1,091) | 90 | 92 |
| Aug 2026 | (1,129) | 97 | 106 |
| Sep 2026 | (1,021) | 61 | 57 |
| Oct 2026 | (26) | (34) | (25) |

_USD k_

## Chart

`line` - WIP & UI - Mexico · Buildings & Infrastructure (Jan 2026 - Oct 2026) ([interactive chart](08_what_happened_to_wip_in_mexico_buildings_infrast_chart.html))

## Filters, version and period used

- Scope: Mexico · Buildings & Infrastructure
- Period: Jan 2026 - Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual, PY, Budget
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why did WIP & UI change vs last year for Mexico · Buildings & Infrastructure?
2. Rank businesss in Mexico · Buildings & Infrastructure by WIP & UI this year
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
        "end": "2026-10",
        "versions": [
          "Actual",
          "PY",
          "Budget"
        ]
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 10.39,
      "usage": {
        "prompt_tokens": 2733,
        "completion_tokens": 85
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 13.93,
      "usage": {
        "prompt_tokens": 1030,
        "completion_tokens": 92
      }
    }
  ],
  "guardrail": {
    "ok": true,
    "template": false,
    "history": [
      {
        "attempt": 1,
        "ok": true,
        "unsupported": [],
        "checked": 5
      }
    ],
    "unsupported": []
  },
  "errors": [],
  "timings": {
    "preprocess": 0.006,
    "plan": 10.393,
    "act": 0.101,
    "write#1": 13.935
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
