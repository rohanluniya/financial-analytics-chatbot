# Rank countries by MAOP margin this year

- **Persona:** Environmental Lab Testing PL Leader
- **Model:** `rules` · **status:** ok · **latency:** 0.11 s
- **Tool:** `rank_entities` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Ranking of Countrys by MAOP margin (on revenue) within Environmental Lab Testing, YTD Oct 2026 (highest first); 7 Countrys in scope, showing 5.**

- Rank 1: United States 14.5% (PY 15.1%, -0.6 pp)
- Rank 2: Canada 12.4% (PY 13.1%, -0.7 pp)
- Rank 3: Argentina 11.6% (PY 12.1%, -0.6 pp)

## Table

| Rank | Country | Actual | PY | Var |
|:---|---:|---:|---:|---:|
| 1 | United States | 14.5% | 15.1% | (0.6 pp) |
| 2 | Canada | 12.4% | 13.1% | (0.7 pp) |
| 3 | Argentina | 11.6% | 12.1% | (0.6 pp) |
| 4 | Uruguay | 11.4% | 11.0% | 0.4 pp |
| 5 | Colombia | 11.4% | 10.7% | 0.6 pp |

## Chart

`hbar` - MAOP margin (on revenue) by Country - Environmental Lab Testing (YTD Oct 2026) ([interactive chart](17_rank_countries_by_maop_margin_this_year_chart.html))

## Filters, version and period used

- Scope: Environmental Lab Testing
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is United States where it is on MAOP margin (on revenue)?
2. Show the MAOP margin (on revenue) trend for United States since 2025
3. Show the bottom 5 Countrys by MAOP margin (on revenue) in Environmental Lab Testing instead

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "rank_entities",
      "arguments": {
        "metric_or_ratio": "maop_margin_revenue",
        "org_level": "l3_country",
        "parent_filter": "",
        "period": "YTD Oct 2026",
        "top_n": 5,
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
        "draft": ""
      }
    ],
    "unsupported": [
      "<empty>"
    ]
  },
  "errors": [],
  "timings": {
    "preprocess": 0.01,
    "plan": 0.0,
    "act": 0.094,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_org.l3_country, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_org.l3_country, fact_pnl.account_id
```

```sql
SELECT dim_org.l3_country, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_org.l3_country, fact_pnl.account_id
```
