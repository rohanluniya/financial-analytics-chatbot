# Architecture

## Components

```mermaid
flowchart LR
    subgraph UI["IRIS UI (Streamlit, top navigation)"]
        CH["Chat"]
        CAT["Data Catalog"]
        UG["User Guide"]
        AB["About"]
        SB["Sidebar: settings, scope filters,<br/>conversations"]
    end
    SB -->|default context| CH
    CH --> AG["LangGraph agent<br/>(preprocess, plan, act,<br/>write, guard, finalize)"]
    AG --> T["Typed tools<br/>(P&L, trend, ratios, drivers, ranking,<br/>versions, cockpit, workforce, catalog,<br/>landing, read-only SQL)"]
    T --> SEM["Semantic layer<br/>metrics.yaml: lines, subtotals,<br/>ratios, versions incl. LANDING"]
    CAT --> SEM
    SEM --> DB[("SQL Server 2022 / DuckDB<br/>leaf accounts, row-level security")]
    LE["Landing engine<br/>make landing (batch, no LLM)"] -->|reads monthly history| DB
    LE -->|writes fact_landing| DB
    BT["Backtest<br/>make backtest"] --> LE
    BT -->|landing_backtest_metric| DB
    CH <-->|"last 10 per user"| HIST[("Conversation history<br/>[app] schema / SQLite")]
    AG --> LLM["LLM via LiteLLM<br/>(Ollama on CPU, or a hosted model)"]
```

- **UI** (`app/ui/`): `streamlit_app.py` signs the user in (demo sign-in), builds the top navigation and the
  sidebar, and runs a page from `app/ui/views/`. All product names come from `app/ui/branding.py`.
- **Agent** (`app/agent/`): the state graph below; the LLM chooses tools and writes the narrative, but every
  number comes from a tool.
- **Semantic layer** (`app/semantic/`): one definition of every line, subtotal and ratio; the landing is the
  virtual version `LANDING` (open month from `fact_landing_leaf`, other months from `fact_pnl`).
- **Landing engine** (`app/landing/`): deterministic batch job; see [landing_methodology.md](landing_methodology.md).
- **Catalog** (`app/semantic/catalog.py`): shared by the Data Catalog page, the `describe_catalog` tool and
  `docs/data_manual.md`.
- **Conversation history** (`app/history/store.py`): last 10 conversations per user with the full answer
  payloads, so a conversation reopens without calling the LLM or the database.

## Request flow

```mermaid
flowchart LR
    U["Business user<br/>(question + sidebar filters)"] --> P["preprocess<br/>entity resolution, filters, memory,<br/>access check"]
    P -->|refuse / clarify| F["finalize<br/>output contract"]
    P --> PL["plan<br/>LLM picks tool + arguments<br/>(router fallback, catalog / landing guard)"]
    PL --> A["act<br/>typed tools -> semantic layer<br/>-> SQLAlchemy Core"]
    A --> DB[("SQL Server 2022<br/>row-level security")]
    A --> W["write<br/>LLM narrative from FACTS"]
    W --> G["guard<br/>numbers, months, scope, causes<br/>(1 rewrite, then redact or template)"]
    G -->|retry| W
    G --> F
    F --> U
```

The flow is a LangGraph state graph (`app/agent/graph.py`) with six nodes.

1. **preprocess** (deterministic, no LLM)
   - `app/semantic/entity_resolver.py` finds org units at any level (aliases, ISO codes, BU codes, typo tolerance), metrics and ratios, periods, versions and comparisons, intents (why / trend / rank / breakdown / versions / cockpit), top-N and ranking level.
   - Follow-ups ("now for Canada", "same vs FC2", "why is the first one so low?") are merged with the previous turn's memory.
   - Sidebar filters are applied as the default context; the question's own words win, and every answer
     lists where each filter came from (question, sidebar, conversation or default).
   - Discovery questions ("which countries are in scope?") are marked for the catalog and landing questions
     ("what's the November landing?") for the landing tools; the planner cannot override either.
   - "Profit %", "margin" or "MAOP %" without a base asks for both operating margins.
   - The access check (`app/semantic/access.py`) refuses, narrows or allows the request before any data is read.
   - Ambiguous names (a city with several businesses) trigger a clarification.
2. **plan.** The LLM chooses one of fourteen typed data tools through native or text tool calling (LiteLLM).
   - If the model returns no usable call, a deterministic router supplies one.
   - Every answer records whether the LLM or the router made the choice.
3. **act.** Tools validate their arguments (Pydantic) and call the semantic layer.
   - If the LLM's call fails, the router's call is tried once.
4. **write.** The LLM receives pre-formatted FACTS only and writes 2–4 sentences.
   - It does no arithmetic.
   - The FACTS spell out comparisons ("USD 3.2M (5.8%) above PY (USD 55.9M), favourable").
5. **guard.** Every number in the text must exist in the tool output, within display rounding. On top of that (`app/agent/guardrails.py`, `check_answer`):
   - a number next to a single month, or labelled restructuring / voluntary, must be the data's number for that month or leaver type, and a change stated for a leaver type must be that type's change;
   - small numbers are checked when they are stated as a difference ("30 above PY");
   - the scope may not be named more broadly than asked ("the United States" for United States · Environmental Lab Testing);
   - a cause ("driven by …", "due to …") must name a line, account, driver, role, BU or month from the data, and listed generic causes ("sales volumes", "cost management") must appear in the facts.
   - If the draft fails, the writer gets one rewrite with the problems spelled out. If the rewrite also fails, the sentences with unsupported numbers are dropped, as long as the first (headline) sentence survives. Otherwise a templated answer replaces the text.
   - Sentences after the headline that give causes not in the data are dropped from an accepted answer.
   - Customer terms typed in the question (MAOP) are written with the app's names in the answer.
   - The table and the key-figure bullets always come straight from the data.
6. **finalize.** Builds the validated output contract (`FinalAnswer`):
   - narrative + deterministic key-figure bullets + scope notes
   - finance table spec
   - chart spec (chosen by rules, never by the LLM)
   - filters / versions / period / currency
   - SQL
   - exactly three follow-up questions
   - diagnostics

## Tools

| Tool | Answers | Chart |
|---|---|---|
| `get_pnl` | general-ledger P&L for an org and period vs PY / Budget / forecasts | operating profit bridge (waterfall) |
| `get_trend` | monthly series of a metric or ratio (Actual, PY, Budget, R12M) | line |
| `get_ratio` | one ratio / KPI vs comparisons | bar |
| `variance_drivers` | account and org drill-down of a variance (pp bridge for margins) | waterfall or stacked bar |
| `rank_entities` | top / bottom BUs, businesses, sectors, countries, regions | horizontal bar |
| `compare_versions` | Actual vs Budget vs FC1/FC2/FC3 (full-year view for forecasts) | grouped bar |
| `get_kpi_cockpit` | operational profitability cockpit, MTD and YTD vs LY and Budget | combo (bars + lines) |
| `get_workforce` | headcount, FTE, hires, leavers, attrition, utilization and overtime from the employee records, by role, grade, staff type, month or org level, vs PY | horizontal bar, line, or hires vs leavers bars |
| `describe_catalog` | what is in scope (regions, countries, product lines, businesses, BUs, accounts, metrics, ratios, versions, periods, billing patterns, capabilities, examples), row-level security applied, never SQL | horizontal bar |
| `get_landing` | current-month landing (P50, P10-P90) by measure vs Budget, latest forecast, PY; closed month -> actuals, future month -> forecast | trend with landing marker and P10-P90 bar |
| `get_ytd_with_landing` | YTD, QTD or full-year outlook including the landing, vs PY / Budget / latest forecast | monthly bars, landing month hatched |
| `rank_landing` | BUs or other units ranked by landing gap vs budget or forecast ("which BUs will miss budget?") | horizontal bar |
| `explain_landing` | the four methods, their weights, the pattern class and the cost rules for one unit | bar |
| `run_readonly_sql` | fallback: one SELECT on whitelisted views (sqlglot guard, row limit, timeout) | bar |

## Semantic layer

`app/semantic/` has five parts:

- **Registry.** Built from `metrics.yaml` (P&L lines, direct / indirect staff cost groups, computed amounts, statistics, 21 ratios including the two operating margins, the margin pair for "profit %", cockpit KPIs, driver tree) plus the chart of accounts.
- **Query builder.** `query_builder.py` aggregates leaf accounts with SQLAlchemy Core and pivots them into a "wide" frame where every line, subtotal, group and statistic is a column. The same code runs on SQL Server and DuckDB.
- **Time intelligence.** `time_intel.py` covers YTD, QTD, MTD, R12M, FY, quarters and ranges, the close calendar and the last closed month, PY as shifted Actual, forecast availability by as-of date, like-for-like truncation, and favourability.
- **Access.** `access.py` holds persona scopes and narrowing messages, which mirror the SQL Server security policy.
- **Formatting.** `app/viz/` renders finance tables (thousand separators, negatives in parentheses, favourability colours, bold subtotals), Plotly charts and CSV / Excel export.

## Deployment used for this prototype

```mermaid
flowchart TB
    L["Laptop<br/>kubectl only"] -->|"kubectl port-forward<br/>(Google identity)"| APP
    subgraph GKE["GKE cluster, CPU node pool, own namespace"]
        APP["dev pod<br/>app container: Streamlit :8501<br/>dev container: make targets"]
        CJ["optional CronJob<br/>daily make landing"]
        MS[("SQL Server 2022 Developer<br/>StatefulSet + PVC")]
        OL["Ollama (CPU)<br/>qwen2.5-coder:14b, gpt-oss:20b"]
        APP --> MS
        APP --> OL
        CJ --> MS
    end
```

- Nothing runs on the laptop except `kubectl`. All Services are ClusterIP only; there is no LoadBalancer, NodePort or Ingress.
- The UI is reached with an authenticated port-forward (`make k8s-forward`). There is no public endpoint or tunnel: IRIS is local and private by design.
- `docker-compose.yml` runs the same stack (SQL Server + app + optional Ollama) on a single host. The `Dockerfile` was built in-cluster with kaniko; see `results/build/`.

## Swapping components

| Component | Prototype | Change by |
|---|---|---|
| Database | SQL Server 2022 Developer (container) | `DB_HOST` / `DB_NAME` / logins in `.env` (any SQL Server 2016+ with RLS) |
| Light demo backend | DuckDB file | `DB_BACKEND=duckdb` |
| LLM | Ollama qwen2.5-coder:14b on CPU | `LLM_MODEL` (any LiteLLM string: Azure OpenAI, Vertex AI, Bedrock, OpenAI, Ollama) |
| UI | Streamlit | the agent is a plain function `ask(question, user_id, memory, ui_filters=...)` returning `FinalAnswer` (JSON) |
| Sign-in | display name + shared access code (demo only) | single sign-on (Microsoft Entra ID / Active Directory) in front of the app |
| Conversation history | `[app]` schema in the same SQL Server (SQLite for DuckDB) | any database; retention and privacy rules to be decided for production |
