# Which countries are in scope?

- **Persona:** Group CFO
- **Model:** `rules` · **status:** ok · **latency:** 0.03 s
- **Tool:** `describe_catalog` (chosen by `router_fallback`) · **numeric guardrail:** n/a (no LLM)

## Answer

**11 countries in your scope, with monthly P&L from Jan 2022 to Oct 2026 (the last closed month).**

Countries (11): Argentina; Brazil; Canada; Chile; Colombia; Ecuador; Mexico; Paraguay; Peru; United States; Uruguay.

## Table

| Country | Region | Product lines | Businesses | BUs |
|:---|---:|---:|---:|---:|
| Argentina | Southern South America | 3 | 4 | 7 |
| Brazil | BPU | 6 | 11 | 29 |
| Canada | US & Canada | 6 | 12 | 15 |
| Chile | Southern South America | 3 | 6 | 11 |
| Colombia | Northern South America | 3 | 3 | 5 |
| Ecuador | Northern South America | 2 | 3 | 4 |
| Mexico | Mexico | 6 | 9 | 11 |
| Paraguay | BPU | 2 | 2 | 2 |
| Peru | Northern South America | 3 | 3 | 4 |
| United States | US & Canada | 7 | 12 | 16 |
| Uruguay | BPU | 2 | 2 | 2 |

_Countries in your scope (live from the database, row-level security applied). See the Data Catalog page for details._

## Chart

`hbar` - BUs by countrie ([interactive chart](28_which_countries_are_in_scope_chart.html))

## Filters, version and period used

- Scope: your scope
- Period: catalog ()
- Versions: -
- Currency: USD at -
- As-of date: 2026-11-16 · row-level security: -

## Follow-up questions

1. How is Argentina doing YTD vs budget?
2. Rank countries by operating margin on revenue YTD
3. What's the Nov landing for Argentina?

## Diagnostics

```json
{
  "tool_calls": [
    {
      "name": "describe_catalog",
      "arguments": {
        "kind": "countries",
        "parent_filter": ""
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
    "act": 0.018,
    "write#1": 0.0
  }
}
```
