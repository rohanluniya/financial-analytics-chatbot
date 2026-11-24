# How is the whole group doing this year vs budget?

- **Persona:** United States Country Head
- **Model:** `rules` · **status:** ok · **latency:** 0.23 s
- **Tool:** `get_pnl` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**MAOP: Actual USD 54.4M; USD 1.9M (3.4%) below Budget (USD 56.4M), unfavourable.**

MAOP vs Budget: decrease of USD 1.9M driven by Production (USD 6.3M lower, unfavourable) and Functional neutralization (USD 100k lower, unfavourable), partly offset by Personnel charges (USD 2.6M lower, favourable) and Other costs (USD 811k lower, favourable).

- Production: Actual USD 322.5M; USD 6.3M (1.9%) below Budget (USD 328.8M), unfavourable
- Personnel charges: Actual USD 162.4M; USD 2.6M (1.6%) lower than Budget (USD 165.0M), favourable
- Other costs: Actual USD 50.5M; USD 811k (1.6%) lower than Budget (USD 51.3M), favourable
- MAOP margin (on revenue): Actual 17.0%; 0.3 pp below Budget (17.3%), unfavourable

_Your access covers **United States** only, so the figures below are for **United States** (not all of RL Group)._

## Table

| Line | Actual | Budget | Var vs Budget | Var % vs Budget |
|:---|---:|---:|---:|---:|
| 1 Billing | 314,454 | 320,495 | (6,041) | (1.9%) |
| 2 WIP & UI | 5,778 | 6,064 | (286) | (4.7%) |
| **3 REVENUE** | **320,232** | **326,559** | **(6,327)** | **(1.9%)** |
| 4 Intragroup revenue | 13,350 | 13,592 | (242) | (1.8%) |
| 5 Intragroup subcontracting | (11,048) | (11,349) | 301 | 2.7% |
| **6 PRODUCTION** | **322,533** | **328,801** | **(6,268)** | **(1.9%)** |
| 7 Personnel charges | (162,422) | (165,015) | 2,593 | 1.6% |
| 8 External subcontracting | (29,333) | (29,985) | 651 | 2.2% |
| 9 Other costs | (50,492) | (51,303) | 811 | 1.6% |
| 10 Functional neutralization | 8,078 | 8,178 | (100) | (1.2%) |
| **11 GROSS PROFIT** | **88,363** | **90,677** | **(2,314)** | **(2.6%)** |
| 12 Total functional costs | (33,924) | (34,310) | 386 | 1.1% |
| **13 MAOP** | **54,439** | **56,367** | **(1,928)** | **(3.4%)** |
| 17 Other operating expenses | (2,783) | (2,594) | (188) | (7.3%) |
| **18 MANAGEMENT OP** | **51,657** | **53,773** | **(2,116)** | **(3.9%)** |
| 19 Financial result | (1,924) | (1,938) | 14 | 0.7% |
| 20 Corporate taxes | (12,433) | (12,959) | 526 | 4.1% |
| **21 NET INCOME** | **37,299** | **38,876** | **(1,577)** | **(4.1%)** |
| MAOP margin (on revenue) | 17.0% | 17.3% | (0.3 pp) |  |
| Gross margin | 27.4% | 27.6% | (0.2 pp) |  |
| Direct margin | 60.6% | 60.8% | (0.1 pp) |  |
| Personnel charges / Production | 50.4% | 50.2% | 0.2 pp |  |
| Total FTE (average) | 1,694 | 1,708 | (13) | (0.8%) |
| Total headcount (average) | 1,810 | 1,824 | (14) | (0.8%) |

_USD k · Signed values: costs negative. Variances are profit impact (positive = favourable)._

## Chart

`waterfall` - MAOP bridge Budget to Actual - United States (YTD Oct 2026) ([interactive chart](16_how_is_the_whole_group_doing_this_year_vs_budget_chart.html))

## Filters, version and period used

- Scope: United States
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), Budget (Budget, YTD Oct 2026)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)
- Note: Your access covers **United States** only, so the figures below are for **United States** (not all of RL Group).

## Follow-up questions

1. What are the main drivers of the MAOP variance vs budget for United States?
2. Show the monthly MAOP trend for United States vs last year
3. Which product lines in United States have the lowest MAOP margin this year?

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
        "draft": ""
      }
    ],
    "unsupported": [
      "<empty>"
    ]
  },
  "errors": [],
  "timings": {
    "preprocess": 0.012,
    "plan": 0.0,
    "act": 0.211,
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
