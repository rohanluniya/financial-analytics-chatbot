# Demo responses

Model `ollama/qwen2.5-coder:14b` · backend `mssql` · as-of date 2026-11-12 · 17 questions in 442 s · median latency 28.4 s

Each file contains the insight text, the finance table, the chart, the filters / version / period used, three follow-up questions and the SQL that produced the numbers.

| # | Persona | Question | Status | Tool | Chart | Guardrail | Latency (s) |
|---:|:---|:---|:---|:---|:---|:---|---:|
| 1 | Group CFO | [How is MAOP YTD vs last year and budget for the United States?](01_how_is_maop_ytd_vs_last_year_and_budget_for_the.md) | ok | `get_pnl` | waterfall | passed | 37.21 |
| 2 | Group CFO | [now for Canada](02_now_for_canada.md) | ok | `get_pnl` | waterfall | passed | 37.48 |
| 3 | Group CFO | [Show personnel cost as % of revenue trend for Environmental Lab Testing since 2023](03_show_personnel_cost_as_of_revenue_trend_for_envi.md) | ok | `get_trend` | line | passed | 35.93 |
| 4 | Group CFO | [Why did Brazil Environmental Lab Testing margin drop in 2026?](04_why_did_brazil_environmental_lab_testing_margin.md) | ok | `variance_drivers` | waterfall | passed | 27.8 |
| 5 | Group CFO | [Top 5 BUs by MAOP margin in US & Canada this year](05_top_5_bus_by_maop_margin_in_us_canada_this_year.md) | ok | `rank_entities` | hbar | passed | 22.38 |
| 6 | Group CFO | [Compare Budget vs FC2 vs Actual for Chile Metals & Minerals](06_compare_budget_vs_fc2_vs_actual_for_chile_metals.md) | ok | `compare_versions` | grouped_bar | passed | 21.31 |
| 7 | Group CFO | [Break down 7A personnel cost for US Elevators & Pressure Vessels in March 2025](07_break_down_7a_personnel_cost_for_us_elevators_pr.md) | ok | `variance_drivers` | stacked_bar | passed | 22.87 |
| 8 | Group CFO | [What happened to WIP in Mexico Buildings & Infrastructure this year?](08_what_happened_to_wip_in_mexico_buildings_infrast.md) | ok | `get_trend` | line | passed | 24.44 |
| 9 | Group CFO | [Subcontracting cost by product line YTD vs PY](09_subcontracting_cost_by_product_line_ytd_vs_py.md) | ok | `rank_entities` | hbar | passed | 28.42 |
| 10 | Group CFO | [Show the operational profitability cockpit for Canada](10_show_the_operational_profitability_cockpit_for_c.md) | ok | `get_kpi_cockpit` | combo | passed after removing unsupported sentences | 33.99 |
| 11 | Group CFO | [What is the utilization rate in Mexico vs budget?](11_what_is_the_utilization_rate_in_mexico_vs_budget.md) | ok | `get_ratio` | bar | passed | 13.7 |
| 12 | Group CFO | [How has the MAOP margin of Canada Power & Utilities developed since 2022?](12_how_has_the_maop_margin_of_canada_power_utilitie.md) | ok | `get_trend` | line | templated fallback | 31.53 |
| 13 | Group CFO | [Which countries have the lowest MAOP margin this year?](13_which_countries_have_the_lowest_maop_margin_this.md) | ok | `rank_entities` | hbar | passed | 17.73 |
| 14 | Group CFO | [why is the first one so low?](14_why_is_the_first_one_so_low.md) | ok | `variance_drivers` | waterfall | passed | 24.39 |
| 15 | United States Country Head | [How is MAOP YTD for Brazil?](15_how_is_maop_ytd_for_brazil.md) | refusal | `-` | none | n/a | 0.01 |
| 16 | United States Country Head | [How is the whole group doing this year vs budget?](16_how_is_the_whole_group_doing_this_year_vs_budget.md) | ok | `get_pnl` | waterfall | passed | 30.62 |
| 17 | Environmental Lab Testing PL Leader | [Rank countries by MAOP margin this year](17_rank_countries_by_maop_margin_this_year.md) | ok | `rank_entities` | hbar | passed | 31.15 |
