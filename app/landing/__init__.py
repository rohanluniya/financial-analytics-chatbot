"""Current-month landing: expected month-end of the open month (the month after the last closed month).

Deterministic Python, never the LLM. Monthly data only: closed-month actuals, Budget and FC1-FC3
(no daily billing, no intra-month curves). WIP is 0 in the landing month, so revenue = billing.
"""
