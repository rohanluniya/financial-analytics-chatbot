# Why did Canada Environmental Lab Testing margin drop in 2026?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.18 s
- **Tool:** `variance_drivers` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Operating margin on revenue for Canada · Environmental Lab Testing, YTD Oct 2026: Actual 2.5%, 9.6 pp below PY (12.1%), unfavourable.**

Account drivers (largest first): Personnel costs as % of revenue: 51.2% vs 46.5%, impact on Operating margin on revenue -4.7 pp (unfavourable); Other costs as % of revenue: 33.4% vs 30.2%, impact on Operating margin on revenue -3.1 pp (unfavourable); Functional costs as % of revenue: 13.0% vs 10.6%, impact on Operating margin on revenue -2.4 pp (unfavourable); Functional cost recharges as % of revenue: 3.1% vs 2.5%, impact on Operating margin on revenue +0.6 pp (favourable); External subcontracting as % of revenue: 3.9% vs 4.0%, impact on Operating margin on revenue +0.1 pp (favourable).

- Business with the largest change: Env Lab Calgary 1.3% vs 12.1% (-10.8 pp, unfavourable)

## Table

| Driver | PY | Actual | Impact | Share of variance |
|:---|---:|---:|---:|---:|
| Personnel costs as % of revenue | 46.5% | 51.2% | (4.7 pp) | 48.8% |
| Other costs as % of revenue | 30.2% | 33.4% | (3.1 pp) | 32.5% |
| Functional costs as % of revenue | 10.6% | 13.0% | (2.4 pp) | 25.3% |
| Functional cost recharges as % of revenue | 2.5% | 3.1% | 0.6 pp | (6.2%) |
| External subcontracting as % of revenue | 4.0% | 3.9% | 0.1 pp | (0.5%) |
| Production as % of revenue | 100.9% | 100.8% | 0.0 pp | 0.2% |

_Impact = contribution to the change in Operating margin on revenue (percentage points)_

**By business**

| Business | PY | Actual | Impact |
|:---|---:|---:|---:|
| Env Lab Calgary | 12.1% | 1.3% | (10.8 pp) |
| Env Lab Montreal | 12.9% | 2.6% | (10.3 pp) |
| Env Lab Toronto | 11.6% | 3.2% | (8.4 pp) |
| Env Lab Vancouver | 11.8% | 3.5% | (8.3 pp) |

## Chart

`waterfall` - Operating margin on revenue: PY to Actual - Canada · Environmental Lab Testing (YTD Oct 2026) ([interactive chart](04_why_did_canada_environmental_lab_testing_margin_chart.html))

## Filters, version and period used

- Scope: Canada · Environmental Lab Testing
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show the monthly trend of Operating margin on revenue for Canada · Environmental Lab Testing since 2025
2. Show the Personnel costs trend for Canada · Environmental Lab Testing vs budget
3. Compare Budget vs FC3 vs Actual for Canada · Environmental Lab Testing

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "variance_drivers",
      "arguments": {
        "metric": "maop_margin_revenue",
        "org": "Canada \u00b7 Environmental Lab Testing",
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
    "preprocess": 0.011,
    "plan": 0.0,
    "act": 0.157,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_pnl.account_id
```

```sql
SELECT dim_org.l5_business, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_org.l5_business, fact_pnl.account_id
```

_1 more SQL statements in the JSON file._
