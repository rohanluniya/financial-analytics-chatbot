# now for the United States

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.08 s
- **Tool:** `get_workforce` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Attrition rate (annualised): 11.6%; 8.4 pp below PY (19.9%), favourable.**

- By role, highest attrition (annualised) first: Lab analyst 35.8% (PY 14.1%); Lab technician 7.8% (PY 9.4%); 5 other roles 0.0%
- Average headcount: 31.1; 1.0 (3.3%) above PY (30.1)
- Leavers: 3; 2 fewer than PY (5); of these 3 voluntary and 0 restructuring (PY 3 voluntary and 2 restructuring)
- Hires: 4; 2 fewer than PY (6)
- Month with the most leavers: Feb 2026 (1)

## Table

| Role | Avg headcount | Headcount PY | Hires | Leavers | of which restructuring | Attrition | Attrition PY | Utilization | Utilization PY | Overtime ratio |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Total** | **31** | **30** | **4** | **3** | **0** | **11.6%** | **19.9%** | **70.7%** | **70.7%** | **5.2%** |
| Lab analyst | 6.7 | 8.5 | 1 | 2 | 0 | 35.8% | 14.1% | 71.1% | 70.6% | 4.6% |
| Lab technician | 15 | 13 | 3 | 1 | 0 | 7.8% | 9.4% | 70.1% | 70.3% | 5.1% |
| Administration | 1.0 | 0.9 | 0 | 0 | 0 | 0.0% | 133.3% |  |  |  |
| Chemist | 1.0 | 1.0 | 0 | 0 | 0 | 0.0% | 0.0% | 76.5% | 75.9% | 9.4% |
| Manager | 1.0 | 1.0 | 0 | 0 | 0 | 0.0% | 0.0% |  |  |  |
| Quality | 1.0 | 1.4 | 0 | 0 | 0 | 0.0% | 85.7% |  |  |  |
| Sample reception | 5.0 | 4.6 | 0 | 0 | 0 | 0.0% | 26.1% |  |  |  |

_Fictional employee records, closed months. Headcount and FTE are monthly averages; attrition = leavers x 12 / months / average headcount; utilization and overtime use direct staff hours. Green / red = better / worse than PY._

## Chart

`hbar` - Attrition (annualised) by role - United States · Environmental Lab Testing (YTD Oct 2026) ([interactive chart](17_now_for_the_united_states_chart.html))

## Filters, version and period used

- Scope: United States · Environmental Lab Testing
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (YTD Oct 2026), PY (Jan 2025 - Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show utilization by grade for United States · Environmental Lab Testing this year
2. Show headcount, hires and leavers by month for United States · Environmental Lab Testing this year
3. Which BUs in United States · Environmental Lab Testing have the highest attrition this year?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_workforce",
      "arguments": {
        "org": "United States \u00b7 Environmental Lab Testing",
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
    "act": 0.066,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_employee.role, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202601 AND 202610 AND dim_org.l3_country IN (N'United States') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_employee.role, fact_employee_month.month_key
```

```sql
SELECT dim_employee.role, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202501 AND 202510 AND dim_org.l3_country IN (N'United States') AND dim_org.l4_product_line IN (N'Environmental Lab Testing') GROUP BY dim_employee.role, fact_employee_month.month_key
```
