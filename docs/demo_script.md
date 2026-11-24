# IRIS demo script (about 15 minutes)

Before the demo: `make landing` has run for today's as-of date, the UI is open on http://localhost:8501
(`make run`, or `make k8s-forward` for the cluster setup) and you are signed in. Use the persona *Group CFO*
and the model *rules (no LLM)* for instant answers, or a local LLM for written insights. Figures below are
what the current synthetic data returns (as of 2026-11-16).

## 1. About (1 min)

Open **About** in the top navigation.

- What IRIS is and why: dashboards can't anticipate every question, and every leader analyses
  differently.
- Scope: monthly P&L by organisation level, Actual, Budget, FC1-FC3, plus a current-month landing.
- How it works: governed definitions, secure data access, the AI chooses the query and never calculates
  numbers; the landing is a separate, tested calculation.
- The last closed month (Oct 2026) and the last landing refresh are read live.

## 2. Data Catalog (2 min)

Open **Data Catalog**.

- *Overview*: 5 regions, 11 countries, 8 product lines, 67 businesses, 106 BUs; first month Jan 2022, last
  closed month Oct 2026, next close 2026-12-05, landing month Nov 2026. Switch the heatmap to revenue.
- *Organisation*: click into the sunburst; search "Toronto".
- *Ratios*: both operating margins with their typical ranges by business type.
- *Landing*: method, pattern class per BU, and the measured backtest accuracy.
- *Data & sources*: the reconciliation badge (0 mismatches), lineage and rows per version.
- Click **Ask IRIS** on a card to show that every item leads into a question.

## 3. A catalog question in chat (1 min)

Ask *"Which countries are in scope?"* The answer lists the 11 countries as a table, mentions the Data
Catalog page and suggests follow-ups. It is answered from the catalog, never with SQL.

## 4. Sidebar filters (2 min)

In **Scope filters**, choose Country = Mexico (the product line, business and BU lists narrow to Mexico).
The chip "Filters: Country: Mexico" appears above the chat box.

- Ask *"How is operating profit YTD vs budget?"*: the answer is for Mexico; *Filters used* says
  "Scope: Mexico (from the sidebar filters)".
- Ask *"How is operating profit YTD vs budget for Canada?"*: the question wins; *Filters used* says
  "Scope: Canada (from your question)".
- Click **Clear filters**.

## 5. Persona and row-level security (1 min)

In **Settings**, switch the persona to *United States Country Head*. The scope filters now only offer the
United States.

- Ask *"Which countries are in scope?"*: only the United States.
- Ask *"How is operating profit YTD for Brazil?"*: a polite refusal, no data and no SQL.
- Switch back to *Group CFO*.

## 6. Margins (1 min)

Ask *"What is our profit % YTD?"* No base is named, so both margins are shown side by side: operating
margin on revenue 14.9% and on production 14.8% for Jan-Oct 2026, each 0.6 pp above last year and 0.6 pp
below budget. Ask *"What is the operating margin on revenue for Mexico YTD?"* to get only one.

## 7. November landing for the United States (2 min)

Ask *"What's the November landing for the United States?"*

- Billing P50 USD 35.2M with a P10-P90 range of USD 34.5M-36.7M: above budget (USD 33.8M) and last year
  (USD 30.6M), below FC3 (USD 36.4M).
- Point out the notes: landing month and as-of date, WIP = 0 so revenue = billing, monthly history only,
  and the measured backtest accuracy.
- The chart shows the year's trend with the landing marker and its P10-P90 bar, against PY and Budget.

## 8. Which BUs will miss budget? (1 min)

Click **New conversation** first: in the same conversation the question counts as a follow-up and keeps the
United States from step 7 (then it answers 7 of the 16 US BUs). Ask *"Which BUs are expected to miss budget
this month?"* 52 of 106 BUs land below budget at P50. The largest shortfall is CA-ENV-VAN-01 (Canada
Environmental Lab Testing, Vancouver): USD 1.4M against a budget of USD 1.7M. Click *Explain the landing for
CA-ENV-VAN-01* to show the four methods, their weights and the pattern class.

## 9. YTD margin including the landing (1 min)

Ask *"What will YTD MAOP margin be through November including the landing?"* January-October actuals plus
the November landing: operating margin on revenue 14.8% (P10-P90 14.7%-14.9%), 0.8 pp above last year,
0.5 pp below budget and in line with FC3; on production 14.7%. The bar chart shows the landing month
hatched.

## 10. Resume a conversation (2 min)

Click **New conversation** in the sidebar. The previous conversation is listed under *Conversations*
with its title. Click it: every answer comes back exactly as it was, without calling the model or the
database. Ask *"and for Canada?"*: the follow-up uses the restored context. Show the **⋯** menu (rename,
pin, delete) and mention that the last 10 conversations are kept per user.
