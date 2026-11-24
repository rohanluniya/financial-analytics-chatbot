# Show personnel cost as % of revenue trend for Environmental Lab Testing since 2023

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.13 s
- **Tool:** `get_trend` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Personnel costs / Revenue monthly trend for Environmental Lab Testing, Jan 2023 - Oct 2026 (series: Actual, Actual R12M, Budget), USD.**

- Actual by calendar year: 2023 46.6% (full year), 2024 46.7% (full year), 2025 46.5% (full year), 2026 50.8% (Jan-Oct)
- Latest month Oct 2026: Actual 47.2%, Budget 44.6%
- Rolling 12-month Personnel costs / Revenue: Jan 2023 46.3% -> Oct 2026 49.9% (up 3.6 pp)

## Table

| Month | Actual | Actual R12M | Budget |
|:---|---:|---:|---:|
| Jan 2023 | 47.8% | 46.3% | 47.5% |
| Feb 2023 | 44.5% | 46.4% | 44.7% |
| Mar 2023 | 40.7% | 46.5% | 38.5% |
| Apr 2023 | 49.1% | 46.7% | 48.5% |
| May 2023 | 45.2% | 46.5% | 44.2% |
| Jun 2023 | 46.1% | 46.8% | 44.4% |
| Jul 2023 | 49.0% | 46.6% | 49.7% |
| Aug 2023 | 57.4% | 46.5% | 59.0% |
| Sep 2023 | 45.6% | 46.6% | 46.1% |
| Oct 2023 | 44.9% | 46.5% | 44.6% |
| Nov 2023 | 42.9% | 46.5% | 44.0% |
| Dec 2023 | 50.8% | 46.6% | 49.8% |
| Jan 2024 | 45.5% | 46.4% | 46.2% |
| Feb 2024 | 43.9% | 46.4% | 43.4% |
| Mar 2024 | 43.5% | 46.7% | 42.4% |
| Apr 2024 | 44.6% | 46.3% | 44.3% |
| May 2024 | 44.3% | 46.2% | 44.4% |
| Jun 2024 | 47.4% | 46.3% | 47.6% |
| Jul 2024 | 48.3% | 46.3% | 48.3% |
| Aug 2024 | 60.3% | 46.5% | 61.0% |
| Sep 2024 | 47.0% | 46.6% | 46.3% |
| Oct 2024 | 43.9% | 46.5% | 43.5% |
| Nov 2024 | 46.3% | 46.8% | 45.6% |
| Dec 2024 | 49.2% | 46.7% | 48.4% |
| Jan 2025 | 46.4% | 46.7% | 46.2% |
| Feb 2025 | 44.9% | 46.8% | 44.9% |
| Mar 2025 | 43.6% | 46.8% | 41.1% |
| Apr 2025 | 46.6% | 47.0% | 45.5% |
| May 2025 | 44.8% | 47.0% | 45.7% |
| Jun 2025 | 46.5% | 46.9% | 46.0% |
| Jul 2025 | 48.3% | 46.9% | 48.2% |
| Aug 2025 | 61.8% | 47.0% | 62.9% |
| Sep 2025 | 44.9% | 46.9% | 44.8% |
| Oct 2025 | 42.9% | 46.8% | 43.4% |
| Nov 2025 | 45.5% | 46.7% | 47.1% |
| Dec 2025 | 46.9% | 46.5% | 46.9% |
| Jan 2026 | 48.9% | 46.7% | 47.6% |
| Feb 2026 | 52.8% | 47.3% | 44.8% |
| Mar 2026 | 51.8% | 48.1% | 39.8% |
| Apr 2026 | 53.6% | 48.6% | 45.4% |
| May 2026 | 49.2% | 49.0% | 47.0% |
| Jun 2026 | 46.8% | 49.0% | 44.5% |
| Jul 2026 | 51.6% | 49.3% | 48.1% |
| Aug 2026 | 64.3% | 49.3% | 62.7% |
| Sep 2026 | 46.0% | 49.5% | 44.7% |
| Oct 2026 | 47.2% | 49.9% | 44.6% |

## Chart

`line` - Personnel costs / Revenue - Environmental Lab Testing (Jan 2023 - Oct 2026) ([interactive chart](03_show_personnel_cost_as_of_revenue_trend_for_envi_chart.html))

## Filters, version and period used

- Scope: Environmental Lab Testing
- Period: Jan 2023 - Oct 2026 (Jan 2023 - Oct 2026)
- Versions: Actual, Actual R12M, Budget
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why did Personnel costs / Revenue change vs last year for Environmental Lab Testing?
2. Rank countries in Environmental Lab Testing by Personnel costs / Revenue this year
3. Compare Budget vs FC3 vs Actual for Environmental Lab Testing

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_trend",
      "arguments": {
        "metric_or_ratio": "personnel_to_revenue",
        "org": "Environmental Lab Testing",
        "start": "2023-01",
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
    "preprocess": 0.005,
    "plan": 0.0,
    "act": 0.113,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.month_key, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202202 AND 202610 AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_pnl.month_key, fact_pnl.account_id
```

```sql
SELECT fact_pnl.month_key, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202301 AND 202610 AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_pnl.month_key, fact_pnl.account_id
```
