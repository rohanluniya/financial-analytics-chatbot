# Reconciliation report (mssql backend)

## Row counts per table

| Table | Rows |
|---|---:|
| dim_org | 106 |
| dim_account | 57 |
| dim_version | 5 |
| dim_period | 60 |
| app_user | 3 |
| user_org_access | 3 |
| fact_pnl | 1,168,756 |
| fact_stats | 31,588 |
| dim_employee | 27,294 |
| fact_employee_month | 937,504 |
| dim_calendar | 20,086 |
| working_days | 660 |

## fact_pnl rows and totals per version

| Version | Rows | Months | Sum of signed amounts (USD) |
|---|---:|---:|---:|
| Actual | 227,476 | 58 | 617,668,991.84 |
| Budget | 235,320 | 60 | 718,056,048.78 |
| FC1 | 235,320 | 60 | 693,701,737.07 |
| FC2 | 235,320 | 60 | 669,497,243.56 |
| FC3 | 235,320 | 60 | 658,545,460.44 |

## Integrity checks

| Check | Found | Expected | Status |
|---|---:|---:|---|
| Fact rows on non-leaf (subtotal/header) accounts | 0 | 0 | OK |
| Actual rows for months not yet closed | 0 | 0 | OK |
| Forecast actual-months differing from Actual (month totals) | 0 | 0 | OK |
| BU-months where employee totals differ from the Actual BU statistics | 0 | 0 | OK |
| Employee rows for months not yet closed | 0 | 0 | OK |
| Employees with more than one hire or leave month | 0 | 0 | OK |

## Subtotal reconciliation: 50 random BU x month x version samples

Each sample checks Revenue, Production, Gross profit, Operating profit, EBIT and Net income three ways: semantic layer vs raw SQL leaf sums (tolerance USD 0.005) and vs generator control totals (tolerance USD 0.15).

| BU | Month | Version | Production (USD) | Operating profit (USD) | Status |
|---|---|---|---:|---:|---|
| CA-MMI-TOR-02 | 202501 | Budget | 843,377.37 | 155,902.87 | OK |
| CA-ENV-VAN-01 | 202510 | FC3 | 1,791,041.22 | 368,169.95 | OK |
| CL-IND-CJC-02 | 202406 | FC1 | 607,194.76 | 138,368.94 | OK |
| CA-ENV-CAL-02 | 202509 | Budget | 1,524,469.00 | 199,761.99 | OK |
| CA-BNI-TOR-01 | 202402 | FC1 | 1,036,636.34 | 325,975.38 | OK |
| US-CPS-LAX-01 | 202601 | FC3 | 1,968,499.19 | 129,271.45 | OK |
| BR-MMI-BHZ-02 | 202410 | FC2 | 529,633.08 | 89,892.09 | OK |
| CL-MMI-ANF-02 | 202401 | FC3 | 630,100.41 | 71,511.81 | OK |
| MX-IND-MEX-01 | 202610 | Budget | 1,509,735.65 | 247,783.52 | OK |
| PY-BNI-ASU-01 | 202307 | FC3 | 530,238.66 | -70,691.51 | OK |
| US-BNI-LAX-01 | 202402 | FC2 | 1,088,717.94 | 192,217.71 | OK |
| CL-MMI-CCP-01 | 202402 | Actual | 1,025,087.57 | 129,372.53 | OK |
| ... 38 more samples | | | | | |

**Mismatches: 0** (subtotal checks: 300), integrity check failures: 0
