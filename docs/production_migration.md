# Moving to production

This page lists what changes when the prototype runs on the customer's SQL Server and real P&L
data. The agent, tools and UI talk only to the semantic layer, and the semantic layer reads only
SQL views. Most of the work is therefore mapping the customer's tables to those views.

## 1. Data: point the views at the real tables

1. **Keep the view contract.** Keep `v_org`, `v_account`, `v_period`, `v_version`, `v_pnl_leaf`, `v_stats`, `v_employee` and `v_employee_month` with the same column names, and redefine them in `sql/views.sql` on top of the customer's tables.
   - Typical sources are the monthly general-ledger P&L fact, the org hierarchy (org levels down to BU), the account master and the HR / timesheet extracts.
2. **Map the semantic layer.** The query builder reads `fact_pnl` / `fact_stats` / `fact_employee_month` / `dim_*` through SQLAlchemy table objects in `app/db.py`. Either:
   - expose the customer's data under those names (views or synonyms), or
   - change the table definitions in `app/db.py`.
3. **Match the chart of accounts.** Load the customer's leaf accounts into `dim_account` with their P&L line, group (direct / indirect staff costs) and sign, and use the customer's own line names as display names. Check the subtotal formulas in `metrics.yaml` against the customer's monthly P&L report.
4. **Versions and exchange rates.**
   - Map Actual / Budget / forecasts to `dim_version`.
   - If several exchange-rate bases exist (budget rate, actual rate, ...), add a rate column and a default in `settings.yaml`.
5. **Reconcile before go-live.** `make reconcile` compares semantic-layer subtotals with raw SQL. Add a comparison with the published dashboard numbers for a few BUs and months.

## 2. Security

| Item | Production setting |
|---|---|
| Database login | A dedicated SQL login or Entra ID managed identity with SELECT on the reporting views only (as `iris_reader` in `sql/rls.sql`) |
| Row-level security | Replace `user_org_access` with the existing entitlement tables (dashboard user filters or a directory group → org-level mapping) and keep the SECURITY POLICY + `SESSION_CONTEXT` pattern |
| User identity | The UI sets `user_id` from SSO (Entra ID / Okta) instead of the persona selector |
| Secrets | Key Vault / Secret Manager; never in `.env` files on shared hosts |
| LLM data flow | The LLM receives only pre-aggregated facts (no row-level data). Use a provider and region covered by the customer's data-processing agreement, or a self-hosted model |
| Employee data | Limit workforce questions to HR and finance roles; hide groups too small to stay anonymous; privacy review for employee-level data (Canadian and US rules differ) |
| Audit | Log every question, the user, the tool calls and the SQL statements (they are already returned in each answer's diagnostics) |

## 3. LLM choice

- **Use the endpoint the customer is licensed for.** `LLM_MODEL` takes any LiteLLM model string, for example `azure/<deployment>` (Azure OpenAI), `openai/<model>`, `vertex_ai/gemini-2.5-flash`, `bedrock/...` or `ollama/...`. A Microsoft 365 Copilot licence usually does not cover API calls from a custom application; those normally go through Azure OpenAI, billed separately. Confirm with the customer's Microsoft team.
- **Check the terms.** Data retention, no training on customer data, processing region (Canada / US), rate limits and cost per question.
- **Choosing a model.** Re-run `make eval` with each candidate. The report compares tool choice, numeric accuracy, guardrail outcomes and latency on the same questions. The prompts were tuned on small local models, so measure before switching.
- **Pin the model version** and re-run the evaluation before every upgrade; hosted models change behaviour between versions.
- **CPU-only models.** These run at 20–100 s per answer in this prototype (see the eval report). Production needs a GPU-backed endpoint or a managed API for interactive use.
- **Teams / Copilot.** The tools can also be exposed as an API, so a Copilot agent (for example built in Copilot Studio) can call them from Teams. The semantic layer, row-level security and guardrails stay in this service.

## 4. Conversation memory

**Today (prototype).** Within a conversation, memory holds the scope, measure, period and comparison of the
last answer, ranked items for "the first one", and the last five questions with what each used (the LLM planner
sees these). Follow-ups, corrections ("no, I meant Mexico", "not YTD, full year 2025") and pushback ("that's not
right") use it.

Across conversations, IRIS keeps the **last 10 conversations per signed-in user** (`app/history/store.py`,
tables `app.app_conversation`, `app.app_message`, `app.app_conversation_state`): every question, the full
answer payload (text, table, chart, filters, SQL) and the conversation state with the sidebar filters.
Reopening a conversation re-renders the stored answers without calling the LLM or the database and restores
the context, so follow-ups continue. Old landing answers are labelled with their date and offer a refresh.
The 11th conversation deletes the oldest unpinned one in the same transaction; every query filters by user.
The sign-in is a demo (display name + shared access code).

**For production** this needs decisions on retention and privacy:

| Item | Proposal |
|---|---|
| Identity | The SSO user id (Microsoft Entra ID / Active Directory) instead of the display name |
| What is stored | Today the full payload, including figures, so a reopened answer shows what the user saw then. Alternative: store only the question and what was used, and re-run on current data and current access rights |
| Who sees it | Only the user (every query filters by user id; row-level security on the tables can enforce it in the database too); administrators through the audit log only |
| Retention | Set by the customer (for example 30 or 90 days, or the last N conversations as today), purged automatically; users can delete their own history |
| LLM | Only the last few turns of the open conversation are sent, as today |
| Privacy | Questions can name employees or groups of employees, so the store follows the employee-data rules above |

## 5. Answer quality in production

- **Golden questions from the team.** Rewrite `tests/golden_questions.yaml` with the finance team's real questions and the answers they check in Tableau; agree pass thresholds.
- **Re-run on every change** of model, prompt, metric definition or data mapping (`make eval`).
- **Feedback.** Add thumbs up / down to each answer and review flagged answers regularly, together with the guardrail outcome logged per answer.

## 6. Hosting

| Option | Notes |
|---|---|
| Container (Dockerfile) | Azure Container Apps / App Service, AKS, Cloud Run or on-prem Docker. ODBC Driver 18 is in the image |
| docker compose | Single VM next to SQL Server; ports bound to localhost behind a reverse proxy with SSO |
| Kubernetes | As in this prototype (`deploy/k8s/`); expose through an ingress with SSO instead of port-forward |

## 7. Relationship to Tableau

- **Tableau stays the system for standard dashboards.** IRIS covers the ad-hoc questions that today become dashboard requests.
- **Same numbers.** Both read the same SQL Server views, so the figures match. A Tableau extract of the views can be reconciled automatically.
- **Linking out.** Answers can link to the matching Tableau view by passing the resolved filters (org, period, version) as URL parameters.

## 8. Checklist

- [ ] Views mapped to the customer's tables; `make reconcile` shows 0 mismatches against the published P&L.
- [ ] Entitlements mapped; RLS tests pass for real users.
- [ ] Golden questions rewritten with the customer's names; `make eval` meets the agreed thresholds.
- [ ] LLM endpoint approved by security; model version pinned; prompts contain no row-level data.
- [ ] Employee-data access and minimum group size agreed; privacy review done.
- [ ] Decision on conversation history across sessions (retention, deletion, who can see it).
- [ ] SSO in front of the UI; audit log enabled.
