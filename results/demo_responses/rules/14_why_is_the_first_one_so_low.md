# why is the first one so low?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.15 s
- **Tool:** `variance_drivers` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Operating margin on revenue for Paraguay, YTD Oct 2026: Actual 10.3%, 1.4 pp above PY (8.9%), favourable.**

Account drivers (largest first): Personnel costs as % of revenue: 50.8% vs 52.3%, impact on Operating margin on revenue +1.5 pp (favourable); External subcontracting as % of revenue: 19.3% vs 18.6%, impact on Operating margin on revenue -0.6 pp (unfavourable); Functional costs as % of revenue: 10.4% vs 10.8%, impact on Operating margin on revenue +0.4 pp (favourable); Other costs as % of revenue: 11.1% vs 11.3%, impact on Operating margin on revenue +0.2 pp (favourable); Functional cost recharges as % of revenue: 2.4% vs 2.5%, impact on Operating margin on revenue -0.1 pp (unfavourable).

- Product line with the largest change: Buildings & Infrastructure 8.3% vs 6.8% (+1.5 pp, favourable)

## Table

| Driver | PY | Actual | Impact | Share of variance |
|:---|---:|---:|---:|---:|
| Personnel costs as % of revenue | 52.3% | 50.8% | 1.5 pp | 107.9% |
| External subcontracting as % of revenue | 18.6% | 19.3% | (0.6 pp) | (46.4%) |
| Functional costs as % of revenue | 10.8% | 10.4% | 0.4 pp | 26.2% |
| Other costs as % of revenue | 11.3% | 11.1% | 0.2 pp | 15.4% |
| Functional cost recharges as % of revenue | 2.5% | 2.4% | (0.1 pp) | (6.4%) |
| Production as % of revenue | 99.3% | 99.4% | 0.0 pp | 3.4% |

_Impact = contribution to the change in Operating margin on revenue (percentage points)_

**By product line**

| Product line | PY | Actual | Impact |
|:---|---:|---:|---:|
| Buildings & Infrastructure | 6.8% | 8.3% | 1.5 pp |
| Certification & Sustainability | 25.8% | 26.1% | 0.4 pp |

## Chart

`waterfall` - Operating margin on revenue: PY to Actual - Paraguay (YTD Oct 2026) ([interactive chart](14_why_is_the_first_one_so_low_chart.html))

## Filters, version and period used

- Scope: Paraguay
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show the monthly trend of Operating margin on revenue for Paraguay since 2025
2. Show the Personnel costs trend for Paraguay vs budget
3. Compare Budget vs FC3 vs Actual for Paraguay

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "variance_drivers",
      "arguments": {
        "metric": "maop_margin_revenue",
        "org": "Paraguay",
        "period": "YTD Oct 2026",
        "comparison": "PY",
        "depth": 1
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
    "preprocess": 0.007,
    "plan": 0.0,
    "act": 0.138,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Paraguay') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Paraguay') GROUP BY fact_pnl.account_id
```

```sql
SELECT dim_org.l4_product_line, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Paraguay') GROUP BY dim_org.l4_product_line, fact_pnl.account_id
```

_1 more SQL statements in the JSON file._
