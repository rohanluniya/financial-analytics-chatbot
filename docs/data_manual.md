# IRIS data manual

Generated from the live database and `app/semantic/metrics.yaml` by `make data-manual`; the Data Catalog page shows the same content, filtered by each user's access. Synthetic data generated for this prototype; structure mirrors the target model.

## Coverage

- Organisation: 5 regions, 11 countries, 8 product lines, 67 businesses, 106 business units (BUs).
- P&L: 12 P&L lines over 37 leaf accounts, monthly, in USD.
- Months: Jan 2022 to Oct 2026 (last closed month, as of 2026-11-16); the next close is 2026-12-05.
- Landing month: Nov 2026; last landing refresh: 2026-11-17 00:17 (as of 2026-11-16).

## Organisation

| Region | Countries | Businesses | BUs |
|---|---|---|---|
| BPU | 3 | 15 | 33 |
| Mexico | 1 | 9 | 11 |
| Northern South America | 3 | 9 | 13 |
| Southern South America | 2 | 10 | 18 |
| US & Canada | 2 | 24 | 31 |


| Country | Region | Product lines | Businesses | BUs |
|---|---|---|---|---|
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


| Product line | Business type | Countries | Businesses | BUs |
|---|---|---|---|---|
| Buildings & Infrastructure | infrastructure | 11 | 15 | 22 |
| Certification & Sustainability | certification | 7 | 9 | 13 |
| Consumer Products | laboratory | 2 | 4 | 5 |
| Elevators & Pressure Vessels | inspection | 4 | 5 | 9 |
| Environmental Lab Testing | laboratory | 2 | 5 | 6 |
| Industry & Energy | industry | 9 | 18 | 28 |
| Metals & Minerals | laboratory | 5 | 7 | 16 |
| Power & Utilities | industry | 3 | 4 | 7 |


## P&L lines and accounts

Names only; subtotals are computed from the accounts.

| P&L line | Accounts | Sign | Favourable when | Also understood as |
|---|---|---|---|---|
| Billing | External billing, Credit notes | Revenue / income | higher | billing, billings, invoicing, invoiced |
| WIP & deferred income | WIP change, Deferred income change | Revenue / income | higher | wip, wip and ui, wip ui, wip and deferred income |
| Intragroup revenue | - | Revenue / income | higher | intragroup revenue, intra-group revenue, intercompany revenue, ic revenue |
| Intragroup subcontracting | - | Cost | lower | intragroup subcontracting, intra-group subcontracting, intercompany subcontracting, ic subcontracting |
| Personnel costs | Direct staff salaries, Direct staff bonus, Direct staff overtime, Direct staff social security, Direct staff pension, Direct staff other costs, Indirect staff salaries, Indirect staff bonus, Indirect staff social security, Indirect staff other costs | Cost | lower | personnel charges, personnel cost, personnel costs, personnel |
| External subcontracting | External subcontractors, Temporary staff | Cost | lower | external subcontracting, subcontracting, subcontracting cost, subcontracting costs |
| Other costs | Contract expenses, Rent & utilities, Depreciation, Travel & living, Vehicles, IT & telecom, Lab consumables, Insurance, Miscellaneous costs | Cost | lower | other costs, other cost, other direct costs |
| Functional cost recharges | - | Revenue / income | higher | functional cost recharges, functional recharges, recharges, functional neutralization |
| Functional costs | Country functions, Region functions, HQ allocation | Cost | lower | total functional costs, functional costs, functional cost, function costs |
| Other operating expenses | Restructuring, Amortisation of acquired intangibles, Other non-recurring | Cost | lower | other operating expenses, other operating expense, other opex, non-recurring items |
| Financial result | Net interest, FX result | Revenue / income | higher | financial result, finance result, net financial result, financial costs |
| Income taxes | - | Cost | lower | corporate taxes, corporate tax, taxes, tax |


## Metrics

| Metric | Type | Definition | Favourable when | Also understood as |
|---|---|---|---|---|
| Billing | P&L line | Booked amount | higher | billing, billings, invoicing, invoiced |
| WIP & deferred income | P&L line | Booked amount | higher | wip, wip and ui, wip ui, wip and deferred income |
| Revenue | Subtotal | Billing + WIP & deferred income | higher | revenue, revenues, sales, turnover |
| Intragroup revenue | P&L line | Booked amount | higher | intragroup revenue, intra-group revenue, intercompany revenue, ic revenue |
| Intragroup subcontracting | P&L line | Booked amount | lower | intragroup subcontracting, intra-group subcontracting, intercompany subcontracting, ic subcontracting |
| Production | Subtotal | Revenue + Intragroup revenue + Intragroup subcontracting | higher | production, total production, production value, output |
| Personnel costs | P&L line | Booked amount | lower | personnel charges, personnel cost, personnel costs, personnel |
| External subcontracting | P&L line | Booked amount | lower | external subcontracting, subcontracting, subcontracting cost, subcontracting costs |
| Other costs | P&L line | Booked amount | lower | other costs, other cost, other direct costs |
| Functional cost recharges | P&L line | Booked amount | higher | functional cost recharges, functional recharges, recharges, functional neutralization |
| Gross profit | Subtotal | Production + Personnel costs + External subcontracting + Other costs + Functional cost recharges | higher | gross profit, gp, gross profit amount |
| Functional costs | P&L line | Booked amount | lower | total functional costs, functional costs, functional cost, function costs |
| Operating profit | Subtotal | Gross profit + Functional costs | higher | operating profit, op, profit, profits |
| Other operating expenses | P&L line | Booked amount | lower | other operating expenses, other operating expense, other opex, non-recurring items |
| EBIT | Subtotal | Operating profit + Other operating expenses | higher | ebit, operating income, reported operating profit, management op |
| Financial result | P&L line | Booked amount | higher | financial result, finance result, net financial result, financial costs |
| Income taxes | P&L line | Booked amount | lower | corporate taxes, corporate tax, taxes, tax |
| Net income | Subtotal | EBIT + Financial result + Income taxes | higher | net income, net profit, net result, net earnings |
| Direct staff costs | Account group | Sum of its accounts | lower | 7a, 7a personnel, 7a personnel cost, direct labor |
| Indirect staff costs | Account group | Sum of its accounts | lower | 7b, 7b personnel, 7b personnel cost, non-production employees |
| Direct margin (amount) | Amount | Production - Direct staff costs | higher | direct margin amount, direct margin value, direct margin in usd |
| Direct margin incl. subcontracting (amount) | Amount | Production - Direct staff costs - External subcontracting | higher | direct margin incl subcontracting amount, direct margin after subcontracting amount |
| Total FTE | Statistic | Average over the months | - | fte, ftes, total fte, full time equivalents |
| Total headcount | Statistic | Average over the months | - | headcount, head count, total headcount, hc |
| Direct FTE | Statistic | Average over the months | - | direct fte, production fte, direct ftes |
| Billable hours | Statistic | Sum over the months | - | billable hours, billed hours, chargeable hours |
| Available hours | Statistic | Sum over the months | - | available hours, capacity hours, available capacity |
| Overtime hours | Statistic | Sum over the months | - | overtime hours |


## Ratios

Aggregates are always a ratio of sums; a zero or negative denominator shows n/a. 'Profit %' or 'margin' without a base returns both operating margins.

| Ratio | Formula | Unit | Favourable when | Typical range (middle half of BUs, last 12 months) | Also understood as |
|---|---|---|---|---|---|
| Personnel costs / Billing | Personnel costs / Billing | % | lower | certification 50.6%-52.8%; industry 52.5%-56.0%; infrastructure 45.6%-49.6%; inspection 58.5%-59.8%; laboratory 45.2%-48.3% | personnel to billing, personnel cost to billing, personnel / billing |
| Personnel costs / Revenue | Personnel costs / Revenue | % | lower | certification 50.2%-52.3%; industry 52.4%-55.7%; infrastructure 45.7%-49.4%; inspection 58.1%-59.7%; laboratory 45.1%-48.0% | personnel to revenue, personnel cost to revenue, personnel / revenue |
| Personnel costs / Production | Personnel costs / Production | % | lower | certification 49.8%-52.7%; industry 53.0%-55.5%; infrastructure 45.8%-49.8%; inspection 58.6%-59.4%; laboratory 45.3%-47.8% | personnel to production, personnel cost to production, personnel / production |
| Direct staff costs / Production | Direct staff costs / Production | % | lower | certification 35.8%-37.9%; industry 42.4%-44.5%; infrastructure 35.8%-38.9%; inspection 46.9%-47.5%; laboratory 34.0%-35.9% | direct labor cost over production, direct labour cost over production, direct labor cost ratio |
| External subcontracting % of production | External subcontracting / Production | % | lower | certification 8.3%-9.7%; industry 7.6%-12.7%; infrastructure 16.7%-20.5%; inspection 6.0%-7.3%; laboratory 2.9%-4.3% | subcontracting %, subcontracting ratio, subcontracting as % of production |
| Other costs % of production | Other costs / Production | % | lower | certification 7.3%-8.6%; industry 13.2%-14.4%; infrastructure 10.9%-12.0%; inspection 12.2%-13.2%; laboratory 29.1%-31.4% | other cost %, other costs %, other cost ratio |
| Functional costs % of production | Functional costs / Production | % | lower | certification 11.0%-11.2%; industry 10.3%-10.5%; infrastructure 9.4%-10.5%; inspection 10.4%-10.6%; laboratory 10.4%-10.7% | functional cost %, functional costs %, functional cost ratio |
| Direct margin | Direct margin (amount) / Production | % | higher | certification 62.1%-64.2%; industry 55.5%-57.6%; infrastructure 61.1%-64.2%; inspection 52.5%-53.1%; laboratory 64.1%-66.0% | direct margin, direct margin %, direct margin rate |
| Direct margin incl. subcontracting | Direct margin incl. subcontracting (amount) / Production | % | higher | certification 53.1%-55.1%; industry 43.8%-49.3%; infrastructure 42.6%-46.7%; inspection 45.2%-46.5%; laboratory 60.0%-63.2% | direct margin including subcontracting, direct margin incl subcontracting, direct margin after subcontracting |
| Gross margin | Gross profit / Production | % | higher | certification 32.8%-35.2%; industry 20.8%-26.7%; infrastructure 23.4%-27.7%; inspection 23.4%-24.7%; laboratory 20.9%-24.7% | gross margin, gross margin %, gp margin |
| Operating margin on revenue | Operating profit / Revenue | % | higher | certification 21.7%-24.3%; industry 10.4%-16.2%; infrastructure 13.2%-18.3%; inspection 13.0%-14.1%; laboratory 10.3%-14.4% | operating margin on revenue, operating profit margin on revenue, margin on revenue |
| Operating margin on production | Operating profit / Production | % | higher | certification 21.6%-23.8%; industry 10.4%-16.3%; infrastructure 13.4%-18.4%; inspection 13.0%-14.3%; laboratory 10.4%-14.3% | operating margin on production, operating profit margin on production, margin on production |
| EBIT margin (on revenue) | EBIT / Revenue | % | higher | certification 19.7%-24.1%; industry 9.7%-15.4%; infrastructure 12.5%-18.1%; inspection 11.4%-13.1%; laboratory 8.9%-13.5% | ebit margin, operating income margin, management op margin |
| Net income margin (on revenue) | Net income / Revenue | % | higher | certification 13.4%-15.8%; industry 6.4%-10.6%; infrastructure 8.1%-11.6%; inspection 7.4%-9.1%; laboratory 5.9%-8.9% | net margin, net income margin, net profit margin |
| Personnel costs per FTE (annualised) | Personnel costs / Total FTE x 12 (annualised) | USD | lower | - | personnel cost per fte, personnel charges per fte, cost per fte |
| Production per FTE (annualised) | Production / Total FTE x 12 (annualised) | USD | higher | - | production per fte, productivity, output per fte |
| WIP & deferred income as % of revenue | WIP & deferred income / Revenue | % | - | certification 0.2%-0.8%; industry 0.2%-0.7%; infrastructure 0.2%-0.5%; inspection 0.1%-0.6%; laboratory 0.2%-0.5% | wip as % of revenue, wip % of revenue, wip ratio |
| Utilization rate (billable / available hours) | Billable hours / Available hours | % | higher | certification 70.4%-75.6%; industry 73.1%-76.5%; infrastructure 74.9%-79.3%; inspection 73.1%-75.7%; laboratory 71.0%-75.8% | utilization rate, utilisation rate, utilization |
| Production per billable hour | Production / Billable hours | USD | higher | - | production per hour, production per billable hour, revenue per hour |
| Production hourly cost (direct staff cost per billable hour) | Direct staff costs / Billable hours | USD | lower | - | production hourly cost, hourly cost, cost per hour |
| Overtime ratio (overtime / available hours) | Overtime hours / Available hours | % | lower | certification 5.0%-6.1%; industry 5.5%-7.7%; infrastructure 5.4%-7.6%; inspection 5.3%-6.9%; laboratory 4.5%-6.8% | overtime ratio, overtime %, overtime rate |
| Profit % / margin (no base given) | Shows both operating margins side by side | % | higher | - | operating margin, operating margins, operating profit margin, operating profit margins, op margin |


## Versions and periods

| Version | What it is | Available for |
|---|---|---|
| Actual | Booked results of closed months (a month closes on the 5th of the following month). | 2022-2026 |
| Budget | Annual plan set before the year starts. | 2022-2026 |
| FC1 | First reforecast: actuals for January-April plus a reforecast of the remaining months. | 2022-2026 |
| FC2 | Second reforecast: actuals for January-August plus a reforecast of the remaining months. | 2022-2026 |
| FC3 | Third reforecast: actuals for January-September plus a reforecast of the remaining months. | 2022-2026 |
| Latest forecast | The newest of FC3, FC2, FC1 published for the year (else the Budget). | FC3 for 2026 |
| Landing | Expected month-end of the open month (P50 with a P10-P90 range), computed by the landing engine from monthly history; WIP = 0, so revenue = billing. | Nov 2026 |


| Period type | Meaning | Example |
|---|---|---|
| Month | One calendar month | October 2026 |
| QTD | Quarter to date | QTD Oct 2026 |
| YTD | Year to date | YTD Oct 2026 |
| Rolling 12M | Last twelve months | R12M to Oct 2026 |
| Full year | January to December | FY 2025 |
| Quarter | A full quarter | Q3 2026 |
| Range | Any span of months | Jan 2025 - Jun 2026 |


### Close calendar

| Month | Closes on | Status |
|---|---|---|
| May 2026 | 2026-06-05 | Closed |
| Jun 2026 | 2026-07-05 | Closed |
| Jul 2026 | 2026-08-05 | Closed |
| Aug 2026 | 2026-09-05 | Closed |
| Sep 2026 | 2026-10-05 | Closed |
| Oct 2026 | 2026-11-05 | Closed |
| Nov 2026 | 2026-12-05 | Open (landing month) |
| Dec 2026 | 2027-01-05 | Future |
| Jan 2027 | 2027-02-05 | Future |
| Feb 2027 | 2027-03-05 | Future |


## Landing

The landing is the expected month-end result of the open month, computed by a separate, tested Python engine
(never by the language model) from monthly data only: closed-month actuals, the Budget and the forecasts.

1. Each BU's billing history is profiled (seasonal index, quarter-end and December share, volatility) and
   classified as steady, quarter-end loaded, year-end loaded, seasonal or lumpy.
2. Four methods forecast billing, all adjusted for working days: same month last year x recent growth;
   trailing 12 months x seasonal index; latest forecast x the BU's historical forecast accuracy; and
   exponential smoothing.
3. The methods are combined with weights learned from each method's recent errors, shrunk toward the
   weights of the BU's pattern class.
4. P10 and P90 come from the engine's own past errors; group and other totals use a 1,000-draw simulation.
5. Costs follow the billing landing (ratios to billing, a personnel run-rate, functional lines from the latest
   forecast). WIP is 0 in the landing month, so the revenue landing equals the billing landing.
6. BU results add up exactly to every higher level; margins are ratios of sums.


| Pattern | What it means | BUs in your scope | Landing backtest error (BU billing WAPE) |
|---|---|---|---|
| Steady | Billing spread evenly through the year with mild seasonality. | 23 | 3.9% (552 BU-months) |
| Quarter-end loaded | A large share of billing in March, June, September and December. | 44 | 3.9% (1056 BU-months) |
| Year-end loaded | A large share of billing in December (annual fees and audits). | 11 | 3.4% (264 BU-months) |
| Seasonal (March peak, August dip) | Clear seasonal shape: a March peak and an August dip. | 9 | 4.1% (216 BU-months) |
| Lumpy (project billing) | Project billing: large, irregular months; the widest landing ranges. | 19 | 19.4% (456 BU-months) |


### Measured backtest accuracy (run 2026-11-16)

Measured by `make backtest` over the last 24 closed months; see docs/landing_backtest_report.md.

**Group level, by method**

| Method | Billing WAPE % | Revenue WAPE % | Operating profit WAPE % (excl. WIP) | Operating profit WAPE % (as booked) |
|---|---|---|---|---|
| Same month last year x recent growth | 1.09 | 3.02 | 7.49 | 18.42 |
| Trailing 12 months x seasonal index | 2.10 | 4.15 | 11.70 | 23.53 |
| Latest forecast x the BU's forecast accuracy | 1.25 | 2.53 | 8.91 | 16.00 |
| Exponential smoothing (ETS) | 1.44 | 3.28 | 8.09 | 19.37 |
| IRIS landing (weighted ensemble) | 0.99 | 3.13 | 6.95 | 19.21 |
| Latest forecast as published | 2.28 | 2.31 | 8.55 | 8.66 |


**P10-P90 coverage by organisation level**

| Organisation level | Actual inside P10-P90 % | Months x units |
|---|---|---|
| BU | 73.70 | 2544 |
| Business | 78.70 | 1608 |
| Country | 87.90 | 264 |
| Group | 95.80 | 24 |
| Product line | 87.00 | 192 |
| Region | 93.30 | 120 |


**BU billing by pattern class**

| Billing pattern | IRIS landing WAPE % | Latest forecast WAPE % |
|---|---|---|
| Lumpy (project billing) | 19.40 | 17.70 |
| Quarter-end loaded | 3.90 | 5.20 |
| Seasonal (March peak, August dip) | 4.10 | 7.10 |
| Steady | 3.90 | 6.90 |
| Year-end loaded | 3.40 | 6.40 |


## Data and sources

- Storage: leaf accounts only, monthly, one currency (USD); subtotals and ratios are computed by the semantic layer from `metrics.yaml`.
- Refresh: Actuals: monthly, after the close on day 5 of the following month. Budget: once a year. Forecasts: three times a year. Landing: `make landing` (daily in production, for example with the optional private CronJob).
- Lineage: generator -> Parquet -> SQL Server 2022 (or DuckDB) -> semantic layer -> agent tools -> answer; the landing engine reads the same database and writes `fact_landing`.
- Reconciliation: last `make reconcile` on 2026-11-17 00:42: 0 mismatches in 300 subtotal checks, 0 integrity failures.

### Rows per version

| Version | Rows | From | To |
|---|---|---|---|
| Actual | 227476 | Jan 2022 | Oct 2026 |
| Budget | 235320 | Jan 2022 | Dec 2026 |
| FC1 | 235320 | Jan 2022 | Dec 2026 |
| FC2 | 235320 | Jan 2022 | Dec 2026 |
| FC3 | 235320 | Jan 2022 | Dec 2026 |


### Assumptions

- Synthetic data generated for this prototype; structure mirrors the target model.
- One currency (USD) at a constant budget exchange rate.
- Only leaf accounts are stored; every subtotal and ratio is computed by the semantic layer, so totals always reconcile.
- A month closes on day 5 of the following month; the month after the last closed month is the open (landing) month.
- Budget is set before the year; FC1, FC2 and FC3 carry 4, 8 and 9 months of actuals plus a reforecast.
- The landing has WIP = 0 in the landing month (revenue = billing) and uses monthly history only.
- Employee records are fictional codes without names or personal attributes.

## What IRIS can do

| Capability | Example question |
|---|---|
| Performance against budget, prior year and forecasts | How is operating profit YTD vs last year and budget for the United States? |
| Both operating margins | What is our profit % this year? |
| Trends over time | Show revenue by month since 2024 for Canada |
| Why something changed (drivers) | Why did Canada Environmental Lab Testing operating profit drop vs last year? |
| Rankings and comparisons | Which 5 BUs have the lowest operating margin on revenue YTD? |
| Budget and forecast versions | Compare budget, FC2 and FC3 for Mexico this year |
| Drill-down to accounts and business units | Break down personnel costs for US Elevators & Pressure Vessels |
| Current-month landing with a P10-P90 range | What's the November landing for the United States? |
| YTD and full year including the landing | What will YTD MAOP margin be through November including the landing? |
| Workforce from fictional employee records | What is the attrition rate by role in Canada Environmental Lab Testing? |
| Discovery: what is in scope | Which businesses can I ask about? |

