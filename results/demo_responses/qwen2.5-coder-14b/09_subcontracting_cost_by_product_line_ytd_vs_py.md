# Subcontracting cost by product line YTD vs PY

- **Persona:** Group CFO
- **Model:** `ollama/qwen2.5-coder:14b` · **status:** ok · **latency:** 28.42 s
- **Tool:** `rank_entities` (chosen by `llm_text`) · **numeric guardrail:** passed

## Answer

USD 108.2M, USD 4.4M (4.2%) higher than PY (USD 103.9M), unfavourable. The increase is driven by higher subcontracting costs in Buildings & Infrastructure (+USD 1.8M, +4.2%), Industry & Energy (+USD 1.0M, +3.8%), Power & Utilities (+USD 445k, +3.7%), Certification & Sustainability (+USD 464k, +7.3%), Metals & Minerals (+USD 245k, +6.3%), Elevators & Pressure Vessels (+USD 170k, +4.6%), and Consumer Products (+USD 119k, +4.8%).

- Rank 1: Buildings & Infrastructure USD 43.5M (PY USD 41.8M, +USD 1.8M, +4.2%)
- Rank 2: Industry & Energy USD 28.6M (PY USD 27.6M, +USD 1.0M, +3.8%)
- Rank 3: Power & Utilities USD 12.3M (PY USD 11.9M, +USD 445k, +3.7%)

## Table

| Rank | Product line | Actual | PY | Var | Var % |
|:---|---:|---:|---:|---:|---:|
| 1 | Buildings & Infrastructure | 43,538 | 41,772 | 1,766 | 4.2% |
| 2 | Industry & Energy | 28,608 | 27,563 | 1,045 | 3.8% |
| 3 | Power & Utilities | 12,330 | 11,885 | 445 | 3.7% |
| 4 | Certification & Sustainability | 6,784 | 6,319 | 464 | 7.3% |
| 5 | Environmental Lab Testing | 6,380 | 6,281 | 99 | 1.6% |
| 6 | Metals & Minerals | 4,153 | 3,908 | 245 | 6.3% |
| 7 | Elevators & Pressure Vessels | 3,874 | 3,704 | 170 | 4.6% |
| 8 | Consumer Products | 2,582 | 2,464 | 119 | 4.8% |

_USD k_

## Chart

`hbar` - External subcontracting by Product line - RL Group (YTD Oct 2026) ([interactive chart](09_subcontracting_cost_by_product_line_ytd_vs_py_chart.html))

## Filters, version and period used

- Scope: RL Group
- Period: YTD Oct 2026 (Jan 2026 - Oct 2026)
- Versions: Actual (Actual, YTD Oct 2026), PY (Actual, YTD Oct 2025)
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why is Buildings & Infrastructure where it is on External subcontracting?
2. Show the External subcontracting trend for Buildings & Infrastructure since 2025
3. Show the bottom 5 Product lines by External subcontracting in RL Group instead

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "rank_entities",
      "arguments": {
        "metric_or_ratio": "subcontracting",
        "org_level": "l4_product_line",
        "parent_filter": "(user default scope)",
        "period": "YTD Oct 2026",
        "top_n": 0
      }
    }
  ],
  "llm_calls": [
    {
      "step": "plan",
      "latency": 9.05,
      "usage": {
        "prompt_tokens": 2735,
        "completion_tokens": 72
      },
      "native_tool_call": false
    },
    {
      "step": "write#1",
      "latency": 19.05,
      "usage": {
        "prompt_tokens": 763,
        "completion_tokens": 164
      }
    }
  ],
  "guardrail": {
    "ok": true,
    "template": false,
    "history": [
      {
        "attempt": 1,
        "ok": true,
        "unsupported": [],
        "checked": 18
      }
    ],
    "unsupported": []
  },
  "errors": [],
  "timings": {
    "preprocess": 0.006,
    "plan": 9.051,
    "act": 0.307,
    "write#1": 19.051
  }
}
```

```sql
SELECT dim_org.l4_product_line, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202601 AND 202610 GROUP BY dim_org.l4_product_line, fact_pnl.account_id
```

```sql
SELECT dim_org.l4_product_line, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202501 AND 202510 GROUP BY dim_org.l4_product_line, fact_pnl.account_id
```
