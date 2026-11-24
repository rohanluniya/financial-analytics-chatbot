# What is the utilization rate in Mexico vs budget?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.16 s
- **Tool:** `get_ratio` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Utilization rate (billable / available hours) for Mexico, YTD Oct 2026 (Actual): 74.7%.**

- Components (Actual): Billable hours 1,449,116.8; Available hours 1,940,360.6
- Actual is 0.9 pp below Budget (YTD Oct 2026) (75.6%), unfavourable

## Table

| Version | Period | Billable hours | Available hours | Utilization rate (billable / available hours) | Actual vs version |
|:---|---:|---:|---:|---:|---:|
| Actual | YTD Oct 2026 | 1,449,117 | 1,940,361 | 74.7% |  |
| Budget | YTD Oct 2026 | 1,472,989 | 1,948,966 | 75.6% | (0.9 pp) |

## Chart

`bar` - Utilization rate (billable / available hours) - Mexico ([interactive chart](11_what_is_the_utilization_rate_in_mexico_vs_budget_chart.html))

## Filters, version and period used

- Scope: Mexico
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), Budget (Budget, YTD Oct 2026)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show the Utilization rate (billable / available hours) trend for Mexico since 2024
2. Rank product lines in Mexico by Utilization rate (billable / available hours) this year
3. What drives the change in Utilization rate (billable / available hours) vs last year for Mexico?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_ratio",
      "arguments": {
        "ratio_name": "utilization_rate",
        "org": "Mexico",
        "period": "",
        "comparison": "Budget"
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
    "preprocess": 0.008,
    "plan": 0.0,
    "act": 0.147,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Mexico') GROUP BY fact_pnl.account_id
```

```sql
SELECT sum(fact_stats.fte) AS fte_sum, sum(fact_stats.headcount) AS headcount_sum, sum(fact_stats.direct_fte) AS direct_fte_sum, sum(fact_stats.billable_hours) AS billable_hours_sum, sum(fact_stats.available_hours) AS available_hours_sum, sum(fact_stats.overtime_hours) AS overtime_hours_sum, count(DISTINCT fact_stats.month_key) AS n_months 
FROM fact_stats JOIN dim_org ON fact_stats.bu_id = dim_org.bu_id JOIN dim_version ON fact_stats.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_stats.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Mexico')
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Mexico') GROUP BY fact_pnl.account_id
```

_1 more SQL statements in the JSON file._
