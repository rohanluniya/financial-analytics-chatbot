# now for Canada

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.28 s
- **Tool:** `get_pnl` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Operating profit: Actual USD 21.5M; USD 5.9M (21.7%) below PY (USD 27.4M), unfavourable; USD 13.6M (38.8%) below Budget (USD 35.1M), unfavourable.**

Operating profit vs PY: decrease of USD 5.9M driven by Production (USD 4.2M lower, unfavourable) and Personnel costs (USD 1.0M higher, unfavourable), partly offset by Functional cost recharges (USD 230k higher, favourable) and Other costs (USD 203k lower, favourable).

- Production: Actual USD 177.8M; USD 4.2M (2.3%) below PY (USD 182.1M), unfavourable; USD 22.5M (11.3%) below Budget (USD 200.4M), unfavourable
- Personnel costs: Actual USD 88.7M; USD 1.0M (1.1%) higher than PY (USD 87.7M), unfavourable; USD 4.9M (5.2%) lower than Budget (USD 93.7M), favourable
- Functional costs: Actual USD 19.6M; USD 948k (5.1%) higher than PY (USD 18.6M), unfavourable; USD 277k (1.4%) lower than Budget (USD 19.9M), favourable
- Operating margin on revenue: Actual 12.1%; 3.0 pp below PY (15.1%), unfavourable; 5.5 pp below Budget (17.6%), unfavourable

## Table

| Line | Actual | PY | Budget | Var vs PY | Var % vs PY | Var vs Budget | Var % vs Budget |
|:---|---:|---:|---:|---:|---:|---:|---:|
| Billing | 173,949 | 178,110 | 195,856 | (4,161) | (2.3%) | (21,907) | (11.2%) |
| WIP & deferred income | 3,260 | 3,243 | 3,723 | 18 | 0.6% | (462) | (12.4%) |
| **REVENUE** | **177,209** | **181,352** | **199,579** | **(4,143)** | **(2.3%)** | **(22,369)** | **(11.2%)** |
| Intragroup revenue | 8,108 | 8,340 | 9,204 | (232) | (2.8%) | (1,096) | (11.9%) |
| Intragroup subcontracting | (7,468) | (7,617) | (8,384) | 149 | 2.0% | 916 | 10.9% |
| **PRODUCTION** | **177,850** | **182,075** | **200,398** | **(4,225)** | **(2.3%)** | **(22,549)** | **(11.3%)** |
| Personnel costs | (88,746) | (87,743) | (93,662) | (1,003) | (1.1%) | 4,916 | 5.2% |
| External subcontracting | (14,943) | (14,747) | (15,942) | (196) | (1.3%) | 999 | 6.3% |
| Other costs | (37,772) | (37,976) | (40,594) | 203 | 0.5% | 2,821 | 6.9% |
| Functional cost recharges | 4,662 | 4,432 | 4,732 | 230 | 5.2% | (70) | (1.5%) |
| **GROSS PROFIT** | **41,051** | **46,042** | **54,933** | **(4,991)** | **(10.8%)** | **(13,883)** | **(25.3%)** |
| Functional costs | (19,595) | (18,647) | (19,872) | (948) | (5.1%) | 277 | 1.4% |
| **OPERATING PROFIT** | **21,456** | **27,395** | **35,062** | **(5,939)** | **(21.7%)** | **(13,606)** | **(38.8%)** |
| Other operating expenses | (2,338) | (1,127) | (1,162) | (1,211) | (107.5%) | (1,176) | (101.2%) |
| **EBIT** | **19,118** | **26,268** | **33,900** | **(7,150)** | **(27.2%)** | **(14,782)** | **(43.6%)** |
| Financial result | (1,106) | (1,100) | (1,126) | (7) | (0.6%) | 20 | 1.7% |
| Income taxes | (4,773) | (6,670) | (8,685) | 1,897 | 28.4% | 3,912 | 45.0% |
| **NET INCOME** | **13,238** | **18,499** | **24,089** | **(5,260)** | **(28.4%)** | **(10,850)** | **(45.0%)** |
| Operating margin on revenue | 12.1% | 15.1% | 17.6% | (3.0 pp) |  | (5.5 pp) |  |
| Operating margin on production | 12.1% | 15.0% | 17.5% | (3.0 pp) |  | (5.4 pp) |  |
| Gross margin | 23.1% | 25.3% | 27.4% | (2.2 pp) |  | (4.3 pp) |  |
| Direct margin | 61.5% | 62.9% | 64.0% | (1.3 pp) |  | (2.5 pp) |  |
| Personnel costs / Production | 49.9% | 48.2% | 46.7% | 1.7 pp |  | 3.2 pp |  |
| Total FTE (average) | 1,076 | 1,094 | 1,127 | (18) | (1.6%) | (51) | (4.5%) |
| Total headcount (average) | 1,147 | 1,164 | 1,197 | (17) | (1.5%) | (50) | (4.2%) |

_USD k · Signed values: costs negative. Variances are profit impact (positive = favourable)._

## Chart

`waterfall` - Operating profit bridge PY to Actual - Canada (YTD Oct 2026) ([interactive chart](02_now_for_canada_chart.html))

## Filters, version and period used

- Scope: Canada
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025), Budget (Budget, YTD Oct 2026)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. What are the main drivers of the operating profit variance vs budget for Canada?
2. Show the monthly operating profit trend for Canada vs last year
3. Which product lines in Canada have the lowest operating margin this year?

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
    "preprocess": 0.006,
    "plan": 0.0,
    "act": 0.263,
    "write#1": 0.0
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
