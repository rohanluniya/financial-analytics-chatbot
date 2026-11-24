# Break down direct staff costs for US Elevators & Pressure Vessels in March 2025

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.46 s
- **Tool:** `variance_drivers` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Direct staff costs for United States · Elevators & Pressure Vessels, Mar 2025: Actual USD 1.6M, USD 354k (28.2%) higher than PY (USD 1.3M), unfavourable.**

Account drivers (largest first): Direct staff bonus: USD 469k vs USD 152k, impact +USD 318k (unfavourable, 89.8% of the change); Direct staff salaries: USD 794k vs USD 772k, impact +USD 22k (unfavourable, 6.3% of the change); Direct staff social security: USD 183k vs USD 177k, impact +USD 6k (unfavourable, 1.7% of the change); Direct staff overtime: USD 75k vs USD 71k, impact +USD 4k (unfavourable, 1.1% of the change); Direct staff pension: USD 62k vs USD 59k, impact +USD 3k (unfavourable, 0.8% of the change).

- BU with the largest change: US-EPV-NYC-01 USD 788k vs USD 608k (change +USD 180k, unfavourable)

## Table

| Driver | PY | Actual | Impact | Share of variance |
|:---|---:|---:|---:|---:|
| Direct staff bonus | 152 | 469 | 318 | 89.8% |
| Direct staff salaries | 772 | 794 | 22 | 6.3% |
| Direct staff social security | 177 | 183 | 6 | 1.7% |
| Direct staff overtime | 71 | 75 | 4 | 1.1% |
| Direct staff pension | 59 | 62 | 3 | 0.8% |
| Direct staff other costs | 25 | 26 | 2 | 0.4% |

_USD k · Impact = contribution to the change in Direct staff costs (USD; positive = higher cost)_

**By bu**

| BU | PY | Actual | Impact |
|:---|---:|---:|---:|
| US-EPV-NYC-01 | 608 | 788 | 180 |
| US-EPV-NYC-02 | 648 | 823 | 174 |

_USD k · By bu_

## Chart

`stacked_bar` - Direct staff costs mix: PY vs Actual - United States · Elevators & Pressure Vessels (Mar 2025) ([interactive chart](07_break_down_direct_staff_costs_for_us_elevators_p_chart.html))

## Filters, version and period used

- Scope: United States · Elevators & Pressure Vessels
- Period: Mar 2025 (Mar 2025 - Mar 2025)
- Versions: Actual (Actual, Mar 2025), PY (Actual, Mar 2024)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show the monthly trend of Direct staff costs for United States · Elevators & Pressure Vessels since 2025
2. Show the Direct staff bonus trend for United States · Elevators & Pressure Vessels vs budget
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
    "preprocess": 0.324,
    "plan": 0.0,
    "act": 0.126,
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
