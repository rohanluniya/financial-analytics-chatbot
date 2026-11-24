# How is the whole group doing this year vs budget?

- **Persona:** United States Country Head
- **Model:** `rules` · **status:** ok · **latency:** 0.21 s
- **Tool:** `get_pnl` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Operating profit: Actual USD 68.0M; USD 7.9M (13.0%) above Budget (USD 60.2M), favourable.**

Operating profit vs Budget: increase of USD 7.9M driven by Production (USD 5.9M higher, favourable) and Personnel costs (USD 2.1M lower, favourable), partly offset by Other costs (USD 524k higher, unfavourable) and Functional cost recharges (USD 97k lower, unfavourable).

- Production: Actual USD 356.4M; USD 5.9M (1.7%) above Budget (USD 350.4M), favourable
- Personnel costs: Actual USD 180.6M; USD 2.1M (1.2%) lower than Budget (USD 182.7M), favourable
- Other costs: Actual USD 56.0M; USD 524k (0.9%) higher than Budget (USD 55.5M), unfavourable
- Operating margin on revenue: Actual 19.3%; 2.0 pp above Budget (17.3%), favourable

_Your access covers **United States** only, so the figures below are for **United States** (not all of RL Group)._

## Table

| Line | Actual | Budget | Var vs Budget | Var % vs Budget |
|:---|---:|---:|---:|---:|
| Billing | 346,403 | 340,917 | 5,486 | 1.6% |
| WIP & deferred income | 6,573 | 6,492 | 81 | 1.3% |
| **REVENUE** | **352,976** | **347,409** | **5,568** | **1.6%** |
| Intragroup revenue | 15,010 | 14,647 | 363 | 2.5% |
| Intragroup subcontracting | (11,634) | (11,617) | (18) | (0.2%) |
| **PRODUCTION** | **356,352** | **350,439** | **5,913** | **1.7%** |
| Personnel costs | (180,583) | (182,730) | 2,147 | 1.2% |
| External subcontracting | (24,099) | (24,003) | (96) | (0.4%) |
| Other costs | (56,004) | (55,480) | (524) | (0.9%) |
| Functional cost recharges | 8,607 | 8,704 | (97) | (1.1%) |
| **GROSS PROFIT** | **104,273** | **96,930** | **7,344** | **7.6%** |
| Functional costs | (36,231) | (36,738) | 507 | 1.4% |
| **OPERATING PROFIT** | **68,042** | **60,192** | **7,851** | **13.0%** |
| Other operating expenses | (3,024) | (3,186) | 162 | 5.1% |
| **EBIT** | **65,018** | **57,005** | **8,013** | **14.1%** |
| Financial result | (2,066) | (2,065) | (1) | (0.1%) |
| Income taxes | (15,738) | (13,735) | (2,003) | (14.6%) |
| **NET INCOME** | **47,214** | **41,205** | **6,009** | **14.6%** |
| Operating margin on revenue | 19.3% | 17.3% | 2.0 pp |  |
| Operating margin on production | 19.1% | 17.2% | 1.9 pp |  |
| Gross margin | 29.3% | 27.7% | 1.6 pp |  |
| Direct margin | 60.1% | 59.0% | 1.1 pp |  |
| Personnel costs / Production | 50.7% | 52.1% | (1.5 pp) |  |
| Total FTE (average) | 1,888 | 1,897 | (8.9) | (0.5%) |
| Total headcount (average) | 2,008 | 2,029 | (21) | (1.0%) |

_USD k · Signed values: costs negative. Variances are profit impact (positive = favourable)._

## Chart

`waterfall` - Operating profit bridge Budget to Actual - United States (YTD Oct 2026) ([interactive chart](21_how_is_the_whole_group_doing_this_year_vs_budget_chart.html))

## Filters, version and period used

- Scope: United States
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), Budget (Budget, YTD Oct 2026)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)
- Note: Your access covers **United States** only, so the figures below are for **United States** (not all of RL Group).

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
        "org": "RL Group",
        "period": "YTD Oct 2026",
        "versions": [
          "Actual",
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
    "preprocess": 0.008,
    "plan": 0.0,
    "act": 0.2,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l1_group IN (N'RL Group') AND dim_org.l3_country IN (N'United States') GROUP BY fact_pnl.account_id
```

```sql
SELECT sum(fact_stats.fte) AS fte_sum, sum(fact_stats.headcount) AS headcount_sum, sum(fact_stats.direct_fte) AS direct_fte_sum, sum(fact_stats.billable_hours) AS billable_hours_sum, sum(fact_stats.available_hours) AS available_hours_sum, sum(fact_stats.overtime_hours) AS overtime_hours_sum, count(DISTINCT fact_stats.month_key) AS n_months 
FROM fact_stats JOIN dim_org ON fact_stats.bu_id = dim_org.bu_id JOIN dim_version ON fact_stats.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_stats.month_key BETWEEN 202601 AND 202610 AND dim_org.l1_group IN (N'RL Group') AND dim_org.l3_country IN (N'United States')
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202601 AND 202610 AND dim_org.l1_group IN (N'RL Group') AND dim_org.l3_country IN (N'United States') GROUP BY fact_pnl.account_id
```

_1 more SQL statements in the JSON file._
