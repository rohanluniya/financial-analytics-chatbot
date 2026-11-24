# Headcount, hires and leavers by month for Canada Environmental Lab Testing this year

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.19 s
- **Tool:** `get_workforce` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Average headcount: 353; 29.1 (7.6%) below PY (382).**

- Attrition rate (annualised): 31.7%; 20.3 pp above PY (11.3%), unfavourable
- Leavers: 93; 57 (158.3%) more than PY (36); of these 32 voluntary and 61 restructuring (PY 34 voluntary and 2 restructuring)
- Hires: 47; in line with PY (47)
- Month with the most leavers: Apr 2026 (60, of which 58 restructuring)

## Table

| Month | Headcount | Headcount PY | Hires | Leavers | of which restructuring | Attrition | Attrition PY | Utilization | Utilization PY | Overtime ratio |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Jan 2026 | 387 | 378 | 11 | 4 | 0 | 12.8% | 10.7% | 71.8% | 74.6% | 5.2% |
| Feb 2026 | 388 | 381 | 5 | 6 | 0 | 13.6% | 10.9% | 62.2% | 73.1% | 4.2% |
| Mar 2026 | 388 | 379 | 6 | 1 | 0 | 12.7% | 11.2% | 59.9% | 72.1% | 5.0% |
| Apr 2026 | 389 | 380 | 2 | 60 | 58 | 27.0% | 11.7% | 63.8% | 72.4% | 4.6% |
| May 2026 | 329 | 381 | 0 | 4 | 2 | 27.8% | 10.9% | 68.6% | 74.8% | 4.1% |
| Jun 2026 | 327 | 382 | 2 | 1 | 0 | 27.4% | 10.9% | 71.1% | 73.0% | 4.7% |
| Jul 2026 | 328 | 383 | 2 | 5 | 0 | 28.0% | 11.6% | 70.6% | 75.6% | 3.9% |
| Aug 2026 | 330 | 383 | 7 | 6 | 1 | 29.1% | 11.6% | 68.9% | 71.6% | 3.3% |
| Sep 2026 | 329 | 385 | 5 | 5 | 0 | 30.1% | 11.6% | 71.3% | 74.1% | 4.7% |
| Oct 2026 | 331 | 385 | 7 | 1 | 0 | 30.2% | 11.6% | 69.0% | 75.3% | 5.1% |
| **Total YTD Oct 2026** | **353** | **382** | **47** | **93** | **61** | **31.7%** | **11.3%** | **67.4%** | **73.7%** | **4.5%** |

_Fictional employee records, closed months. Headcount and FTE are monthly averages; attrition = leavers x 12 / months / average headcount (monthly rows: rolling 12 months to that month); utilization and overtime use direct staff hours. Green / red = better / worse than PY._

## Chart

`grouped_bar` - Hires and leavers by month - Canada · Environmental Lab Testing (YTD Oct 2026) ([interactive chart](15_headcount_hires_and_leavers_by_month_for_canada_chart.html))

## Filters, version and period used

- Scope: Canada · Environmental Lab Testing
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (YTD Oct 2026), PY (Jan 2025 - Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show attrition by role for Canada · Environmental Lab Testing this year
2. Show utilization by grade for Canada · Environmental Lab Testing this year
3. Which businesses in Canada · Environmental Lab Testing have the highest attrition this year?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_workforce",
      "arguments": {
        "org": "Canada \u00b7 Environmental Lab Testing",
        "period": "YTD Oct 2026",
        "group_by": "",
        "metric": "",
        "top_n": 0
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
    "act": 0.177,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_employee_month.month_key
```

```sql
SELECT fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_employee_month.month_key
```

```sql
SELECT fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202502 AND 202610 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY fact_employee_month.month_key
```

_1 more SQL statements in the JSON file._
