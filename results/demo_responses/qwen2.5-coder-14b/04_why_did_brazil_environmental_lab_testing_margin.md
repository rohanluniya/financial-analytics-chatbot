# Why did Brazil Environmental Lab Testing margin drop in 2026?

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 27.8 s
- **Tool:** `variance_drivers` (chosen by `llm_text`) · **numeric guardrail:** passed

## Answer

The MAOP margin for Brazil Environmental Lab Testing, YTD Oct 2026, was 2.6%, 9.8 pp below the prior year (12.5%), which is unfavourable. The margin decline was driven by higher personnel charges as a percentage of revenue (50.5% vs 45.9%, -4.6 pp), higher other costs as a percentage of revenue (33.1% vs 29.7%, -3.4 pp), and higher total functional costs as a percentage of revenue (12.9% vs 10.5%, -2.4 pp). Each business unit also experienced significant margin declines: Env Lab Sao Paulo, Env Lab Curitiba, and Env Lab Belo Horizonte all saw margins fall by more than 9 percentage points.

- MAOP margin (on revenue) for Brazil · Environmental Lab Testing, YTD Oct 2026: Actual 2.6%, 9.8 pp below PY (12.5%), unfavourable
- Personnel charges as % of revenue: 50.5% vs 45.9%, impact on MAOP margin (on revenue) -4.6 pp (unfavourable)
- Other costs as % of revenue: 33.1% vs 29.7%, impact on MAOP margin (on revenue) -3.4 pp (unfavourable)
- Total functional costs as % of revenue: 12.9% vs 10.5%, impact on MAOP margin (on revenue) -2.4 pp (unfavourable)
- Business with the largest change: Env Lab Sao Paulo 1.8% vs 12.3% (-10.5 pp, unfavourable)

## Table

| Driver | PY | Actual | Impact | Share of variance |
|:---|---:|---:|---:|---:|
| Personnel charges as % of revenue | 45.9% | 50.5% | (4.6 pp) | 47.1% |
| Other costs as % of revenue | 29.7% | 33.1% | (3.4 pp) | 34.7% |
| Total functional costs as % of revenue | 10.5% | 12.9% | (2.4 pp) | 24.2% |
| Functional neutralization as % of revenue | 2.5% | 3.0% | 0.5 pp | (5.6%) |
| External subcontracting as % of revenue | 3.9% | 3.9% | 0.0 pp | (0.4%) |
| Production as % of revenue | 99.9% | 99.9% | 0.0 pp | 0.0% |

_Impact = contribution to the change in MAOP margin (on revenue) (percentage points)_

**By business**

| Business | PY | Actual | Impact |
|:---|---:|---:|---:|
| Env Lab Sao Paulo | 12.3% | 1.8% | (10.5 pp) |
| Env Lab Curitiba | 13.9% | 4.6% | (9.3 pp) |
| Env Lab Belo Horizonte | 11.9% | 2.6% | (9.2 pp) |

## Chart

`waterfall` - MAOP margin (on revenue): PY to Actual - Brazil · Environmental Lab Testing (YTD Oct 2026) ([interactive chart](04_why_did_brazil_environmental_lab_testing_margin_chart.html))

## Filters, version and period used

- Scope: Brazil · Environmental Lab Testing
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show the monthly trend of MAOP margin (on revenue) for Brazil · Environmental Lab Testing since 2025
2. Show the Personnel charges trend for Brazil · Environmental Lab Testing vs budget
3. Compare Budget vs FC3 vs Actual for Brazil · Environmental Lab Testing

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "variance_drivers",
      "arguments": {
        "metric": "maop_margin_revenue",
        "org": "Brazil Environmental Lab Testing",
        "period": "YTD Oct 2026",
        "comparison": "PY"
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 8.04,
      "usage": {
        "prompt_tokens": 2736,
        "completion_tokens": 62
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 19.61,
      "usage": {
        "prompt_tokens": 702,
        "completion_tokens": 176
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
        "checked": 13
      }
    ],
    "unsupported": []
  },
  "errors": [],
  "timings": {
    "preprocess": 0.006,
    "plan": 8.043,
    "act": 0.132,
    "write#1": 19.611
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Brazil') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Brazil') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_pnl.account_id
```

```sql
SELECT dim_org.l5_business, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Brazil') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_org.l5_business, fact_pnl.account_id
```

_1 more SQL statements in the JSON file._
