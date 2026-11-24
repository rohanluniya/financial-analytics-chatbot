-- =============================================================================
-- Whitelisted reporting views. These are the ONLY objects the fallback tool
-- run_readonly_sql may query (enforced with sqlglot in app/agent/guardrails.py).
-- RLS on the fact tables applies through the views automatically on SQL Server.
-- The same file is replayed on DuckDB (scripts/export_duckdb.py strips `dbo.`/GO).
-- =============================================================================

CREATE OR ALTER VIEW dbo.v_org AS
SELECT bu_id, bu_name, l6_bu, l5_business, l4_product_line, l3_country, l2_region, l1_group,
       business_type, city
FROM dbo.dim_org;
GO

CREATE OR ALTER VIEW dbo.v_account AS
SELECT account_id, line_no, l1_name AS line_name, l2_code, l2_name, l3_code, l3_name,
       is_leaf, is_subtotal, natural_sign, favorable_direction, display_order
FROM dbo.dim_account;
GO

CREATE OR ALTER VIEW dbo.v_period AS
SELECT month_key, year, quarter, month, month_name, close_date
FROM dbo.dim_period;
GO

CREATE OR ALTER VIEW dbo.v_version AS
SELECT version_id, name AS version, actual_months, is_forecast
FROM dbo.dim_version;
GO

-- Leaf-level P&L with all dimension attributes (signed USD amounts: revenue +, cost -)
CREATE OR ALTER VIEW dbo.v_pnl_leaf AS
SELECT f.month_key, p.year, p.quarter, p.month, v.name AS version,
       f.bu_id, o.bu_name, o.l5_business, o.l4_product_line, o.l3_country, o.l2_region, o.l1_group,
       a.line_no, a.l1_name AS line_name, a.l2_code, a.l2_name, a.l3_code, a.l3_name,
       f.amount_usd
FROM dbo.fact_pnl AS f
JOIN dbo.dim_account AS a ON a.account_id = f.account_id
JOIN dbo.dim_org     AS o ON o.bu_id      = f.bu_id
JOIN dbo.dim_version AS v ON v.version_id = f.version_id
JOIN dbo.dim_period  AS p ON p.month_key  = f.month_key;
GO

-- P&L by line INCLUDING the computed subtotals (internal line keys):
--   3 REVENUE = 1+2, 6 PRODUCTION = 3+4+5, 11 GROSS PROFIT = 6+7+8+9+10, 13 OPERATING PROFIT = 11+12,
--   18 EBIT = 13+17, 21 NET INCOME = 18+19+20
CREATE OR ALTER VIEW dbo.v_pnl AS
WITH line_sum AS (
    SELECT f.month_key, f.bu_id, f.version_id, a.line_no, SUM(f.amount_usd) AS amount_usd
    FROM dbo.fact_pnl AS f
    JOIN dbo.dim_account AS a ON a.account_id = f.account_id
    GROUP BY f.month_key, f.bu_id, f.version_id, a.line_no
),
membership AS (
    SELECT line_no, report_line FROM (VALUES
        (1, 1), (1, 3), (1, 6), (1, 11), (1, 13), (1, 18), (1, 21),
        (2, 2), (2, 3), (2, 6), (2, 11), (2, 13), (2, 18), (2, 21),
        (4, 4), (4, 6), (4, 11), (4, 13), (4, 18), (4, 21),
        (5, 5), (5, 6), (5, 11), (5, 13), (5, 18), (5, 21),
        (7, 7), (7, 11), (7, 13), (7, 18), (7, 21),
        (8, 8), (8, 11), (8, 13), (8, 18), (8, 21),
        (9, 9), (9, 11), (9, 13), (9, 18), (9, 21),
        (10, 10), (10, 11), (10, 13), (10, 18), (10, 21),
        (12, 12), (12, 13), (12, 18), (12, 21),
        (17, 17), (17, 18), (17, 21),
        (19, 19), (19, 21),
        (20, 20), (20, 21)
    ) AS m (line_no, report_line)
)
SELECT ls.month_key, p.year, p.quarter, p.month, v.name AS version,
       ls.bu_id, o.bu_name, o.l5_business, o.l4_product_line, o.l3_country, o.l2_region, o.l1_group,
       m.report_line AS line_no, n.l1_name AS line_name,
       SUM(ls.amount_usd) AS amount_usd
FROM line_sum AS ls
JOIN membership      AS m ON m.line_no = ls.line_no
JOIN dbo.dim_account AS n ON n.line_no = m.report_line AND n.is_leaf = 0
                         AND n.display_order = m.report_line * 100
JOIN dbo.dim_org     AS o ON o.bu_id      = ls.bu_id
JOIN dbo.dim_version AS v ON v.version_id = ls.version_id
JOIN dbo.dim_period  AS p ON p.month_key  = ls.month_key
GROUP BY ls.month_key, p.year, p.quarter, p.month, v.name,
         ls.bu_id, o.bu_name, o.l5_business, o.l4_product_line, o.l3_country, o.l2_region, o.l1_group,
         m.report_line, n.l1_name;
GO

CREATE OR ALTER VIEW dbo.v_stats AS
SELECT s.month_key, p.year, p.quarter, p.month, v.name AS version,
       s.bu_id, o.bu_name, o.l5_business, o.l4_product_line, o.l3_country, o.l2_region, o.l1_group,
       s.fte, s.headcount, s.direct_fte, s.billable_hours, s.available_hours, s.overtime_hours
FROM dbo.fact_stats AS s
JOIN dbo.dim_org     AS o ON o.bu_id      = s.bu_id
JOIN dbo.dim_version AS v ON v.version_id = s.version_id
JOIN dbo.dim_period  AS p ON p.month_key  = s.month_key;
GO

-- Fictional employees with org attributes (codes only, no names)
CREATE OR ALTER VIEW dbo.v_employee AS
SELECT e.employee_id, e.employee_code, e.role, e.grade, e.staff_type, e.fte_pct, e.hire_date, e.leave_date,
       e.leave_reason, e.bu_id, o.bu_name, o.l5_business, o.l4_product_line, o.l3_country, o.l2_region, o.l1_group
FROM dbo.dim_employee AS e
JOIN dbo.dim_org      AS o ON o.bu_id = e.bu_id;
GO

-- Employee x month (Actual): FTE, hours, hires and leavers
CREATE OR ALTER VIEW dbo.v_employee_month AS
SELECT f.month_key, p.year, p.quarter, p.month, f.employee_id, e.employee_code, e.role, e.grade, e.staff_type,
       e.leave_reason, f.bu_id, o.bu_name, o.l5_business, o.l4_product_line, o.l3_country, o.l2_region, o.l1_group,
       f.fte, f.available_hours, f.billable_hours, f.overtime_hours, f.is_hire, f.is_leaver
FROM dbo.fact_employee_month AS f
JOIN dbo.dim_employee AS e ON e.employee_id = f.employee_id
JOIN dbo.dim_org      AS o ON o.bu_id       = f.bu_id
JOIN dbo.dim_period   AS p ON p.month_key   = f.month_key;
GO
