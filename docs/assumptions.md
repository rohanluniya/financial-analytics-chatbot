# Assumptions

The prototype runs on synthetic data for a fictional company. It follows the kind of structures a
TIC finance team reports on (a monthly management P&L and an operational KPI cockpit), with generic
names: no customer report names, account codes, rate codes or real people. The choices below were
made where the material was silent. Each one can be changed in `config/settings.yaml`,
`app/semantic/metrics.yaml` or `scripts/generate_data.py`.

## Company and scope

| Topic | Assumption |
|---|---|
| Company | "RL Certification & Inspection" (RL Group), a fictional TIC company that competes with SGS, Bureau Veritas, Intertek and Dekra |
| Geography | Americas only: 5 regions (US & Canada, Mexico, Northern South America, Southern South America, BPU = Brazil / Paraguay / Uruguay), 11 countries |
| Sectors (product lines) | Buildings & Infrastructure, Industry & Energy, Power & Utilities, Elevators & Pressure Vessels, Environmental Lab Testing, Consumer Products, Certification & Sustainability, Metals & Minerals |
| Environmental Lab Testing | Canada only (5 BUs in Toronto, Montreal, Calgary and Vancouver) plus one small US unit (Seattle) |
| Hierarchy | group > region > country > sector > business (sector + city) > BU; 106 BUs |
| Time | Jan 2022 – Dec 2026, monthly; as-of date 2026-11-12; a month closes on the 5th of the next month |

## Financial structure

| Topic | Assumption |
|---|---|
| P&L layout | A generic general-ledger management P&L: Revenue = Billing + WIP & deferred income; Production = Revenue + intragroup lines; Gross profit = Production − personnel − subcontracting − other costs + functional cost recharges; Operating profit = Gross profit − functional costs; EBIT = Operating profit − other operating expenses; Net income = EBIT + financial result − income taxes |
| "Operating result" (first specification) | Mapped to Gross profit (production minus direct costs, before functional costs); the headline profit line is Operating profit. "MAOP" and "management OP" are accepted as synonyms in questions |
| Personnel costs | Direct staff costs (billable staff) and indirect staff costs, with leaf accounts for salaries, bonus, overtime, social security, pension and other |
| Functional cost recharges | A small positive line (about 2.5% of the BU's production trend) that offsets functional charges booked in other costs |
| Functional costs | Country, region and HQ allocations; HQ allocation is spread evenly over the months of a year |
| Income taxes | Country tax rate × pre-tax result, per BU and month |
| Financial result | Net interest plus an FX result that depends on country volatility (zero for USD; Argentina has a negative drift) |
| Currency | USD at one constant budget exchange rate (constant currency) |
| Versions | Actual, Budget, FC1 (4 actual + 8 forecast months), FC2 (8 + 4), FC3 (9 + 3). Later forecasts sit closer to the outcome (accuracy 0.45 / 0.70 / 0.85) |
| Budget | Prior-year actual × target growth, with a slight optimism bias |

## Operational KPIs (cockpit)

| KPI | Definition |
|---|---|
| Direct margin | (production − direct staff costs) / production; a variant including external subcontracting is also available |
| Utilization rate | billable hours / available hours of direct staff (group level about 74%) |
| Production per hour | production / billable hours |
| Production per FTE | production × 12 / sum of monthly FTE (annualised) |
| Overtime ratio | overtime hours / available hours (group level about 6%) |
| Production hourly cost | direct staff costs / billable hours |
| Direct staff costs over production | direct staff costs / production |

Available hours assume 150 hours per direct FTE per month before seasonality.

## Workforce (employee records)

| Topic | Assumption |
|---|---|
| Employees | Fictional, codes only (`E100123`); no names, gender, age or other personal attributes |
| Attributes | BU, role (by business type, e.g. inspector, lab technician, auditor, sales, administration, manager), grade G1 (junior) to G5 (senior), direct or indirect staff, FTE % (100 / 80 / 50) |
| Consistency | Per BU and month, employee headcount, FTE and hours add up exactly to the Actual BU statistics |
| Hours | Direct staff carry available, billable and overtime hours; utilization varies by grade and role around the BU value |
| Hires and leavers | Hires fill headcount growth. Voluntary leavers follow a monthly probability by region and grade (higher for junior grades). When a BU's headcount falls, the surplus leaves as restructuring |
| Attrition | Leavers × 12 / months / average headcount (annualised) |
| Comparison | Prior year (same months); there is no workforce budget |

## Data generation

| Topic | Assumption |
|---|---|
| Cost profiles | By business type, as a share of production: inspection is personnel-heavy (about 60%), infrastructure subcontracting-heavy (about 18%), laboratories have high other costs (consumables, depreciation), certification has the highest margin |
| Seasonality | Northern countries: March peak, August and December dips. South America: January/February summer dip, July winter break, December dip |
| Stories | Five planted business stories (see `docs/demo_stories.md`) |
| Reproducibility | Fixed seed `20261112`; `make data` always produces the same tables |

## Personas and access

| Persona | Scope |
|---|---|
| Group CFO | whole group |
| United States Country Head | United States only |
| Environmental Lab Testing PL Leader | Environmental Lab Testing (Canada and the US unit) |

A question outside a persona's scope is refused without data. A question wider than the scope
(for example "the whole group" from the US country head) is answered for the allowed part, and
the answer says so. The same rules apply to the employee records.

## Not covered by the prototype

- Balance sheet, cash flow and order intake / backlog.
- Intercompany eliminations beyond the two intragroup lines.
- Local-currency reporting, or more than one FX rate.
- Workforce budget, salaries per employee and any personal data.
- The customer's real data. When it becomes available, the generator is replaced by a load from the existing SQL Server tables (see `docs/production_migration.md`).
