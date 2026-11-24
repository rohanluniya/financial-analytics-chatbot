# now for Canada

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 37.48 s
- **Tool:** `get_pnl` (chosen by `llm_text`) · **numeric guardrail:** passed

## Answer

MAOP: Actual USD 26.1M; USD 1.1M (4.5%) above PY (USD 25.0M), favourable; USD 1.7M (6.2%) below Budget (USD 27.8M), unfavourable. The increase compared to PY is driven by Production (USD 8.0M higher, favourable) and Functional neutralization (USD 234k higher, favourable), partly offset by Personnel charges (USD 3.9M higher, unfavourable) and Other costs (USD 1.6M higher, unfavourable). The decrease compared to Budget is driven by Production (USD 5.1M lower, unfavourable) and Functional neutralization (USD 63k lower, unfavourable), partly offset by Personnel charges (USD 2.0M lower, favourable) and Other costs (USD 924k lower, favourable).

- Production: Actual USD 178.3M; USD 8.0M (4.7%) above PY (USD 170.3M), favourable; USD 5.1M (2.8%) below Budget (USD 183.4M), unfavourable
- Personnel charges: Actual USD 87.3M; USD 3.9M (4.7%) higher than PY (USD 83.3M), unfavourable; USD 2.0M (2.2%) lower than Budget (USD 89.3M), favourable
- Other costs: Actual USD 38.9M; USD 1.6M (4.4%) higher than PY (USD 37.3M), unfavourable; USD 924k (2.3%) lower than Budget (USD 39.9M), favourable
- MAOP margin (on revenue): Actual 14.7%; 0.0 pp below PY (14.7%), unfavourable; 0.5 pp below Budget (15.2%), unfavourable

## Table

| Line | Actual | PY | Budget | Var vs PY | Var % vs PY | Var vs Budget | Var % vs Budget |
|:---|---:|---:|---:|---:|---:|---:|---:|
| 1 Billing | 174,491 | 166,282 | 179,314 | 8,208 | 4.9% | (4,824) | (2.7%) |
| 2 WIP & UI | 3,157 | 3,363 | 3,381 | (206) | (6.1%) | (224) | (6.6%) |
| **3 REVENUE** | **177,648** | **169,645** | **182,696** | **8,003** | **4.7%** | **(5,048)** | **(2.8%)** |
| 4 Intragroup revenue | 7,999 | 7,685 | 8,257 | 314 | 4.1% | (258) | (3.1%) |
| 5 Intragroup subcontracting | (7,359) | (7,041) | (7,573) | (318) | (4.5%) | 214 | 2.8% |
| **6 PRODUCTION** | **178,288** | **170,289** | **183,380** | **7,999** | **4.7%** | **(5,092)** | **(2.8%)** |
| 7 Personnel charges | (87,265) | (83,335) | (89,261) | (3,929) | (4.7%) | 1,996 | 2.2% |
| 8 External subcontracting | (11,571) | (10,983) | (11,793) | (588) | (5.4%) | 221 | 1.9% |
| 9 Other costs | (38,933) | (37,289) | (39,857) | (1,644) | (4.4%) | 924 | 2.3% |
| 10 Functional neutralization | 4,473 | 4,238 | 4,536 | 234 | 5.5% | (63) | (1.4%) |
| **11 GROSS PROFIT** | **44,991** | **42,919** | **47,005** | **2,072** | **4.8%** | **(2,014)** | **(4.3%)** |
| 12 Total functional costs | (18,898) | (17,950) | (19,184) | (948) | (5.3%) | 287 | 1.5% |
| **13 MAOP** | **26,093** | **24,970** | **27,821** | **1,124** | **4.5%** | **(1,727)** | **(6.2%)** |
| 17 Other operating expenses | (1,294) | (1,246) | (1,244) | (48) | (3.8%) | (50) | (4.0%) |
| **18 MANAGEMENT OP** | **24,799** | **23,723** | **26,577** | **1,076** | **4.5%** | **(1,777)** | **(6.7%)** |
| 19 Financial result | (1,089) | (1,009) | (1,082) | (80) | (7.9%) | (6) | (0.6%) |
| 20 Corporate taxes | (6,283) | (6,019) | (6,756) | (264) | (4.4%) | 473 | 7.0% |
| **21 NET INCOME** | **17,427** | **16,695** | **18,738** | **732** | **4.4%** | **(1,311)** | **(7.0%)** |
| MAOP margin (on revenue) | 14.7% | 14.7% | 15.2% | 0.0 pp |  | (0.5 pp) |  |
| Gross margin | 25.2% | 25.2% | 25.6% | 0.0 pp |  | (0.4 pp) |  |
| Direct margin | 62.7% | 62.7% | 62.9% | 0.0 pp |  | (0.2 pp) |  |
| Personnel charges / Production | 48.9% | 48.9% | 48.7% | 0.0 pp |  | 0.3 pp |  |
| Total FTE (average) | 1,062 | 1,044 | 1,074 | 18 | 1.8% | (13) | (1.2%) |
| Total headcount (average) | 1,129 | 1,109 | 1,142 | 20 | 1.8% | (13) | (1.2%) |

_USD k · Signed values: costs negative. Variances are profit impact (positive = favourable)._

## Chart

`waterfall` - MAOP bridge PY to Actual - Canada (YTD Oct 2026) ([interactive chart](02_now_for_canada_chart.html))

## Filters, version and period used

- Scope: Canada
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025), Budget (Budget, YTD Oct 2026)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. What are the main drivers of the MAOP variance vs budget for Canada?
2. Show the monthly MAOP trend for Canada vs last year
3. Which product lines in Canada have the lowest MAOP margin this year?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_pnl",
      "arguments": {
        "org": "Canada",
        "period": "YTD Oct 2026",
        "versions": [
          "Actual",
          "PY",
          "Budget"
        ]
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 7.23,
      "usage": {
        "prompt_tokens": 2736,
        "completion_tokens": 53
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 30.02,
      "usage": {
        "prompt_tokens": 1620,
        "completion_tokens": 200
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
        "checked": 15
      }
    ],
    "unsupported": []
  },
  "errors": [],
  "timings": {
    "preprocess": 0.005,
    "plan": 7.237,
    "act": 0.215,
    "write#1": 30.017
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Canada') GROUP BY fact_pnl.account_id
```

```sql
SELECT sum(fact_stats.fte) AS fte_sum, sum(fact_stats.headcount) AS headcount_sum, sum(fact_stats.direct_fte) AS direct_fte_sum, sum(fact_stats.billable_hours) AS billable_hours_sum, sum(fact_stats.available_hours) AS available_hours_sum, sum(fact_stats.overtime_hours) AS overtime_hours_sum, count(DISTINCT fact_stats.month_key) AS n_months 
FROM fact_stats JOIN dim_org ON fact_stats.bu_id = dim_org.bu_id JOIN dim_version ON fact_stats.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_stats.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Canada')
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Canada') GROUP BY fact_pnl.account_id
```

_3 more SQL statements in the JSON file._
