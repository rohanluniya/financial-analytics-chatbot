# How is operating profit YTD vs last year and budget for the United States?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.51 s
- **Tool:** `get_pnl` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Operating profit: Actual USD 68.0M; USD 15.4M (29.1%) above PY (USD 52.7M), favourable; USD 7.9M (13.0%) above Budget (USD 60.2M), favourable.**

Operating profit vs PY: increase of USD 15.4M driven by Production (USD 29.7M higher, favourable) and Functional cost recharges (USD 400k higher, favourable), partly offset by Personnel costs (USD 8.0M higher, unfavourable) and Other costs (USD 3.7M higher, unfavourable).

- Production: Actual USD 356.4M; USD 29.7M (9.1%) above PY (USD 326.6M), favourable; USD 5.9M (1.7%) above Budget (USD 350.4M), favourable
- Personnel costs: Actual USD 180.6M; USD 8.0M (4.6%) higher than PY (USD 172.6M), unfavourable; USD 2.1M (1.2%) lower than Budget (USD 182.7M), favourable
- Other costs: Actual USD 56.0M; USD 3.7M (7.2%) higher than PY (USD 52.3M), unfavourable; USD 524k (0.9%) higher than Budget (USD 55.5M), unfavourable
- Operating margin on revenue: Actual 19.3%; 3.0 pp above PY (16.3%), favourable; 2.0 pp above Budget (17.3%), favourable

## Table

| Line | Actual | PY | Budget | Var vs PY | Var % vs PY | Var vs Budget | Var % vs Budget |
|:---|---:|---:|---:|---:|---:|---:|---:|
| Billing | 346,403 | 318,112 | 340,917 | 28,291 | 8.9% | 5,486 | 1.6% |
| WIP & deferred income | 6,573 | 5,652 | 6,492 | 921 | 16.3% | 81 | 1.3% |
| **REVENUE** | **352,976** | **323,764** | **347,409** | **29,212** | **9.0%** | **5,568** | **1.6%** |
| Intragroup revenue | 15,010 | 13,691 | 14,647 | 1,320 | 9.6% | 363 | 2.5% |
| Intragroup subcontracting | (11,634) | (10,806) | (11,617) | (828) | (7.7%) | (18) | (0.2%) |
| **PRODUCTION** | **356,352** | **326,649** | **350,439** | **29,704** | **9.1%** | **5,913** | **1.7%** |
| Personnel costs | (180,583) | (172,618) | (182,730) | (7,965) | (4.6%) | 2,147 | 1.2% |
| External subcontracting | (24,099) | (22,580) | (24,003) | (1,519) | (6.7%) | (96) | (0.4%) |
| Other costs | (56,004) | (52,262) | (55,480) | (3,742) | (7.2%) | (524) | (0.9%) |
| Functional cost recharges | 8,607 | 8,207 | 8,704 | 400 | 4.9% | (97) | (1.1%) |
| **GROSS PROFIT** | **104,273** | **87,396** | **96,930** | **16,878** | **19.3%** | **7,344** | **7.6%** |
| Functional costs | (36,231) | (34,709) | (36,738) | (1,522) | (4.4%) | 507 | 1.4% |
| **OPERATING PROFIT** | **68,042** | **52,687** | **60,192** | **15,355** | **29.1%** | **7,851** | **13.0%** |
| Other operating expenses | (3,024) | (2,870) | (3,186) | (154) | (5.4%) | 162 | 5.1% |
| **EBIT** | **65,018** | **49,817** | **57,005** | **15,202** | **30.5%** | **8,013** | **14.1%** |
| Financial result | (2,066) | (1,960) | (2,065) | (106) | (5.4%) | (1) | (0.1%) |
| Income taxes | (15,738) | (11,964) | (13,735) | (3,774) | (31.5%) | (2,003) | (14.6%) |
| **NET INCOME** | **47,214** | **35,893** | **41,205** | **11,322** | **31.5%** | **6,009** | **14.6%** |
| Operating margin on revenue | 19.3% | 16.3% | 17.3% | 3.0 pp |  | 2.0 pp |  |
| Operating margin on production | 19.1% | 16.1% | 17.2% | 3.0 pp |  | 1.9 pp |  |
| Gross margin | 29.3% | 26.8% | 27.7% | 2.5 pp |  | 1.6 pp |  |
| Direct margin | 60.1% | 58.4% | 59.0% | 1.7 pp |  | 1.1 pp |  |
| Personnel costs / Production | 50.7% | 52.8% | 52.1% | (2.2 pp) |  | (1.5 pp) |  |
| Total FTE (average) | 1,888 | 1,865 | 1,897 | 23 | 1.3% | (8.9) | (0.5%) |
| Total headcount (average) | 2,008 | 1,980 | 2,029 | 28 | 1.4% | (21) | (1.0%) |

_USD k · Signed values: costs negative. Variances are profit impact (positive = favourable)._

## Chart

`waterfall` - Operating profit bridge PY to Actual - United States (YTD Oct 2026) ([interactive chart](01_how_is_operating_profit_ytd_vs_last_year_and_bud_chart.html))

## Filters, version and period used

- Scope: United States
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025), Budget (Budget, YTD Oct 2026)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. What are the main drivers of the operating profit variance vs budget for United States?
2. Show the monthly operating profit trend for United States vs last year
3. Which product lines in United States have the lowest operating margin this year?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_pnl",
      "arguments": {
        "org": "United States",
        "period": "YTD Oct 2026",
        "versions": [
          "Actual",
          "PY",
          "Budget"
        ],
        "account_depth": 1
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
    "preprocess": 0.188,
    "plan": 0.0,
    "act": 0.311,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'United States') GROUP BY fact_pnl.account_id
```

```sql
SELECT sum(fact_stats.fte) AS fte_sum, sum(fact_stats.headcount) AS headcount_sum, sum(fact_stats.direct_fte) AS direct_fte_sum, sum(fact_stats.billable_hours) AS billable_hours_sum, sum(fact_stats.available_hours) AS available_hours_sum, sum(fact_stats.overtime_hours) AS overtime_hours_sum, count(DISTINCT fact_stats.month_key) AS n_months 
FROM fact_stats JOIN dim_org ON fact_stats.bu_id = dim_org.bu_id JOIN dim_version ON fact_stats.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_stats.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'United States')
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'United States') GROUP BY fact_pnl.account_id
```

_3 more SQL statements in the JSON file._
