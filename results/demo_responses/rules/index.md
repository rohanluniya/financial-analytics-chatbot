# Demo responses

Model `rules` · backend `mssql` · as-of date 2026-11-16 · 29 questions in 11 s · median latency 0.2 s

Each file contains the insight text, the finance table, the chart, the filters / version / period used, three follow-up questions and the SQL that produced the numbers.

| # | Persona | Question | Status | Tool | Chart | Guardrail | Latency (s) |
|---:|:---|:---|:---|:---|:---|:---|---:|
| 1 | Group CFO | [How is operating profit YTD vs last year and budget for the United States?](01_how_is_operating_profit_ytd_vs_last_year_and_bud.md) | ok | `get_pnl` | waterfall | n/a (no LLM) | 0.51 |
| 2 | Group CFO | [now for Canada](02_now_for_canada.md) | ok | `get_pnl` | waterfall | n/a (no LLM) | 0.28 |
| 3 | Group CFO | [Show personnel cost as % of revenue trend for Environmental Lab Testing since 2023](03_show_personnel_cost_as_of_revenue_trend_for_envi.md) | ok | `get_trend` | line | n/a (no LLM) | 0.13 |
| 4 | Group CFO | [Why did Canada Environmental Lab Testing margin drop in 2026?](04_why_did_canada_environmental_lab_testing_margin.md) | ok | `variance_drivers` | waterfall | n/a (no LLM) | 0.18 |
| 5 | Group CFO | [Top 5 BUs by operating margin in US & Canada this year](05_top_5_bus_by_operating_margin_in_us_canada_this.md) | ok | `rank_entities` | hbar | n/a (no LLM) | 0.09 |
| 6 | Group CFO | [Compare Budget vs FC2 vs Actual for Chile Metals & Minerals](06_compare_budget_vs_fc2_vs_actual_for_chile_metals.md) | ok | `compare_versions` | grouped_bar | n/a (no LLM) | 0.12 |
| 7 | Group CFO | [Break down direct staff costs for US Elevators & Pressure Vessels in March 2025](07_break_down_direct_staff_costs_for_us_elevators_p.md) | ok | `variance_drivers` | stacked_bar | n/a (no LLM) | 0.46 |
| 8 | Group CFO | [What happened to WIP in Mexico Buildings & Infrastructure this year?](08_what_happened_to_wip_in_mexico_buildings_infrast.md) | ok | `get_trend` | line | n/a (no LLM) | 0.13 |
| 9 | Group CFO | [Subcontracting cost by product line YTD vs PY](09_subcontracting_cost_by_product_line_ytd_vs_py.md) | ok | `rank_entities` | hbar | n/a (no LLM) | 0.33 |
| 10 | Group CFO | [Show the operational profitability cockpit for Canada](10_show_the_operational_profitability_cockpit_for_c.md) | ok | `get_kpi_cockpit` | combo | n/a (no LLM) | 0.48 |
| 11 | Group CFO | [What is the utilization rate in Mexico vs budget?](11_what_is_the_utilization_rate_in_mexico_vs_budget.md) | ok | `get_ratio` | bar | n/a (no LLM) | 0.16 |
| 12 | Group CFO | [How has the operating margin of Canada Power & Utilities developed since 2022?](12_how_has_the_operating_margin_of_canada_power_uti.md) | ok | `get_trend` | line | n/a (no LLM) | 0.14 |
| 13 | Group CFO | [Which countries have the lowest operating margin this year?](13_which_countries_have_the_lowest_operating_margin.md) | ok | `rank_entities` | hbar | n/a (no LLM) | 0.33 |
| 14 | Group CFO | [why is the first one so low?](14_why_is_the_first_one_so_low.md) | ok | `variance_drivers` | waterfall | n/a (no LLM) | 0.15 |
| 15 | Group CFO | [Headcount, hires and leavers by month for Canada Environmental Lab Testing this year](15_headcount_hires_and_leavers_by_month_for_canada.md) | ok | `get_workforce` | grouped_bar | n/a (no LLM) | 0.19 |
| 16 | Group CFO | [Attrition by role for Canada Environmental Lab Testing this year vs last year](16_attrition_by_role_for_canada_environmental_lab_t.md) | ok | `get_workforce` | hbar | n/a (no LLM) | 0.11 |
| 17 | Group CFO | [now for the United States](17_now_for_the_united_states.md) | ok | `get_workforce` | hbar | n/a (no LLM) | 0.08 |
| 18 | Group CFO | [Utilization rate by grade in the United States this year](18_utilization_rate_by_grade_in_the_united_states_t.md) | ok | `get_workforce` | hbar | n/a (no LLM) | 0.11 |
| 19 | Group CFO | [Which BUs have the highest attrition this year?](19_which_bus_have_the_highest_attrition_this_year.md) | ok | `get_workforce` | hbar | n/a (no LLM) | 1.39 |
| 20 | United States Country Head | [How is operating profit YTD for Brazil?](20_how_is_operating_profit_ytd_for_brazil.md) | refusal | `-` | none | n/a | 0.01 |
| 21 | United States Country Head | [How is the whole group doing this year vs budget?](21_how_is_the_whole_group_doing_this_year_vs_budget.md) | ok | `get_pnl` | waterfall | n/a (no LLM) | 0.21 |
| 22 | Environmental Lab Testing PL Leader | [Rank countries by operating margin this year](22_rank_countries_by_operating_margin_this_year.md) | ok | `rank_entities` | hbar | n/a (no LLM) | 0.13 |
| 23 | Group CFO | [What's the November landing for the United States?](23_what_s_the_november_landing_for_the_united_state.md) | ok | `get_landing` | landing_trend | n/a (no LLM) | 0.38 |
| 24 | Group CFO | [Which BUs are expected to miss budget this month?](24_which_bus_are_expected_to_miss_budget_this_month.md) | ok | `rank_landing` | hbar | n/a (no LLM) | 2.61 |
| 25 | Group CFO | [Explain the landing for CA-ENV-VAN-01](25_explain_the_landing_for_ca_env_van_01.md) | ok | `explain_landing` | bar | n/a (no LLM) | 0.09 |
| 26 | Group CFO | [What will YTD MAOP margin be through November including the landing?](26_what_will_ytd_maop_margin_be_through_november_in.md) | ok | `get_ytd_with_landing` | ytd_bars | n/a (no LLM) | 0.33 |
| 27 | Group CFO | [What is our profit % YTD?](27_what_is_our_profit_ytd.md) | ok | `get_ratio` | grouped_bar | n/a (no LLM) | 0.21 |
| 28 | Group CFO | [Which countries are in scope?](28_which_countries_are_in_scope.md) | ok | `describe_catalog` | hbar | n/a (no LLM) | 0.03 |
| 29 | United States Country Head | [Which countries are in scope?](29_which_countries_are_in_scope.md) | ok | `describe_catalog` | none | n/a (no LLM) | 0.03 |
