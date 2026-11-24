# Show the operational profitability cockpit for Canada

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.48 s
- **Tool:** `get_kpi_cockpit` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**KPI cockpit for Canada: MTD = Oct 2026, YTD = Jan-Oct 2026; Actual vs LY (prior year) and vs Budget; USD at budget rate.**

- Direct margin: MTD 61.4% (3.0 pp below LY, unfavourable; 2.9 pp below Budget, unfavourable); YTD 61.5% (1.3 pp below LY, unfavourable; 2.5 pp below Budget, unfavourable)
- Utilization rate (billable / available hours): MTD 73.7% (4.5 pp below LY, unfavourable; 2.5 pp below Budget, unfavourable); YTD 73.3% (2.7 pp below LY, unfavourable; 2.9 pp below Budget, unfavourable)
- Production per FTE (annualised): MTD USD 199k (5.2% below LY, unfavourable; 7.6% below Budget, unfavourable); YTD USD 198k (0.7% below LY, unfavourable; 7.0% below Budget, unfavourable)
- Overtime ratio (overtime / available hours): MTD 7.0% (1.3 pp below LY, favourable; 0.9 pp below Budget, favourable); YTD 6.0% (0.6 pp below LY, favourable; 0.7 pp below Budget, favourable)

## Table

| KPI | MTD | MTD vs LY | MTD vs Budget | YTD | YTD vs LY | YTD vs Budget |
|:---|---:|---:|---:|---:|---:|---:|
| Direct margin | 61.4% | (3.0 pp) | (2.9 pp) | 61.5% | (1.3 pp) | (2.5 pp) |
| Production | 17,569 | (8.7%) | (13.2%) | 177,850 | (2.3%) | (11.3%) |
| Direct staff costs | 6,780 | (0.9%) | (6.1%) | 68,400 | 1.2% | (5.2%) |
| Utilization rate (billable / available hours) | 73.7% | (4.5 pp) | (2.5 pp) | 73.3% | (2.7 pp) | (2.9 pp) |
| Production per billable hour | 190.9 | 0.3% | (4.5%) | 198.1 | 2.8% | (3.3%) |
| Production per FTE (annualised) | 199,050 | (5.2%) | (7.6%) | 198,331 | (0.7%) | (7.0%) |
| Overtime ratio (overtime / available hours) | 7.0% | (1.3 pp) | (0.9 pp) | 6.0% | (0.6 pp) | (0.7 pp) |
| Production hourly cost (direct staff cost per billable hour) | 73.7 | 8.8% | 3.3% | 76.2 | 6.5% | 3.4% |
| Direct staff costs / Production | 38.6% | 3.0 pp | 2.9 pp | 38.5% | 1.3 pp | 2.5 pp |
| Gross margin | 22.8% | (4.7 pp) | (5.0 pp) | 23.1% | (2.2 pp) | (4.3 pp) |
| Operating margin on revenue | 11.6% | (6.2 pp) | (6.5 pp) | 12.1% | (3.0 pp) | (5.5 pp) |

_USD k · MTD = month to date, YTD = year to date. Amount variances in %, ratio variances in percentage points; green = favourable._

## Chart

`combo` - Direct margin by month - Canada (Actual bars, LY and Budget lines) ([interactive chart](10_show_the_operational_profitability_cockpit_for_c_chart.html))

## Filters, version and period used

- Scope: Canada
- Period: MTD Oct 2026 and YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual, PY (LY), Budget
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

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
        "org": "Canada",
        "month": ""
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
    "act": 0.471,
    "write#1": 0.0
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
