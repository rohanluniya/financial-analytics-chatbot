# Utilization rate by grade in the United States this year

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.11 s
- **Tool:** `get_workforce` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Utilization rate (direct staff, billable / available hours): 76.0%; 2.6 pp above PY (73.4%), favourable.**

- By grade, utilization: G1 75.0% (PY 72.2%); G2 79.6% (PY 76.9%); G3 80.1% (PY 76.9%)
- Average headcount: 2,008; 27.6 (1.4%) above PY (1,980)
- Attrition rate (annualised): 12.1%; 1.2 pp below PY (13.3%), favourable
- Leavers: 202; 17 (7.8%) fewer than PY (219); of these 187 voluntary and 15 restructuring (PY 197 voluntary and 22 restructuring)

## Table

| Grade | Avg headcount | Headcount PY | Hires | Leavers | of which restructuring | Attrition | Attrition PY | Utilization | Utilization PY | Overtime ratio |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Total** | **2,008** | **1,980** | **221** | **202** | **15** | **12.1%** | **13.3%** | **76.0%** | **73.4%** | **7.5%** |
| G1 | 315 | 328 | 44 | 44 | 2 | 16.8% | 23.4% | 75.0% | 72.2% | 8.9% |
| G2 | 518 | 508 | 63 | 46 | 4 | 10.7% | 15.6% | 79.6% | 76.9% | 9.5% |
| G3 | 512 | 505 | 61 | 58 | 5 | 13.6% | 11.4% | 80.1% | 76.9% | 7.5% |
| G4 | 398 | 395 | 32 | 32 | 3 | 9.6% | 10.0% | 75.0% | 72.5% | 6.1% |
| G5 | 264 | 244 | 21 | 22 | 1 | 10.0% | 3.9% | 62.5% | 60.6% | 3.7% |

_Fictional employee records, closed months. Headcount and FTE are monthly averages; attrition = leavers x 12 / months / average headcount; utilization and overtime use direct staff hours. Green / red = better / worse than PY._

## Chart

`hbar` - Utilization (direct staff) by grade - United States (YTD Oct 2026) ([interactive chart](18_utilization_rate_by_grade_in_the_united_states_t_chart.html))

## Filters, version and period used

- Scope: United States
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (YTD Oct 2026), PY (Jan 2025 - Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show attrition by role for United States this year
2. Show headcount, hires and leavers by month for United States this year
3. Which product lines in United States have the highest attrition this year?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_workforce",
      "arguments": {
        "org": "United States",
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
    "preprocess": 0.008,
    "plan": 0.0,
    "act": 0.091,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_employee.grade, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'United States') GROUP BY dim_employee.grade, fact_employee_month.month_key
```

```sql
SELECT dim_employee.grade, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'United States') GROUP BY dim_employee.grade, fact_employee_month.month_key
```
