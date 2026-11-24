# Top 5 BUs by MAOP margin in US & Canada this year

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.1 s
- **Tool:** `rank_entities` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Ranking of BUs by MAOP margin (on revenue) within US & Canada, YTD Oct 2026 (highest first); 32 BUs in scope, showing 5.**

- Rank 1: US-CER-NYC-01 28.3% (PY 27.2%, +1.1 pp)
- Rank 2: CA-CER-MTL-01 27.5% (PY 26.5%, +1.0 pp)
- Rank 3: CA-CER-TOR-03 24.9% (PY 24.2%, +0.6 pp)

## Table

| Rank | BU | Actual | PY | Var |
|:---|---:|---:|---:|---:|
| 1 | US-CER-NYC-01 | 28.3% | 27.2% | 1.1 pp |
| 2 | CA-CER-MTL-01 | 27.5% | 26.5% | 1.0 pp |
| 3 | CA-CER-TOR-03 | 24.9% | 24.2% | 0.6 pp |
| 4 | CA-CER-TOR-01 | 24.5% | 24.8% | (0.3 pp) |
| 5 | CA-CER-CAL-01 | 24.3% | 23.7% | 0.5 pp |

## Chart

`hbar` - MAOP margin (on revenue) by BU - US & Canada (YTD Oct 2026) ([interactive chart](05_top_5_bus_by_maop_margin_in_us_canada_this_year_chart.html))

## Filters, version and period used

- Scope: US & Canada
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is US-CER-NYC-01 where it is on MAOP margin (on revenue)?
2. Show the MAOP margin (on revenue) trend for US-CER-NYC-01 since 2025
3. Show the bottom 5 BUs by MAOP margin (on revenue) in US & Canada instead

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "rank_entities",
      "arguments": {
        "metric_or_ratio": "maop_margin_revenue",
        "org_level": "l6_bu",
        "parent_filter": "US & Canada",
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
    "preprocess": 0.008,
    "plan": 0.0,
    "act": 0.086,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_org.l6_bu, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l2_region IN (N'US & Canada') GROUP BY dim_org.l6_bu, fact_pnl.account_id
```

```sql
SELECT dim_org.l6_bu, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l2_region IN (N'US & Canada') GROUP BY dim_org.l6_bu, fact_pnl.account_id
```
