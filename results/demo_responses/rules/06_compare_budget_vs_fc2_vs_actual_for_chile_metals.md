# Compare Budget vs FC2 vs Actual for Chile Metals & Minerals

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.12 s
- **Tool:** `compare_versions` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Version comparison for Chile · Metals & Minerals, YTD Oct 2026: Actual, FC2, Budget (USD).**

- Operating profit: Actual USD 8.1M, FC2 USD 8.5M, Budget USD 8.3M; Actual is USD 175k (2.1%) below Budget, unfavourable; FC2 is USD 218k (2.6%) above Budget, favourable
- Production: Actual USD 54.9M, FC2 USD 55.4M, Budget USD 54.5M; Actual is USD 363k (0.7%) above Budget, favourable; FC2 is USD 866k (1.6%) above Budget, favourable
- Operating margin on revenue: Actual 14.8%, FC2 15.4%, Budget 15.3%; Actual is 0.4 pp below Budget, unfavourable; FC2 is 0.2 pp above Budget, favourable

## Table

| Line | Actual | FC2 | Budget | Actual vs Budget | FC2 vs Budget |
|:---|---:|---:|---:|---:|---:|
| **PRODUCTION** | **54,910** | **55,413** | **54,547** | **363** | **866** |
| **REVENUE** | **54,513** | **55,019** | **54,158** | **354** | **861** |
| Personnel costs | (23,775) | (23,768) | (24,012) | 237 | 244 |
| External subcontracting | (2,908) | (2,956) | (2,166) | (742) | (790) |
| Other costs | (16,020) | (16,095) | (15,949) | (72) | (146) |
| Functional costs | (5,414) | (5,408) | (5,459) | 45 | 51 |
| **GROSS PROFIT** | **13,502** | **13,888** | **13,721** | **(219)** | **167** |
| **OPERATING PROFIT** | **8,087** | **8,480** | **8,262** | **(175)** | **218** |
| **EBIT** | **7,945** | **8,331** | **8,046** | **(101)** | **285** |
| **NET INCOME** | **5,578** | **5,867** | **5,649** | **(70)** | **218** |
| Operating margin on revenue | 14.8% | 15.4% | 15.3% | (0.4 pp) | 0.2 pp |
| Operating margin on production | 14.7% | 15.3% | 15.1% | (0.4 pp) | 0.2 pp |
| Gross margin | 24.6% | 25.1% | 25.2% | (0.6 pp) | (0.1 pp) |
| Direct margin | 67.5% | 67.8% | 66.9% | 0.5 pp | 0.8 pp |

_USD k · Signed values: costs negative. Variances are profit impact (positive = favourable)._

## Chart

`grouped_bar` - Versions - Chile · Metals & Minerals (YTD Oct 2026), costs shown as positive amounts ([interactive chart](06_compare_budget_vs_fc2_vs_actual_for_chile_metals_chart.html))

## Filters, version and period used

- Scope: Chile · Metals & Minerals
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), FC2 (FC2, YTD Oct 2026), Budget (Budget, YTD Oct 2026)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is Actual different from Budget for Chile · Metals & Minerals this year?
2. Show the operating profit trend vs Budget for Chile · Metals & Minerals this year
3. What does the latest forecast say for the full year 2026 for Chile · Metals & Minerals?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "compare_versions",
      "arguments": {
        "org": "Chile \u00b7 Metals & Minerals",
        "period": "",
        "versions": [
          "Actual",
          "FC2",
          "Budget"
        ]
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
    "act": 0.11,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Chile') AND dim_org.l4_product_line IN (N'Metals & Minerals') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'FC2' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Chile') AND dim_org.l4_product_line IN (N'Metals & Minerals') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Chile') AND dim_org.l4_product_line IN (N'Metals & Minerals') GROUP BY fact_pnl.account_id
```
