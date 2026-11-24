# What is the utilization rate in Mexico vs budget?

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 13.7 s
- **Tool:** `get_ratio` (chosen by `llm_text`) · **numeric guardrail:** passed

## Answer

The utilization rate in Mexico for YTD Oct 2026 is 82.0%, which is 0.7 pp below the budget of 82.7%, unfavourable. This underperformance is driven by a lower billable hours compared to available hours.

- Components (Actual): Billable hours 1,830,727.4; Available hours 2,233,043.5
- Actual is 0.7 pp below Budget (YTD Oct 2026) (82.7%), unfavourable

## Table

| Version | Period | Billable hours | Available hours | Utilization rate (billable / available hours) | Actual vs version |
|:---|---:|---:|---:|---:|---:|
| Actual | YTD Oct 2026 | 1,830,727 | 2,233,044 | 82.0% |  |
| Budget | YTD Oct 2026 | 1,857,611 | 2,247,542 | 82.7% | (0.7 pp) |

## Chart

`bar` - Utilization rate (billable / available hours) - Mexico ([interactive chart](11_what_is_the_utilization_rate_in_mexico_vs_budget_chart.html))

## Filters, version and period used

- Scope: Mexico
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), Budget (Budget, YTD Oct 2026)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

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
        "period": "YTD",
        "comparison": "Budget"
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 6.77,
      "usage": {
        "prompt_tokens": 2717,
        "completion_tokens": 50
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 6.79,
      "usage": {
        "prompt_tokens": 489,
        "completion_tokens": 59
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
        "checked": 3
      }
    ],
    "unsupported": []
  },
  "errors": [],
  "timings": {
    "preprocess": 0.006,
    "plan": 6.773,
    "act": 0.13,
    "write#1": 6.786
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
