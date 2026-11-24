-- =============================================================================
-- Conversation history (last 10 conversations per user). SQL Server: schema [app], the only
-- place the application login may write (dbo stays read-only). The DuckDB backend uses the
-- equivalent SQLite file (APP_HISTORY_DB, default data/app_history.sqlite) created by the app.
-- Executed by scripts/load_mssql.py after rls.sql. Idempotent: history survives `make load`.
-- Every query filters by user_id (app/history/store.py); retention keeps 10 per user.
-- =============================================================================
IF SCHEMA_ID(N'app') IS NULL EXEC (N'CREATE SCHEMA app AUTHORIZATION dbo');
GO

IF OBJECT_ID(N'app.app_conversation', N'U') IS NULL
CREATE TABLE app.app_conversation (
    conversation_id  UNIQUEIDENTIFIER  NOT NULL,
    user_id          NVARCHAR(80)      NOT NULL,
    persona          NVARCHAR(50)      NOT NULL,
    title            NVARCHAR(120)     NOT NULL,
    created_at       DATETIME2(0)      NOT NULL,
    updated_at       DATETIME2(0)      NOT NULL,
    is_pinned        BIT               NOT NULL CONSTRAINT df_app_conversation_pinned DEFAULT 0,
    CONSTRAINT pk_app_conversation PRIMARY KEY (conversation_id)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_app_conversation_user')
    CREATE INDEX ix_app_conversation_user ON app.app_conversation (user_id, is_pinned, updated_at);
GO

IF OBJECT_ID(N'app.app_message', N'U') IS NULL
CREATE TABLE app.app_message (
    message_id        UNIQUEIDENTIFIER  NOT NULL,
    conversation_id   UNIQUEIDENTIFIER  NOT NULL,
    seq               INT               NOT NULL,
    role              NVARCHAR(10)      NOT NULL,   -- user / assistant
    content_markdown  NVARCHAR(MAX)     NOT NULL,
    payload_json      NVARCHAR(MAX)     NULL,       -- full validated answer (table, chart, filters, SQL)
    created_at        DATETIME2(0)      NOT NULL,
    CONSTRAINT pk_app_message PRIMARY KEY (message_id),
    CONSTRAINT fk_app_message_conversation FOREIGN KEY (conversation_id)
        REFERENCES app.app_conversation (conversation_id) ON DELETE CASCADE
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_app_message_conversation')
    CREATE INDEX ix_app_message_conversation ON app.app_message (conversation_id, seq);
GO

IF OBJECT_ID(N'app.app_conversation_state', N'U') IS NULL
CREATE TABLE app.app_conversation_state (
    conversation_id   UNIQUEIDENTIFIER  NOT NULL,
    agent_state_json  NVARCHAR(MAX)     NOT NULL,   -- conversation memory + sidebar filters
    CONSTRAINT pk_app_conversation_state PRIMARY KEY (conversation_id),
    CONSTRAINT fk_app_state_conversation FOREIGN KEY (conversation_id)
        REFERENCES app.app_conversation (conversation_id) ON DELETE CASCADE
);
GO

-- The application role may read and write its own history tables, nothing else
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::app TO iris_app_role;
GO
