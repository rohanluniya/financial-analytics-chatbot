# What is our profit % YTD?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.21 s
- **Tool:** `get_ratio` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**No margin base was named, so both operating margins are shown for RL Group, YTD Oct 2026 (Actual): Operating margin on revenue 14.9%; Operating margin on production 14.8%. Aggregates are ratios of sums.**

Components (Actual): Operating profit USD 180.1M; Revenue USD 1.21bn; Production USD 1.22bn.

- Operating margin on revenue: Actual 14.9%; 0.6 pp above PY (YTD Oct 2025) (14.3%), favourable; 0.6 pp below Budget (YTD Oct 2026) (15.5%), unfavourable
- Operating margin on production: Actual 14.8%; 0.6 pp above PY (YTD Oct 2025) (14.2%), favourable; 0.6 pp below Budget (YTD Oct 2026) (15.4%), unfavourable

## Table

| Version | Period | Operating profit | Revenue | Production | Operating margin on revenue | Operating margin on production |
|:---|---:|---:|---:|---:|---:|---:|
| Actual | YTD Oct 2026 | 180,115 | 1,211,161 | 1,215,120 | 14.9% | 14.8% |
| PY | YTD Oct 2025 | 164,263 | 1,150,044 | 1,153,543 | 14.3% | 14.2% |
| Budget | YTD Oct 2026 | 191,894 | 1,239,104 | 1,242,812 | 15.5% | 15.4% |

_USD k · Both operating margins (no base named). Margins = operating profit / revenue and / production; aggregates are ratios of sums._

## Chart

`grouped_bar` - Operating margins - RL Group ([interactive chart](27_what_is_our_profit_ytd_chart.html))

## Filters, version and period used

- Scope: RL Group
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025), Budget (Budget, YTD Oct 2026)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)
- Note: No margin base was named, so both operating margins are shown.

## Follow-up questions

1. How is operating profit YTD vs last year and budget for RL Group?
2. Show the operational profitability cockpit for RL Group
3. Show the operating margin trend for RL Group since 2025

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_ratio",
      "arguments": {
        "ratio_name": "operating_margins",
        "org": "",
        "period": "YTD Oct 2026",
        "comparison": "PY,Budget"
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
    "act": 0.198,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202601 AND 202610 GROUP BY fact_pnl.account_id
```

_3 more SQL statements in the JSON file._
