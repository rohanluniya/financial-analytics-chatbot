# Top 5 BUs by operating margin in US & Canada this year

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.09 s
- **Tool:** `rank_entities` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Ranking of BUs by Operating margin on revenue within US & Canada, YTD Oct 2026 (highest first); 31 BUs in scope, showing 5.**

- Rank 1: CA-BNI-TOR-01 30.2% (PY 30.9%, -0.7 pp)
- Rank 2: US-IND-NYC-03 26.6% (PY 19.7%, +6.9 pp)
- Rank 3: US-IND-NYC-02 23.0% (PY 19.6%, +3.4 pp)

## Table

| Rank | BU | Actual | PY | Var |
|:---|---:|---:|---:|---:|
| 1 | CA-BNI-TOR-01 | 30.2% | 30.9% | (0.7 pp) |
| 2 | US-IND-NYC-03 | 26.6% | 19.7% | 6.9 pp |
| 3 | US-IND-NYC-02 | 23.0% | 19.6% | 3.4 pp |
| 4 | US-CER-HOU-01 | 23.0% | 23.6% | (0.6 pp) |
| 5 | US-IND-NYC-01 | 21.6% | 16.6% | 5.0 pp |

## Chart

`hbar` - Operating margin on revenue by BU - US & Canada (YTD Oct 2026) ([interactive chart](05_top_5_bus_by_operating_margin_in_us_canada_this_chart.html))

## Filters, version and period used

- Scope: US & Canada
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is CA-BNI-TOR-01 where it is on Operating margin on revenue?
2. Show the Operating margin on revenue trend for CA-BNI-TOR-01 since 2025
3. Show the bottom 5 BUs by Operating margin on revenue in US & Canada instead

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
    "act": 0.082,
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
