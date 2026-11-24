# why is the first one so low?

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 24.39 s
- **Tool:** `variance_drivers` (chosen by `llm_text`) · **numeric guardrail:** passed

## Answer

The MAOP margin for Ecuador, YTD Oct 2026, is 9.4%, 1.7 pp below PY (11.1%), unfavourable. This decline is driven by higher direct labor costs (40.1% vs 39.4%, -0.7 pp), external subcontractors (13.1% vs 12.6%, -0.5 pp), and indirect personnel costs (10.9% vs 10.7%, -0.2 pp). The Buildings & Infrastructure product line also contributed to the margin decrease with a 2.5 pp decline.

- MAOP margin (on revenue) for Ecuador, YTD Oct 2026: Actual 9.4%, 1.7 pp below PY (11.1%), unfavourable
- Direct labor cost (7A) as % of revenue: 40.1% vs 39.4%, impact on MAOP margin (on revenue) -0.7 pp (unfavourable)
- 8.1 External subcontractors as % of revenue: 13.1% vs 12.6%, impact on MAOP margin (on revenue) -0.5 pp (unfavourable)
- Indirect personnel cost (7B) as % of revenue: 10.9% vs 10.7%, impact on MAOP margin (on revenue) -0.2 pp (unfavourable)
- Product line with the largest change: Buildings & Infrastructure 9.5% vs 12.0% (-2.5 pp, unfavourable)

## Table

| Driver | PY | Actual | Impact | Share of variance |
|:---|---:|---:|---:|---:|
| Direct labor cost (7A) as % of revenue | 39.4% | 40.1% | (0.7 pp) | 40.4% |
| 8.1 External subcontractors as % of revenue | 12.6% | 13.1% | (0.5 pp) | 29.9% |
| Indirect personnel cost (7B) as % of revenue | 10.7% | 10.9% | (0.2 pp) | 12.8% |
| 8.2 Temporary staff as % of revenue | 5.5% | 5.6% | (0.1 pp) | 6.2% |
| 12.1 Country functions as % of revenue | 4.4% | 4.5% | (0.1 pp) | 5.5% |
| 12.3 HQ allocation as % of revenue | 3.4% | 3.5% | (0.1 pp) | 4.9% |
| Functional neutralization as % of revenue | 2.4% | 2.5% | 0.1 pp | (4.8%) |
| Production as % of revenue | 99.2% | 99.3% | 0.1 pp | (3.9%) |
| 12.2 Region functions as % of revenue | 2.5% | 2.5% | (0.1 pp) | 3.5% |
| 9.4 Travel & living as % of revenue | 2.3% | 2.2% | 0.0 pp | (2.9%) |
| 9.3 Depreciation as % of revenue | 1.6% | 1.6% | 0.0 pp | 2.6% |
| 9.2 Rent & utilities as % of revenue | 1.4% | 1.4% | 0.0 pp | 1.9% |
| 9.6 IT & telecom as % of revenue | 1.0% | 1.0% | 0.0 pp | 1.6% |
| 9.9 Other as % of revenue | 0.6% | 0.7% | 0.0 pp | 1.0% |
| 9.8 Insurance as % of revenue | 0.5% | 0.5% | 0.0 pp | 0.7% |
| 9.5 Vehicles as % of revenue | 1.6% | 1.6% | 0.0 pp | 0.6% |
| 9.7 Lab consumables as % of revenue | 0.4% | 0.4% | 0.0 pp | 0.2% |
| 9.1 Contract expenses as % of revenue | 2.8% | 2.8% | 0.0 pp | (0.1%) |

_Impact = contribution to the change in MAOP margin (on revenue) (percentage points)_

**By product line**

| Product line | PY | Actual | Impact |
|:---|---:|---:|---:|
| Buildings & Infrastructure | 12.0% | 9.5% | (2.5 pp) |
| Industry & Energy | 8.5% | 9.1% | 0.6 pp |

## Chart

`waterfall` - MAOP margin (on revenue): PY to Actual - Ecuador (YTD Oct 2026) ([interactive chart](14_why_is_the_first_one_so_low_chart.html))

## Filters, version and period used

- Scope: Ecuador
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show the monthly trend of MAOP margin (on revenue) for Ecuador since 2025
2. Show the Direct labor cost (7A) trend for Ecuador vs budget
3. Compare Budget vs FC3 vs Actual for Ecuador

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "variance_drivers",
      "arguments": {
        "metric": "maop_margin_revenue",
        "org": "Ecuador",
        "period": "YTD Oct 2026",
        "comparison": "PY",
        "depth": 2
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 8.49,
      "usage": {
        "prompt_tokens": 2743,
        "completion_tokens": 67
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 15.77,
      "usage": {
        "prompt_tokens": 718,
        "completion_tokens": 134
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
    "preprocess": 0.005,
    "plan": 8.493,
    "act": 0.11,
    "write#1": 15.771
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Ecuador') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Ecuador') GROUP BY fact_pnl.account_id
```

```sql
SELECT dim_org.l4_product_line, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Ecuador') GROUP BY dim_org.l4_product_line, fact_pnl.account_id
```

_1 more SQL statements in the JSON file._
