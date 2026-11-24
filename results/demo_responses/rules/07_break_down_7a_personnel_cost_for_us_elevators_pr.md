# Break down 7A personnel cost for US Elevators & Pressure Vessels in March 2025

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.12 s
- **Tool:** `variance_drivers` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Direct labor cost (7A) for United States · Elevators & Pressure Vessels, Mar 2025: Actual USD 2.0M, USD 478k (31.0%) higher than PY (USD 1.5M), unfavourable.**

Account drivers (largest first): 7A2 Bonus: USD 593k vs USD 160k, impact +USD 433k (unfavourable, 90.6% of the change); 7A1 Guaranteed salary: USD 1.0M vs USD 975k, impact +USD 29k (unfavourable, 6.1% of the change); 7A4 Social security: USD 231k vs USD 224k, impact +USD 7k (unfavourable, 1.5% of the change); 7A3 Variable / overtime: USD 85k vs USD 79k, impact +USD 6k (unfavourable, 1.3% of the change); 7A5 Pension: USD 78k vs USD 75k, impact +USD 3k (unfavourable, 0.5% of the change).

- Bu with the largest change: US-EPV-DEN-02 USD 1.2M vs USD 935k (change +USD 282k, unfavourable)

## Table

| Driver | PY | Actual | Impact | Share of variance |
|:---|---:|---:|---:|---:|
| 7A2 Bonus | 160 | 593 | 433 | 90.6% |
| 7A1 Guaranteed salary | 975 | 1,004 | 29 | 6.1% |
| 7A4 Social security | 224 | 231 | 7 | 1.5% |
| 7A3 Variable / overtime | 79 | 85 | 6 | 1.3% |
| 7A5 Pension | 75 | 78 | 3 | 0.5% |
| 7A6 Other personnel | 30 | 30 | 0 | 0.0% |

_USD k · Impact = contribution to the change in Direct labor cost (7A) (USD; positive = higher cost)_

**By bu**

| BU | PY | Actual | Impact |
|:---|---:|---:|---:|
| US-EPV-DEN-02 | 935 | 1,217 | 282 |
| US-EPV-DEN-01 | 608 | 804 | 196 |

_USD k · By bu_

## Chart

`stacked_bar` - Direct labor cost (7A) mix: PY vs Actual - United States · Elevators & Pressure Vessels (Mar 2025) ([interactive chart](07_break_down_7a_personnel_cost_for_us_elevators_pr_chart.html))

## Filters, version and period used

- Scope: United States · Elevators & Pressure Vessels
- Period: Mar 2025 (Mar 2025 - Mar 2025)
- Versions: Actual (Actual, Mar 2025), PY (Actual, Mar 2024)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show the monthly trend of Direct labor cost (7A) for United States · Elevators & Pressure Vessels since 2025
2. Show the 7A2 Bonus trend for United States · Elevators & Pressure Vessels vs budget
3. Compare Budget vs FC3 vs Actual for United States · Elevators & Pressure Vessels

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "variance_drivers",
      "arguments": {
        "metric": "personnel_7a",
        "org": "United States \u00b7 Elevators & Pressure Vessels",
        "period": "2025-03",
        "comparison": "PY",
        "depth": 2
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
    "preprocess": 0.009,
    "plan": 0.0,
    "act": 0.101,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202503 AND 202503 AND dim_org.l3_country IN (N'United States') AND dim_org.l4_product_line IN (N'Elevators & Pressure Vessels') GROUP BY fact_pnl.account_id
```

```sql
SELECT fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202403 AND 202403 AND dim_org.l3_country IN (N'United States') AND dim_org.l4_product_line IN (N'Elevators & Pressure Vessels') GROUP BY fact_pnl.account_id
```

```sql
SELECT dim_org.l6_bu, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202503 AND 202503 AND dim_org.l3_country IN (N'United States') AND dim_org.l4_product_line IN (N'Elevators & Pressure Vessels') GROUP BY dim_org.l6_bu, fact_pnl.account_id
```

_1 more SQL statements in the JSON file._
