# Which BUs have the highest attrition this year?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 1.39 s
- **Tool:** `get_workforce` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**Attrition rate (annualised): 13.7%; 0.4 pp below PY (14.1%), favourable.**

- By BU, highest attrition (annualised) first: CA-ENV-CAL-01 42.6% (PY 14.5%); CA-ENV-CAL-02 32.8% (PY 10.7%); CA-ENV-MTL-01 31.1% (PY 15.0%)
- Average headcount: 16,698; 254 (1.5%) above PY (16,444)
- Leavers: 1,911; 22 (1.1%) fewer than PY (1,933); of these 1,766 voluntary and 145 restructuring (PY 1,833 voluntary and 100 restructuring)
- Hires: 2,109; 34 (1.6%) fewer than PY (2,143)
- Month with the most leavers: Apr 2026 (254, of which 70 restructuring)

## Table

| BU | Avg headcount | Headcount PY | Hires | Leavers | of which restructuring | Attrition | Attrition PY | Utilization | Utilization PY | Overtime ratio |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Total** | **16,698** | **16,444** | **2,109** | **1,911** | **145** | **13.7%** | **14.1%** | **74.7%** | **74.4%** | **6.3%** |
| CA-ENV-CAL-01 | 45 | 50 | 11 | 16 | 7 | 42.6% | 14.5% | 64.9% | 70.9% | 5.0% |
| CA-ENV-CAL-02 | 84 | 90 | 12 | 23 | 14 | 32.8% | 10.7% | 69.6% | 78.1% | 4.6% |
| CA-ENV-MTL-01 | 73 | 80 | 7 | 19 | 14 | 31.1% | 15.0% | 68.7% | 75.4% | 4.0% |
| CA-ENV-TOR-01 | 63 | 67 | 10 | 15 | 11 | 28.7% | 8.9% | 67.7% | 72.3% | 3.9% |
| CA-ENV-VAN-01 | 87 | 95 | 7 | 20 | 15 | 27.5% | 8.9% | 65.4% | 70.5% | 4.9% |
| BR-MMI-BHZ-01 | 127 | 123 | 28 | 25 | 1 | 23.6% | 17.5% | 71.8% | 72.9% | 4.5% |
| MX-BNI-QRO-01 | 62 | 62 | 12 | 12 | 2 | 23.1% | 13.5% | 78.4% | 76.9% | 5.9% |
| CA-MMI-TOR-03 | 32 | 32 | 7 | 6 | 0 | 22.3% | 3.8% | 76.4% | 75.2% | 6.7% |
| MX-EPV-MEX-01 | 186 | 186 | 32 | 34 | 0 | 21.9% | 9.7% | 77.4% | 77.0% | 4.1% |
| BR-CER-BHZ-01 | 66 | 63 | 13 | 10 | 1 | 18.3% | 13.3% | 70.5% | 69.7% | 5.4% |

_Fictional employee records, closed months. Headcount and FTE are monthly averages; attrition = leavers x 12 / months / average headcount; utilization and overtime use direct staff hours. Green / red = better / worse than PY._

## Chart

`hbar` - Attrition (annualised) by BU - RL Group (YTD Oct 2026) ([interactive chart](19_which_bus_have_the_highest_attrition_this_year_chart.html))

## Filters, version and period used

- Scope: RL Group
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (YTD Oct 2026), PY (Jan 2025 - Oct 2025)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Show attrition by role for RL Group this year
2. Show utilization by grade for RL Group this year
3. Show headcount, hires and leavers by month for RL Group this year

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_workforce",
      "arguments": {
        "org": "",
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
    "act": 1.374,
    "write#1": 0.0
  }
}
```

```sql
SELECT dim_org.l6_bu, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202601 AND 202610 GROUP BY dim_org.l6_bu, fact_employee_month.month_key
```

```sql
SELECT dim_org.l6_bu, fact_employee_month.month_key, count(*) AS headcount, sum(fact_employee_month.fte) AS fte, sum(fact_employee_month.available_hours) AS available_hours, sum(fact_employee_month.billable_hours) AS billable_hours, sum(fact_employee_month.overtime_hours) AS overtime_hours, sum(CAST(fact_employee_month.is_hire AS INTEGER)) AS hires, sum(CAST(fact_employee_month.is_leaver AS INTEGER)) AS leavers, sum(CASE WHEN (dim_employee.leave_reason = N'Restructuring') THEN CAST(fact_employee_month.is_leaver AS INTEGER) ELSE 0 END) AS restructuring_leavers 
FROM fact_employee_month JOIN dim_employee ON fact_employee_month.employee_id = dim_employee.employee_id JOIN dim_org ON fact_employee_month.bu_id = dim_org.bu_id 
WHERE fact_employee_month.month_key BETWEEN 202501 AND 202510 GROUP BY dim_org.l6_bu, fact_employee_month.month_key
```
