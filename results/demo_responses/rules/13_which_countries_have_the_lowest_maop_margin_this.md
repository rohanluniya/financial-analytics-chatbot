# Which countries have the lowest MAOP margin this year?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.35 s
- **Tool:** `rank_entities` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Ranking of Countrys by MAOP margin (on revenue) within RL Group, YTD Oct 2026 (lowest first); 11 Countrys in scope, showing 5.**

- Rank 1: Ecuador 9.4% (PY 11.1%, -1.7 pp)
- Rank 2: Peru 9.6% (PY 10.6%, -1.0 pp)
- Rank 3: Chile 10.7% (PY 10.5%, +0.2 pp)

## Table

| Rank | Country | Actual | PY | Var |
|:---|---:|---:|---:|---:|
| 1 | Ecuador | 9.4% | 11.1% | (1.7 pp) |
| 2 | Peru | 9.6% | 10.6% | (1.0 pp) |
| 3 | Chile | 10.7% | 10.5% | 0.2 pp |
| 4 | Colombia | 12.1% | 11.8% | 0.3 pp |
| 5 | Brazil | 12.3% | 13.3% | (1.0 pp) |

## Chart

`hbar` - MAOP margin (on revenue) by Country - RL Group (YTD Oct 2026) ([interactive chart](13_which_countries_have_the_lowest_maop_margin_this_chart.html))

## Filters, version and period used

- Scope: RL Group
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is Ecuador where it is on MAOP margin (on revenue)?
2. Show the MAOP margin (on revenue) trend for Ecuador since 2025
3. Show the top 5 Countrys by MAOP margin (on revenue) in RL Group instead

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
        "ascending": true
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
    "act": 0.33,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_org.l3_country, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 GROUP BY dim_org.l3_country, fact_pnl.account_id
```

```sql
SELECT dim_org.l3_country, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 GROUP BY dim_org.l3_country, fact_pnl.account_id
```
