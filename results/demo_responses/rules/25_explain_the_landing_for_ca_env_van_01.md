# Explain the landing for CA-ENV-VAN-01

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.09 s
- **Tool:** `explain_landing` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**How the Nov 2026 billing landing for CA-ENV-VAN-01 is calculated (as of 2026-11-16): each BU's billing is forecast with four methods on monthly history (working-day adjusted) and combined with weights learned from each method's recent errors; costs follow the billing landing (intragroup, subcontracting and other costs as ratios to billing), personnel uses a seasonality-adjusted 3-month run-rate and functional lines come from the latest forecast.**

- Same month last year x recent growth: USD 1.3M, weight 26%, recent WAPE 8.1%
- Trailing 12 months x seasonal index: USD 1.4M, weight 22%, recent WAPE 11.1%
- Latest forecast x the BU's forecast accuracy: USD 1.4M, weight 20%, recent WAPE 11.6%
- Exponential smoothing (ETS): USD 1.4M, weight 32%, recent WAPE 6.6%
- Latest forecast as published: USD 1.5M
- Landing P50 (weighted): USD 1.4M

_WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data. Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time._

## Table

| Method | Billing prediction | Weight in the landing | Recent error of this method (WAPE) |
|:---|---:|---:|---:|
| Same month last year x recent growth | 1,340 | 26.0% | 8.1% |
| Trailing 12 months x seasonal index | 1,376 | 21.6% | 11.1% |
| Latest forecast x the BU's forecast accuracy | 1,429 | 20.1% | 11.6% |
| Exponential smoothing (ETS) | 1,418 | 32.2% | 6.6% |
| Latest forecast as published | 1,468 |  |  |
| **IRIS landing (weighted ensemble)** | **1,391** | **100.0%** |  |

_USD k · Billing landing by method; weights are learned per BU from recent errors and shrunk toward the BU's pattern class._

## Chart

`bar` - Billing landing by method, Nov 2026 - CA-ENV-VAN-01 ([interactive chart](25_explain_the_landing_for_ca_env_van_01_chart.html))

## Filters, version and period used

- Scope: CA-ENV-VAN-01
- Period: Nov 2026 (landing) (Nov 2026)
- Versions: Landing (P50, P10-P90)
- Currency: USD at constant budget rate
- As-of date: 2026-11-16 · row-level security: SQL Server SECURITY POLICY (SESSION_CONTEXT)
- Note: WIP is 0 in the landing month, so the revenue landing equals the billing landing. The landing uses monthly history only (closed-month actuals, Budget and forecasts); there is no intra-month data.
- Note: Backtest (measured): group billing error (WAPE) 1.0% over the last 24 closed months, vs 2.3% for the latest forecast as published, BU actuals fell inside P10-P90 74% of the time.

## Follow-up questions

1. What's the Nov landing for CA-ENV-VAN-01?
2. Which BUs in CA-ENV-VAN-01 are expected to miss budget this month?
3. What data do you use?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "explain_landing",
      "arguments": {
        "org": "CA-ENV-VAN-01"
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
    "preprocess": 0.005,
    "plan": 0.0,
    "act": 0.083,
    "write#1": 0.0
  }
}
```
