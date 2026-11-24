# Compare Budget vs FC2 vs Actual for Chile Metals & Minerals

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 21.31 s
- **Tool:** `compare_versions` (chosen by `llm_text`) · **numeric guardrail:** passed

## Answer

Actual USD 705k, USD 221k (23.9%) below Budget, unfavourable; FC2 USD 722k, USD 204k (22.0%) below Budget, unfavourable. The lower-than-expected MAOP and production are driven by higher external subcontracting costs, while lower personnel charges and other costs contribute to a slightly higher total functional costs.

- MAOP: Actual USD 705k, Budget USD 925k, FC2 USD 722k; Actual is USD 221k (23.9%) below Budget, unfavourable; FC2 is USD 204k (22.0%) below Budget, unfavourable
- Production: Actual USD 6.3M, Budget USD 6.5M, FC2 USD 6.3M; Actual is USD 134k (2.1%) below Budget, unfavourable; FC2 is USD 133k (2.1%) below Budget, unfavourable
- MAOP margin (on revenue): Actual 10.7%, Budget 13.8%, FC2 11.0%; Actual is 3.1 pp below Budget, unfavourable; FC2 is 2.8 pp below Budget, unfavourable

## Table

| Line | Actual | Budget | FC2 | Actual vs Budget | FC2 vs Budget |
|:---|---:|---:|---:|---:|---:|
| **PRODUCTION** | **6,341** | **6,475** | **6,342** | **(134)** | **(133)** |
| **REVENUE** | **6,556** | **6,700** | **6,558** | **(144)** | **(142)** |
| Personnel charges | (2,871) | (2,872) | (2,861) | 1 | 11 |
| External subcontracting | (364) | (271) | (358) | (93) | (87) |
| Other costs | (1,893) | (1,898) | (1,893) | 5 | 5 |
| Total functional costs | (668) | (666) | (667) | (2) | (1) |
| **GROSS PROFIT** | **1,373** | **1,591** | **1,389** | **(219)** | **(202)** |
| **MAOP** | **705** | **925** | **722** | **(221)** | **(204)** |
| **MANAGEMENT OP** | **639** | **851** | **655** | **(213)** | **(196)** |
| **NET INCOME** | **454** | **594** | **466** | **(140)** | **(128)** |
| MAOP margin (on revenue) | 10.7% | 13.8% | 11.0% | (3.1 pp) | (2.8 pp) |
| Gross margin | 21.6% | 24.6% | 21.9% | (2.9 pp) | (2.7 pp) |
| Direct margin | 66.0% | 66.7% | 66.2% | (0.7 pp) | (0.5 pp) |

_USD k · Signed values: costs negative. Variances are profit impact (positive = favourable)._

## Chart

`grouped_bar` - Versions - Chile · Metals & Minerals (YTD Oct 2026), costs shown as positive amounts ([interactive chart](06_compare_budget_vs_fc2_vs_actual_for_chile_metals_chart.html))

## Filters, version and period used

- Scope: Chile · Metals & Minerals
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), Budget (Budget, YTD Oct 2026), FC2 (FC2, YTD Oct 2026)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is Actual different from Budget for Chile · Metals & Minerals this year?
2. Show the MAOP trend vs Budget for Chile · Metals & Minerals this year
3. What does the latest forecast say for the full year 2026 for Chile · Metals & Minerals?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "compare_versions",
      "arguments": {
        "org": "Chile \u00b7 Metals & Minerals",
        "versions": [
          "Actual",
          "Budget",
          "FC2"
        ]
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 6.59,
      "usage": {
        "prompt_tokens": 2737,
        "completion_tokens": 49
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 14.63,
      "usage": {
        "prompt_tokens": 1148,
        "completion_tokens": 90
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
        "checked": 6
      }
    ],
    "unsupported": []
  },
  "errors": [],
  "timings": {
    "preprocess": 0.007,
    "plan": 6.595,
    "act": 0.079,
    "write#1": 14.625
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
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Chile') AND dim_org.l4_product_line IN (N'Metals & Minerals') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'FC2' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Chile') AND dim_org.l4_product_line IN (N'Metals & Minerals') GROUP BY fact_pnl.account_id
```
