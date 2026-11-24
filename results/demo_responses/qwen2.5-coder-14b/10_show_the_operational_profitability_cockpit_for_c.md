# Show the operational profitability cockpit for Canada

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 33.99 s
- **Tool:** `get_kpi_cockpit` (chosen by `llm_text`) · **numeric guardrail:** passed after removing unsupported sentences

## Answer

Direct margin for Canada is 65.0% MTD, 0.6 pp below PY (65.6%), unfavourable, and 0.5 pp below Budget (65.5%), unfavourable.

- Direct margin: MTD 65.0% (0.6 pp below LY, unfavourable; 0.5 pp below Budget, unfavourable); YTD 62.7% (0.0 pp above LY, favourable; 0.2 pp below Budget, unfavourable)
- Utilization rate (billable / available hours): MTD 81.7% (1.3 pp below LY, unfavourable; 1.2 pp below Budget, unfavourable); YTD 82.6% (0.2 pp below LY, unfavourable; 0.3 pp below Budget, unfavourable)
- Production per FTE (annualised): MTD USD 217k (1.0% above LY, favourable; 1.6% below Budget, unfavourable); YTD USD 201k (2.9% above LY, favourable; 1.6% below Budget, unfavourable)
- Overtime ratio (overtime / available hours): MTD 11.7% (0.5 pp below LY, favourable; 0.5 pp below Budget, favourable); YTD 10.0% (0.1 pp below LY, favourable; 0.2 pp below Budget, favourable)

## Table

| KPI | MTD | MTD vs LY | MTD vs Budget | YTD | YTD vs LY | YTD vs Budget |
|:---|---:|---:|---:|---:|---:|---:|
| Direct margin | 65.0% | (0.6 pp) | (0.5 pp) | 62.7% | 0.0 pp | (0.2 pp) |
| Production | 19,359 | 2.7% | (2.1%) | 178,288 | 4.7% | (2.8%) |
| Direct labor cost (7A) | 6,785 | 4.4% | (0.7%) | 66,541 | 4.7% | (2.3%) |
| Utilization rate (billable / available hours) | 81.7% | (1.3 pp) | (1.2 pp) | 82.6% | (0.2 pp) | (0.3 pp) |
| Production per billable hour | 189.7 | 2.4% | (0.4%) | 180.2 | 3.0% | (1.4%) |
| Production per FTE (annualised) | 217,280 | 1.0% | (1.6%) | 201,480 | 2.9% | (1.6%) |
| Overtime ratio (overtime / available hours) | 11.7% | (0.5 pp) | (0.5 pp) | 10.0% | (0.1 pp) | (0.2 pp) |
| Production hourly cost (direct labor per billable hour) | 66.5 | 4.1% | 1.0% | 67.3 | 3.0% | (0.8%) |
| Direct labor cost / Production | 35.0% | 0.6 pp | 0.5 pp | 37.3% | 0.0 pp | 0.2 pp |
| Gross margin | 28.6% | (0.8 pp) | (1.0 pp) | 25.2% | 0.0 pp | (0.4 pp) |
| MAOP margin (on revenue) | 18.8% | (1.0 pp) | (1.2 pp) | 14.7% | 0.0 pp | (0.5 pp) |

_USD k · MTD = month to date, YTD = year to date. Amount variances in %, ratio variances in percentage points; green = favourable._

## Chart

`combo` - Direct margin by month - Canada (Actual bars, LY and Budget lines) ([interactive chart](10_show_the_operational_profitability_cockpit_for_c_chart.html))

## Filters, version and period used

- Scope: Canada
- Period: MTD Oct 2026 and YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual, PY (LY), Budget
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why did direct margin change vs last year for Canada?
2. Show the utilization rate trend for Canada since 2025
3. Rank product lines in Canada by direct margin this year

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_kpi_cockpit",
      "arguments": {
        "org": "Canada"
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 4.32,
      "usage": {
        "prompt_tokens": 2714,
        "completion_tokens": 29
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 17.33,
      "usage": {
        "prompt_tokens": 1203,
        "completion_tokens": 113
      }
    },
    {
      "step": "write#2",
      "latency": 11.94,
      "usage": {
        "prompt_tokens": 1371,
        "completion_tokens": 113
      }
    }
  ],
  "guardrail": {
    "ok": true,
    "template": false,
    "redacted": true,
    "history": [
      {
        "attempt": 1,
        "ok": false,
        "unsupported": [
          "6.5M",
          "6.9M"
        ],
        "checked": 10,
        "draft": "Direct margin for Canada is 65.0% MTD, 0.6 pp below PY (65.6%), unfavourable, and 0.5 pp below Budget (65.5%), unfavourable. This is driven by a 4.4% higher direct labor cost MTD (USD 6.8M) compared to PY (USD 6.5M), unfavourable, and a 0.7% lower direct labor cost compared to Budget (USD 6.9M), favourable."
      },
      {
        "attempt": 2,
        "ok": false,
        "unsupported": [
          "6.5M",
          "6.9M"
        ],
        "checked": 10,
        "draft": "Direct margin for Canada is 65.0% MTD, 0.6 pp below PY (65.6%), unfavourable, and 0.5 pp below Budget (65.5%), unfavourable. This is driven by a 4.4% higher direct labor cost MTD (USD 6.8M) compared to PY (USD 6.5M), unfavourable, and a 0.7% lower direct labor cost compared to Budget (USD 6.9M), favourable."
      }
    ],
    "unsupported": [
      "6.5M",
      "6.9M"
    ]
  },
  "errors": [],
  "timings": {
    "preprocess": 0.005,
    "plan": 4.321,
    "act": 0.373,
    "write#1": 17.333,
    "write#2": 11.944
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202610 AND 202610 AND dim_org.l3_country IN (N'Canada') GROUP BY fact_pnl.account_id
```

```sql
SELECT sum(fact_stats.fte) AS fte_sum, sum(fact_stats.headcount) AS headcount_sum, sum(fact_stats.direct_fte) AS direct_fte_sum, sum(fact_stats.billable_hours) AS billable_hours_sum, sum(fact_stats.available_hours) AS available_hours_sum, sum(fact_stats.overtime_hours) AS overtime_hours_sum, count(DISTINCT fact_stats.month_key) AS n_months 
FROM fact_stats JOIN dim_org ON fact_stats.bu_id = dim_org.bu_id JOIN dim_version ON fact_stats.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_stats.month_key BETWEEN 202610 AND 202610 AND dim_org.l3_country IN (N'Canada')
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202510 AND 202510 AND dim_org.l3_country IN (N'Canada') GROUP BY fact_pnl.account_id
```

_12 more SQL statements in the JSON file._
