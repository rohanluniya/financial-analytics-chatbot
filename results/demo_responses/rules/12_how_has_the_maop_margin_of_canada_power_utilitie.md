# How has the MAOP margin of Canada Power & Utilities developed since 2022?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.17 s
- **Tool:** `get_trend` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**MAOP margin (on revenue) monthly trend for Canada · Power & Utilities, Jan 2022 - Oct 2026 (series: Actual, Actual R12M, Budget), USD.**

- Actual by calendar year: 2022 9.2% (full year), 2023 11.4% (full year), 2024 12.3% (full year), 2025 14.7% (full year), 2026 14.6% (Jan-Oct)
- Latest month Oct 2026: Actual 17.3%, Budget 19.9%
- Rolling 12-month MAOP margin (on revenue): Dec 2022 9.2% -> Oct 2026 14.5% (up 5.3 pp)

## Table

| Month | Actual | Actual R12M | Budget |
|:---|---:|---:|---:|
| Jan 2022 | 0.2% |  | 3.3% |
| Feb 2022 | 0.3% |  | 7.1% |
| Mar 2022 | 14.4% |  | 14.9% |
| Apr 2022 | 12.6% |  | 9.2% |
| May 2022 | 10.1% |  | 10.6% |
| Jun 2022 | 10.2% |  | 11.9% |
| Jul 2022 | 10.7% |  | 7.8% |
| Aug 2022 | (3.8%) |  | (9.0%) |
| Sep 2022 | 14.6% |  | 11.9% |
| Oct 2022 | 14.0% |  | 13.7% |
| Nov 2022 | 16.0% |  | 12.5% |
| Dec 2022 | 3.9% | 9.2% | 2.4% |
| Jan 2023 | 3.4% | 9.4% | 4.5% |
| Feb 2023 | 10.1% | 10.1% | 8.3% |
| Mar 2023 | 16.5% | 10.3% | 16.0% |
| Apr 2023 | 11.8% | 10.3% | 10.4% |
| May 2023 | 13.2% | 10.5% | 11.7% |
| Jun 2023 | 16.7% | 11.1% | 13.0% |
| Jul 2023 | 9.8% | 11.1% | 9.0% |
| Aug 2023 | (5.8%) | 10.9% | (7.6%) |
| Sep 2023 | 14.7% | 10.9% | 13.0% |
| Oct 2023 | 20.3% | 11.6% | 14.8% |
| Nov 2023 | 11.9% | 11.2% | 13.6% |
| Dec 2023 | 6.4% | 11.4% | 3.7% |
| Jan 2024 | 4.8% | 11.5% | 6.8% |
| Feb 2024 | 10.5% | 11.5% | 10.5% |
| Mar 2024 | 16.3% | 11.5% | 18.0% |
| Apr 2024 | 14.7% | 11.8% | 12.5% |
| May 2024 | 14.5% | 11.9% | 13.8% |
| Jun 2024 | 16.7% | 11.9% | 15.1% |
| Jul 2024 | 12.0% | 12.1% | 11.2% |
| Aug 2024 | (2.2%) | 12.2% | (5.0%) |
| Sep 2024 | 14.2% | 12.2% | 15.1% |
| Oct 2024 | 18.5% | 12.0% | 16.9% |
| Nov 2024 | 19.6% | 12.7% | 15.7% |
| Dec 2024 | 0.4% | 12.3% | 6.0% |
| Jan 2025 | 9.7% | 12.6% | 7.7% |
| Feb 2025 | 16.1% | 13.1% | 11.4% |
| Mar 2025 | 20.1% | 13.5% | 18.8% |
| Apr 2025 | 11.3% | 13.2% | 13.4% |
| May 2025 | 18.1% | 13.5% | 14.7% |
| Jun 2025 | 16.7% | 13.5% | 15.9% |
| Jul 2025 | 15.4% | 13.8% | 12.1% |
| Aug 2025 | 2.4% | 14.0% | (3.9%) |
| Sep 2025 | 15.1% | 14.1% | 15.9% |
| Oct 2025 | 19.0% | 14.2% | 17.7% |
| Nov 2025 | 17.7% | 14.0% | 16.5% |
| Dec 2025 | 10.3% | 14.7% | 6.9% |
| Jan 2026 | 10.8% | 14.7% | 10.3% |
| Feb 2026 | 11.7% | 14.4% | 13.8% |
| Mar 2026 | 18.1% | 14.2% | 21.0% |
| Apr 2026 | 16.3% | 14.6% | 15.8% |
| May 2026 | 19.1% | 14.7% | 17.0% |
| Jun 2026 | 13.7% | 14.4% | 18.2% |
| Jul 2026 | 16.4% | 14.5% | 14.5% |
| Aug 2026 | 0.8% | 14.4% | (1.0%) |
| Sep 2026 | 17.7% | 14.7% | 18.2% |
| Oct 2026 | 17.3% | 14.5% | 19.9% |

## Chart

`line` - MAOP margin (on revenue) - Canada · Power & Utilities (Jan 2022 - Oct 2026) ([interactive chart](12_how_has_the_maop_margin_of_canada_power_utilitie_chart.html))

## Filters, version and period used

- Scope: Canada · Power & Utilities
- Period: Jan 2022 - Oct 2026 (Jan 2022 - Oct 2026)
- Versions: Actual, Actual R12M, Budget
- Currency: USD at B26 (constant budget rate)
- As-of date: 2026-11-12 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)

## Follow-up questions

1. Why did MAOP margin (on revenue) change vs last year for Canada · Power & Utilities?
2. Rank businesss in Canada · Power & Utilities by MAOP margin (on revenue) this year
3. Compare Budget vs FC3 vs Actual for Canada · Power & Utilities

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "get_trend",
      "arguments": {
        "metric_or_ratio": "maop_margin_revenue",
        "org": "Canada \u00b7 Power & Utilities",
        "start": "2022-01",
        "end": "",
        "versions": [
          "Actual",
          "PY",
          "Budget"
        ]
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
    "preprocess": 0.01,
    "plan": 0.0,
    "act": 0.148,
    "write#1": 0.0
  }
}
```

```sql
SELECT fact_pnl.month_key, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Actual' AND fact_pnl.month_key BETWEEN 202201 AND 202610 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Power & Utilities') GROUP BY fact_pnl.month_key, fact_pnl.account_id
```

```sql
SELECT fact_pnl.month_key, fact_pnl.account_id, sum(fact_pnl.amount_usd) AS amount 
FROM fact_pnl JOIN dim_org ON fact_pnl.bu_id = dim_org.bu_id JOIN dim_version ON fact_pnl.version_id = dim_version.version_id 
WHERE dim_version.name = N'Budget' AND fact_pnl.month_key BETWEEN 202201 AND 202610 AND dim_org.l3_country IN (N'Canada') AND dim_org.l4_product_line IN (N'Power & Utilities') GROUP BY fact_pnl.month_key, fact_pnl.account_id
```
