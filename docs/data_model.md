# Data model

A star schema in SQL Server 2022 (`sql/schema.sql`). A DuckDB copy with the same tables and
views (`scripts/export_duckdb.py`) supports a laptop demo. The data is synthetic
and seeded (`config/settings.yaml`), so every run produces the same numbers. Company, people, codes
and figures are fictional.

## Storage rules

- **Signed amounts.** Revenue is positive and cost is negative, in USD at a constant budget rate.
- **Leaf accounts only.** Fact rows exist only for leaf accounts. Every line, subtotal and ratio is computed from leaves at query time.
- **Versions in one fact table.** Actual, Budget, FC1, FC2 and FC3 sit in the same table. PY (prior year) is not stored: it is Actual shifted back 12 months.
- **Forecasts.** FCn holds actuals for the first months of the year and a reforecast for the rest. FC1 = 4 + 8, FC2 = 8 + 4, FC3 = 9 + 3. A forecast becomes available after the close of its last actual month, which is the 5th of the following month.
- **Last closed month.** With the as-of date 2026-11-16, the last closed month is October 2026. Actuals stop there; November 2026 is the open (landing) month.
- **Neutral labels.** Line and account names carry no codes or line numbers. Line numbers and account codes are internal keys only.

## Tables

| Table | Rows | Content |
|---|---:|---|
| `dim_org` | 106 | Org hierarchy: L1 group > L2 region > L3 country > L4 product line (sector) > L5 business (sector + city) > L6 BU (e.g. `US-EPV-DEN-01`), plus business type, city and SCD2 validity columns |
| `dim_account` | 57 | General-ledger chart of accounts: internal line key, line name, group (direct / indirect staff costs), leaf account, leaf/subtotal flags, natural sign, favourable direction, display order |
| `dim_version` | 5 | Actual, Budget, FC1, FC2, FC3, with the number of actual months in each forecast |
| `dim_period` | 60 | Jan 2022 – Dec 2026: year, quarter, month, close date, closed flag |
| `fact_pnl` | 1,168,756 | month × BU × leaf account × version → `amount_usd` (DECIMAL(18,2), signed) |
| `fact_stats` | 31,588 | month × BU × version → FTE, headcount, direct FTE, billable / available / overtime hours |
| `dim_employee` | 27,294 | Fictional employees, codes only (`E100123`): BU, role, grade G1–G5, staff type (direct / indirect), FTE %, hire and leave date, leave reason (voluntary / restructuring). No names or personal attributes |
| `fact_employee_month` | 937,504 | employee × closed month → BU, FTE, available / billable / overtime hours (direct staff only), hire and leaver flags |
| `app_user` | 3 | Demo personas |
| `user_org_access` | 3 | Org-level grants per persona (row-level security) |
| `dim_calendar` | 20,086 | date × country → working day (Monday-Friday minus public holidays from the `holidays` package) |
| `working_days` | 660 | month × country → number of working days |
| `fact_landing` | 1,590 | landing snapshot × open month × BU × measure → P10 / P50 / P90, method weights, pattern class |
| `fact_landing_leaf` | 3,286 | landing snapshot × open month × BU × leaf account → P50 amount (adds up to the BU's lines) |
| `landing_method`, `landing_bu_profile`, `landing_residual`, `landing_run` | 530 / 106 / 2,544 / 1 | Per-method predictions and weights, BU profiles, past errors for the ranges, one row per landing run |
| `landing_backtest_metric` | 836 | Measured backtest accuracy by scope, measure, method and metric (read by the Data Catalog and the answers) |
| `landing_mtd_snapshot` | 0 | Optional month-to-date billing, used only when `landing.mtd_snapshot_enabled` is true |
| `app.app_conversation`, `app.app_message`, `app.app_conversation_state` | per user | Conversation history (last 10 per user), in the separate `app` schema that the application login may write |

`fact_pnl` rows per version: Actual 227,476 (58 closed months); Budget, FC1, FC2 and FC3 235,320 each (60 months).

## Management P&L lines

| Line | Definition |
|---|---|
| Billing | external billing, credit notes |
| WIP & deferred income | WIP change, deferred income change |
| **REVENUE** | Billing + WIP & deferred income |
| Intragroup revenue | leaf |
| Intragroup subcontracting | leaf (cost) |
| **PRODUCTION** | Revenue + intragroup revenue + intragroup subcontracting (production is not revenue) |
| Personnel costs | direct staff costs (salaries, bonus, overtime, social security, pension, other) and indirect staff costs (salaries, bonus, social security, other) |
| External subcontracting | external subcontractors, temporary staff |
| Other costs | contract expenses, rent & utilities, depreciation, travel & living, vehicles, IT & telecom, lab consumables, insurance, miscellaneous |
| Functional cost recharges | leaf |
| **GROSS PROFIT** | Production + personnel + subcontracting + other costs + functional cost recharges |
| Functional costs | country functions, region functions, HQ allocation |
| **OPERATING PROFIT** | Gross profit + functional costs |
| Other operating expenses | restructuring, amortisation of acquired intangibles, other non-recurring |
| **EBIT** | Operating profit + other operating expenses |
| Financial result | net interest, FX result |
| Income taxes | leaf |
| **NET INCOME** | EBIT + financial result + income taxes |

## Statistics and KPIs

- **Stocks** (FTE, headcount, direct FTE) are averaged over the months of the period and summed over BUs.
- **Flows** (billable, available and overtime hours) are summed.
- **KPI cockpit** ("Operational Profitability – Direct Margin Drivers"):
  - direct margin = (production − direct staff costs) / production
  - production
  - direct staff costs
  - utilization rate = billable / available hours
  - production per billable hour
  - production per FTE (annualised)
  - overtime ratio
  - production hourly cost
  - direct staff costs / production
  - gross margin
  - operating margin

  Every KPI is shown MTD and YTD, vs LY and vs Budget.

## Employee records

- One row per employee and closed month (Jan 2022 – Oct 2026). Per BU and month, the rows add up exactly to the Actual BU statistics in `fact_stats` (headcount = rows, FTE, hours); `scripts/reconcile.py` checks this.
- Hours exist for direct staff only; indirect staff have 0 available and billable hours.
- A hire is an employee's first month on payroll, a leaver the last month. Leavers are voluntary (monthly probability by region and grade) or restructuring (when a BU's headcount falls).
- Workforce figures: average headcount and FTE over the months of the period; attrition rate (annualised) = leavers × 12 / months / average headcount; utilization = billable / available hours.

## Views

`sql/views.sql` defines the reporting views: `v_org`, `v_account`, `v_period`, `v_version`,
`v_pnl_leaf` and `v_pnl` (leaf rows plus subtotal membership), `v_stats`, `v_employee` and
`v_employee_month`.

- The agent's fallback tool `run_readonly_sql` may only read these views.
- The same views are replayed on DuckDB.

## Row-level security

Row-level security is enforced in two places:

- **SQL Server.**
  - `sql/rls.sql` creates `rls.fn_org_access` and a SECURITY POLICY on `fact_pnl`, `fact_stats`, `dim_employee`, `fact_employee_month` and every landing table with a BU (`fact_landing`, `fact_landing_leaf`, `landing_method`, `landing_bu_profile`, `landing_residual`, `landing_mtd_snapshot`).
  - Rows are filtered by `SESSION_CONTEXT('user_id')`, which the app sets read-only on every connection.
  - The app connects as the least-privilege login `iris_reader`, which has SELECT only on the data and may write only its conversation history in the `app` schema. The admin login is used only by the loader and the landing batch.
- **Semantic layer.**
  - Applies the same rules before querying (`app/semantic/access.py`), so it can explain a refusal or a narrowed scope politely.
  - On DuckDB this is the only enforcement.

| Persona | `user_id` | Access |
|---|---|---|
| Group CFO | `group_cfo` | whole group |
| United States Country Head | `us_country_head` | `l3_country = United States` |
| Environmental Lab Testing PL Leader | `env_pl_leader` | `l4_product_line = Environmental Lab Testing` (Canada and one US unit) |
