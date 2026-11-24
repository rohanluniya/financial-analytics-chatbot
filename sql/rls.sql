-- =============================================================================
-- Row-level security (SQL Server native) for the fact tables and the employee tables.
-- The app connects as a least-privilege login and runs, on every new connection:
--     EXEC sp_set_session_context @key = N'user_id', @value = <persona>, @read_only = 1;
-- The filter predicate then keeps only rows for BUs the user may see according to
-- dbo.user_org_access (any level L1..L6). No session context => no rows (secure default).
-- `dbo` (the admin/loader, e.g. sa) bypasses the filter for maintenance and reconciliation.
-- Org and account dimensions are NOT filtered: org names are not sensitive and the app needs them
-- to tell a user "you don't have access to Brazil" instead of "Brazil doesn't exist". Employee
-- records are filtered like the facts.
-- =============================================================================
IF SCHEMA_ID(N'rls') IS NULL EXEC (N'CREATE SCHEMA rls AUTHORIZATION dbo');
GO

IF EXISTS (SELECT 1 FROM sys.security_policies WHERE name = N'OrgAccessPolicy')
    DROP SECURITY POLICY rls.OrgAccessPolicy;
GO

CREATE OR ALTER FUNCTION rls.fn_org_access (@bu_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
    SELECT 1 AS allowed
    WHERE USER_NAME() = N'dbo'
       OR EXISTS (
            SELECT 1
            FROM dbo.user_org_access AS a
            JOIN dbo.dim_org AS o
              ON o.bu_id = @bu_id
            WHERE a.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(50))
              AND (   (a.org_level = N'l1_group'        AND o.l1_group        = a.org_value)
                   OR (a.org_level = N'l2_region'       AND o.l2_region       = a.org_value)
                   OR (a.org_level = N'l3_country'      AND o.l3_country      = a.org_value)
                   OR (a.org_level = N'l4_product_line' AND o.l4_product_line = a.org_value)
                   OR (a.org_level = N'l5_business'     AND o.l5_business     = a.org_value)
                   OR (a.org_level = N'l6_bu'           AND o.l6_bu           = a.org_value))
       );
GO

CREATE SECURITY POLICY rls.OrgAccessPolicy
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.fact_pnl,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.fact_stats,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.dim_employee,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.fact_employee_month,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.fact_landing,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.fact_landing_leaf,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.landing_method,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.landing_bu_profile,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.landing_residual,
    ADD FILTER PREDICATE rls.fn_org_access(bu_id) ON dbo.landing_mtd_snapshot
    WITH (STATE = ON, SCHEMABINDING = ON);
GO

-- Read-only application role (the loader creates the login/user and adds it to this role)
IF DATABASE_PRINCIPAL_ID(N'iris_app_role') IS NULL
    CREATE ROLE iris_app_role AUTHORIZATION dbo;
GO
GRANT SELECT ON SCHEMA::dbo TO iris_app_role;
DENY INSERT, UPDATE, DELETE, ALTER, EXECUTE ON SCHEMA::dbo TO iris_app_role;
GO
