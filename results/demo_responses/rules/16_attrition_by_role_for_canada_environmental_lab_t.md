# Attrition by role for Canada Environmental Lab Testing this year vs last year

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.11 s
- **Tool:** `get_workforce` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Attrition rate (annualised): 31.7%; 20.3 pp above PY (11.3%), unfavourable.**

- By role, highest attrition (annualised) first: Chemist 38.7% (PY 16.9%); Lab analyst 34.4% (PY 12.8%); Sample reception 34.0% (PY 21.3%)
- Average headcount: 353; 29.1 (7.6%) below PY (382)
- Leavers: 93; 57 (158.3%) more than PY (36); of these 32 voluntary and 61 restructuring (PY 34 voluntary and 2 restructuring)
- Hires: 47; in line with PY (47)
- Month with the most leavers: Apr 2026 (60, of which 58 restructuring)

## Table

| Role | Avg headcount | Headcount PY | Hires | Leavers | of which restructuring | Attrition | Attrition PY | Utilization | Utilization PY | Overtime ratio |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Total** | **353** | **382** | **47** | **93** | **61** | **31.7%** | **11.3%** | **67.4%** | **73.7%** | **4.5%** |
| Chemist | 31 | 35 | 8 | 10 | 6 | 38.7% | 16.9% | 67.6% | 73.9% | 4.2% |
| Lab analyst | 87 | 93 | 15 | 25 | 16 | 34.4% | 12.8% | 67.6% | 74.3% | 4.3% |
| Sample reception | 28 | 28 | 5 | 8 | 8 | 34.0% | 21.3% |  |  |  |
| Lab technician | 147 | 158 | 18 | 40 | 24 | 32.7% | 7.6% | 67.3% | 73.3% | 4.7% |
| Administration | 29 | 34 | 0 | 6 | 5 | 24.7% | 10.6% |  |  |  |
| Manager | 16 | 18 | 1 | 3 | 1 | 23.1% | 6.9% |  |  |  |
| Quality | 14 | 15 | 0 | 1 | 1 | 8.3% | 15.8% |  |  |  |

_Fictional employee records, closed months. Headcount and FTE are monthly averages; attrition = leavers x 12 / months / average headcount; utilization and overtime use direct staff hours. Green / red = better / worse than PY._

## Chart

`hbar` - Attrition (annualised) by role - Canada · Environmental Lab Testing (YTD Oct 2026) ([interactive chart](16_attrition_by_role_for_canada_environmental_lab_t_chart.html))

## Filters, version and period used

- Scope: Canada · Environmental Lab Testing
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (YTD Oct 2026), PY (Jan 2025 - Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show utilization by grade for Canada · Environmental Lab Testing this year
2. Show headcount, hires and leavers by month for Canada · Environmental Lab Testing this year
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
    "preprocess": 0.009,
    "plan": 0.0,
    "act": 0.089,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_employee.role, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_employee.role, fact_employee_month.month_key
```

```sql
SELECT dim_employee.role, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_employee.role, fact_employee_month.month_key
```
