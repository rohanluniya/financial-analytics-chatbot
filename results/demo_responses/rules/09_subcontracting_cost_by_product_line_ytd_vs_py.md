# Subcontracting cost by product line YTD vs PY

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.33 s
- **Tool:** `rank_entities` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Ranking of Product lines by External subcontracting within RL Group, YTD Oct 2026 (highest first); 8 Product lines in scope, showing 8.**

- Rank 1: Industry & Energy USD 40.5M (PY USD 38.2M, +USD 2.4M, +6.2%)
- Rank 2: Buildings & Infrastructure USD 34.2M (PY USD 31.5M, +USD 2.7M, +8.5%)
- Rank 3: Power & Utilities USD 11.4M (PY USD 10.8M, +USD 580k, +5.4%)

## Table

| Rank | Product line | Actual | PY | Var | Var % |
|:---|---:|---:|---:|---:|---:|
| 1 | Industry & Energy | 40,546 | 38,189 | 2,357 | 6.2% |
| 2 | Buildings & Infrastructure | 34,215 | 31,526 | 2,689 | 8.5% |
| 3 | Power & Utilities | 11,352 | 10,771 | 580 | 5.4% |
| 4 | Metals & Minerals | 6,859 | 5,862 | 997 | 17.0% |
| 5 | Certification & Sustainability | 6,693 | 6,279 | 414 | 6.6% |
| 6 | Elevators & Pressure Vessels | 6,374 | 6,080 | 294 | 4.8% |
| 7 | Environmental Lab Testing | 2,288 | 2,653 | (364) | (13.7%) |
| 8 | Consumer Products | 1,843 | 1,765 | 78 | 4.4% |

_USD k_

## Chart

`hbar` - External subcontracting by Product line - RL Group (YTD Oct 2026) ([interactive chart](09_subcontracting_cost_by_product_line_ytd_vs_py_chart.html))

## Filters, version and period used

- Scope: RL Group
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is Industry & Energy where it is on External subcontracting?
2. Show the External subcontracting trend for Industry & Energy since 2025
3. Show the bottom 5 Product lines by External subcontracting in RL Group instead

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "rank_entities",
      "arguments": {
        "metric_or_ratio": "subcontracting",
        "org_level": "l4_product_line",
        "parent_filter": "",
        "period": "YTD Oct 2026",
        "top_n": 0,
        "ascending": false
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
    "act": 0.315,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_org.l4_product_line, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 GROUP BY dim_org.l4_product_line, fact_pnl.account_id
```

```sql
SELECT dim_org.l4_product_line, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 GROUP BY dim_org.l4_product_line, fact_pnl.account_id
```
