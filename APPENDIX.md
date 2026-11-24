# Appendix

Detailed progression, what worked and what did not, and extended caveats. The short version is
in [README.md](README.md); raw outputs are in [`results/`](results/).

## 1. Environment and constraints

| Constraint | What happened | Resolution |
|---|---|---|
| Corporate laptop | Docker, Colima, the uv-managed Python 3.11 and Ollama are blocked by device policy | Everything runs on an existing Kubernetes CPU node pool (2× 44-vCPU nodes). Only `kubectl` runs on the laptop |
| Shared CPU nodes | Other services *reserve* about 96% of each node's CPU but use almost none of it | Pods request little (≈1 vCPU in total) with high limits, so they use idle capacity and yield under contention. Existing services were not touched |
| Access to the UI | IRIS is local and private: no public endpoint, tunnel, LoadBalancer, NodePort or Ingress | The UI is reached with `make k8s-forward` (authenticated port-forward to a ClusterIP Service) or `make run` on localhost. The earlier public-tunnel and hosted-demo targets were removed |
| Docker validation | No Docker daemon available | The Dockerfile was built in-cluster with kaniko (`--no-push`) in about 63 s; log in `results/build/` |
| Vertex AI Gemini comparison | (1) Project IAM change denied for the user account. (2) The user's OAuth token type is rejected by Vertex AI (`ACCESS_TOKEN_TYPE_UNSUPPORTED`). (3) The pod's Workload Identity reaches Vertex but lacks `aiplatform.endpoints.predict` | Not run. One IAM binding (`roles/aiplatform.user` for the dev service account) enables it; the code path is in place (`LLM_MODEL=vertex_ai/gemini-2.5-flash`) |
| GitHub | No token on the laptop, and its SSH key is not registered with GitHub (`Permission denied (publickey)`) | Local git repo + `scripts/publish_github.sh` (`GITHUB_TOKEN=... ./scripts/publish_github.sh`) |

## 2. Progression

1. **First version: "XYZ Group", Europe, EUR.** Data, SQL Server load, DuckDB export and reconciliation passed. It was superseded by the re-theme below.
2. **Re-theme to RL Certification & Inspection (Americas, USD).**
   - The P&L was rebuilt with the line structure of a typical TIC monthly management report (revenue, production, personnel, subcontracting, other and functional costs, operating profit, EBIT, net income).
   - The org became 5 regions and 11 countries, with 8 sectors.
   - Operational KPIs (direct margin, utilization, production per hour / FTE, overtime ratio, production hourly cost) were added as statistics, ratios and the `get_kpi_cockpit` tool.
3. **Data, semantic layer, agent, UI, evaluation and packaging** (first full version) on an earlier dataset with customer-style labels. Its raw evaluation records are not kept in the repository because they contain those labels.
4. **Generic labels, Environmental Lab Testing scope, employee records:**
   - All labels are generic: "Operating profit" and "EBIT" instead of customer-specific line names, "general ledger (GL) P&L" instead of a report name, "constant budget rate" instead of a rate code, no account codes or line numbers in labels, no real place or person names. Customer terms still work in questions as synonyms.
   - KPI levels were moved away from any real dashboard values (utilization about 74%, overtime about 6%).
   - Environmental Lab Testing exists only in Canada (5 BUs) plus one small US unit; the lost-contract story moved to Canada Environmental Lab Testing.
   - New fictional employee records (27,360 employees, 937,506 employee-months) that add up exactly to the BU statistics, a `get_workforce` tool, 11 workforce golden questions (82 in total) and 4 workforce example buttons.
   - The data has 106 BUs, 1,168,756 P&L fact rows and 31,588 statistics rows; 0 mismatches over 300 subtotal checks.
5. **Narrative checks.** The guard also checks that a number next to a month (or labelled restructuring / voluntary) belongs to that month or type, that small numbers stated as a difference exist, that the scope is named in full, and that reasons come from the data; sentences with other reasons are dropped. Leavers facts state each change. The run before this step is kept in `results/eval/earlier/`; section 3 quotes it.
6. **Conversation memory** (current version).
   - Corrections replace only the part they name: "No, I meant Uruguay", "not YTD, full year 2025", "use Q3 2026 rather than YTD". A negated phrase is removed before parsing only if it starts with a period, measure, comparison, workforce figure or org, so "BUs that did not meet budget" keeps its meaning.
   - "How does that compare with last year?" is a prior-year comparison, not a switch to last year's period.
   - Follow-ups keep the P&L line asked about ("now for Canada" after a net income question answers with net income).
   - Reference words anywhere ("that", "it", "same", …) make a follow-up when the question does not name both a measure and a scope.
   - Pushback without details ("that's not right", "are you sure?") is answered with the measure, scope, period, comparison and source of the previous answer, and one button per part to change (each button is a complete follow-up question). The memory stays as it was.
   - The LLM planner sees the last five questions and what each used. If its tool call repeats a corrected-away period or measure, that argument is dropped or replaced.
   - Follow-up answers show what was carried over ("↪ Carried over: Net income · YTD Oct 2026").
   - 12 test conversations were added (category `conversation`, 94 questions in total). In rules mode, the previous code passed 4 of the 12 (`results/eval/earlier/rules_before_conversation_fixes.jsonl`).

## 3. What did not work at first, and the fix

| Symptom | Cause | Fix |
|---|---|---|
| The LLM wrote that production "outperformed budget" when it was below budget, and called cost increases "neutral" | Small CPU models infer directions badly from raw numbers | Facts spell out every comparison ("USD 1.8M (2.9%) below Budget (USD 61.0M), unfavourable") and the main reasons ("Operating profit vs PY: increase of USD 3.2M driven by …, partly offset by …"). The LLM writes only 2–4 sentences; key-figure bullets are added deterministically |
| Bridge items labelled "neutral" | `numpy.bool_` is not `True`, so favourability text fell through to "neutral" | `_fav_word` accepts any truthy value and treats NaN as neutral |
| The planner step was slow on every question | Ollama with one slot re-processed the long planner prompt after every writer call | `OLLAMA_NUM_PARALLEL=2`: planner and writer keep their own KV cache, so the planner prompt is not re-processed |
| qwen2.5-coder returns tool calls as JSON text, not native calls | Model / template behaviour in Ollama | The text tool-call parser recovers them; the source is recorded per answer (`llm_text`) |
| qwen never chose the new workforce tool by itself | The text tool-call parser had its own hard-coded list of tool names, without the new tool, so its calls were dropped and the router answered | The parser list now includes the tool, and a test checks that it covers every tool |
| "why is the first one so low?" answered for the whole group | Follow-ups did not remember ranked entities | Memory stores the ranked / drilled entities; ordinal references resolve to them |
| "H1 2026" lost after routing | The router passed "2026-01 to 2026-06", which the parser read as January | Explicit month-range patterns (ISO and month names) |
| "Mexcio" not recognised | The similarity cutoff (86) missed a transposition (83) | One adjacent-letter swap is accepted; substitutions stay strict so "lower" never becomes "power" |
| "latest forecast for the full year" returned YTD numbers | Comparisons were truncated like-for-like to the last Actual month | Full-year version view: Budget and forecasts for Jan–Dec, Actual left out with a note |
| Bonus / restructuring questions answered with the line-level P&L | Leaf metrics were routed to `get_pnl` | Leaf and group metrics route to `variance_drivers` (total vs PY, account and org drill-down) |
| "Split personnel into direct and indirect" showed leaf accounts only | Depth-2 breakdown skipped the direct / indirect staff level | Breakdowns also return sub-group totals |
| Trend facts averaged monthly percentages | Yearly values were the mean of monthly ratios | Yearly ratio = sum(numerator) / sum(denominator) over the months shown |
| Schema test failed on SQL Server syntax | sqlglot cannot parse `SELECT @sql += …` | The test parses only the CREATE TABLE statements |
| UI deprecation warnings | `use_container_width` is deprecated in Streamlit 1.67 | `width="stretch"` |
| Operating profit bridge steps barely visible | The waterfall axis started at zero, with totals of about USD 50M and steps of a few USD M | The value axis zooms when every running level is positive and the lowest is at least 35% of the highest (`tests/test_charts.py`) |
| qwen's answer to "What is the net income of Mexico this year?" never stated net income | The P&L key-figure bullets always used the same lines (production, personnel, gross profit), and the guardrail had dropped the narrative sentence that held the figure | The line the question asks about is always the first bullet |
| The same answer said "lower net income" with nothing to compare against | The LLM planner asked `get_pnl` for Actual only, and the tool followed it | Unless the user names versions or comparisons, `get_pnl` always adds PY and Budget, as the rules router does |
| Some redacted answers opened with "This improvement is driven by …" | The guardrail had dropped the first sentence (the headline), so the rest pointed back to a sentence that was gone and could keep unsupported causes | If the headline sentence has to be dropped, the templated answer is used instead |
| On the earlier dataset, qwen reported the operating profit as the "restructuring costs" of the lab business with the lost contract | The LLM picked `get_pnl`. The restructuring account was in the table but not in the facts, so the model reused a nearby number, and the guardrail passed it because that number exists in the output | When the question names an account or sub-group, `get_pnl` includes it (deeper account level if needed) and states it as the first fact and bullet. The operating-profit variance explanation is left out of such answers: with it in the facts, qwen stated the right restructuring figure but explained the increase with a production change that went the other way |
| llama answered "How is Colombia doing vs budget?" with Budget figures presented as results ("all above budget") | The planner asked `get_pnl` for Budget only, so Budget became the main version | For a comparison question ("vs", "against", "compared") on a closed period, Actual is always the main version |
| llama's answers to "Why is subcontracting above budget?" and "How is the whole group doing vs budget?" gave the gaps but not the amounts | Driver bullets started with the accounts, and P&L bullets without a named line skipped the headline profit line | Driver bullets start with the total and its change; P&L bullets start with operating profit when no line is named |
| llama answered "now for Canada" (after a P&L question) with the KPI cockpit | The follow-up changed only the scope, but the LLM picked a different tool | A pure follow-up keeps the previous turn's tool. The eval counts this as a router decision, not the LLM's |
| The numeric guardrail ignored counts followed by a word ("62 restructuring", "353 employees") | The check that skips internal account codes (digits followed by a letter) looked at the first letter after the number *and the following space*, so any number followed by a word was skipped | Only a letter directly after the digits marks a code; counts followed by a word are now checked |
| A restructuring month showed an attrition rate of almost 200% in the monthly view (April 2026: 63 leavers × 12 / 390 headcount) | A single month annualised exaggerates one-off exits | Monthly rows show attrition over the rolling 12 months to that month; period totals stay annualised over the period |
| "Turnover" questions could mean revenue or attrition | Finance teams use "turnover" for revenue | "Turnover" alone stays revenue; "staff turnover" or "turnover rate" goes to the workforce tool |
| qwen wrote "with 63 restructuring leavers in Apr 2026"; April had 63 leavers, 60 of them restructuring | The numeric guardrail only checked that a number exists somewhere in the tool output, not which month or leaver type it belongs to | Month binding: a number next to a single month must be one of the numbers the data ties to that month, and a count labelled restructuring or voluntary must be that type. Checked per clause; period bounds ("YTD Oct 2026", "Jan–Jun 2026") and the question's own month are skipped |
| qwen wrote "62 restructuring leavers this year, 30 above PY (32)" and llama "with 62 restructuring, which is 30 (30) more than the prior year (PY 32)"; the prior year had 3 restructuring leavers | The leavers fact gave prior-year counts without a comparison phrase, so the models computed one and paired the total's prior year with one leaver type; numbers up to 31 were never checked | Leavers facts state each change, and restructuring and voluntary leavers get their own lines ("Restructuring leavers: 62; 59 more than PY (3)"). A change stated for a leaver type must be that type's change, and small numbers are checked when stated as a difference ("30 above") |
| After "now for the United States", qwen wrote "The attrition rate in the United States is 15.5%" for the US Environmental Lab Testing unit (31 people) | The writer shortened the scope | Scope check: an answer may not name the country without the business line it was asked about. The writer is told to name the scope as the facts do |
| Answers gave causes that are not in the data ("driven by higher sales volumes and improved cost management"; "Operating margins in Argentina have been stable, with no significant changes in drivers") | Small models fill in typical business explanations | Sentences with cause words that the facts never mention, or with a "driven by / due to / reflecting" clause that names no line, account, driver, role, BU or month from the data, are dropped. In the headline sentence the answer is rewritten once, then the templated answer is used |
| "Highest attrition first" listed roles at 0.0% for a small unit | The breakdown fact listed every row | Zero values are summarised ("5 other roles 0.0%") |
| The LLM asked the workforce tool for "leavers" when the question said "restructuring leavers" | The tool took the LLM's argument over the question | When the question names the narrower figure (restructuring leavers, voluntary attrition), the question wins |
| "What is the MAOP margin of Paraguay this year?" got "The MAOP margin for Paraguay …" | The writer copied the question's wording | The narrative uses the app's names (operating profit, operating margin, EBIT) |
| "not YTD, full year 2025" (after a Mexico question) still answered for YTD | Negations were not handled, so "YTD" was read as the period | Negated phrases that name a period, measure, comparison, workforce figure or org are removed before parsing |
| After "What is the net income of Mexico this year?", "now for Canada" answered with operating profit | The follow-up kept the measure in memory, but the P&L tool took the line to show from the current question only | The carried measure is passed to the tools |
| "How does that compare with last year?" (after a Peru margin question) answered for FY 2025 | "compare with" was not among the prior-year phrases, so "last year" was read as a period | "compare (that) with last year" is a prior-year comparison |
| "That's not right" re-ran the previous question | Pushback was not recognised | The reply lists what the previous answer used, with one button per part to change |

## 4. Evaluation details

- **Expected values.** `tests/eval_dsl.py` compiles small specs (measure, org, period, version, ranking, workforce figure) straight to SQL on the base tables. It does not use the semantic layer, the views or the metric registry.
- **Checks per question:** status (ok / refusal / clarification), primary tool, every expected value in the tool output, headline value(s) in the answer text, RLS behaviour, guardrail outcome and the narrative problems it found, sentences dropped, latency. A pushback question also needs at least the expected number of change buttons.
- **Golden set.** 135 questions. The 94 of the earlier version: P&L, trends, ratios, drivers, rankings, versions, KPI cockpit, follow-ups, row-level security, clarification, robustness (typos, leaf accounts, three questions that use customer terms as synonyms), 11 workforce questions and 12 multi-turn conversations (corrections, negations, "compare with last year", references such as "that" or "the same business", and pushback). Added with IRIS: 10 data-catalog questions (two of them as restricted personas, with names that must not appear), 6 margin questions (both margins when no base is named, one when it is), 5 sidebar-filter questions (the filters are passed like the UI does; the question's words win), 5 resumed conversations (the earlier turns are stored in the conversation store and reloaded before the follow-up) and 15 landing questions (BU, business, country and group; YTD including the landing; vs budget, forecast and last year; which BUs miss budget; closed and future months; row-level security). Landing expectations are computed from `fact_landing` and `fact_pnl` with raw SQL, independently of the semantic layer.
- **Rules baseline.** The deterministic router without an LLM failed several checks on its first run; after the fixes above it passes every check. The golden set and the router were developed together, so the rules score shows what the semantic layer supports. It is not a generalisation measure.
- **LLM fixes came from the same questions.** The LLM-side fixes in section 3 were found by reading answers on this golden set and in the UI, and the 12 conversations were written together with the conversation fixes, so the scores are not held-out either. The fixes are general rules (state the figure that was asked for, Actual as the main version, keep the tool on a pure follow-up, keep numbers with their month, type and scope, replace only the corrected part), not per-question patches. Earlier runs are kept in `results/eval/earlier/`.
- **LLM runs.** Each LLM run answers the same questions; multi-turn questions replay their earlier turns. All local models ran on CPU through Ollama 0.40.16.
- **UI checks.** `scripts/ui_walkthrough.py` follows [docs/demo_script.md](docs/demo_script.md) in a headless browser (Playwright) against the running app: sign-in, the About and Data Catalog pages (header present, no old project name), a catalog question, a sidebar filter and the question's own words winning over it, a restricted persona (catalog answer and refusal), both margins, the November landing, the BUs that miss budget (as a follow-up and in a new conversation), the YTD margin including the landing, a conversation with a follow-up, a pushback and a change button, and reopening that conversation from the sidebar. In rules mode all 20 steps passed with every expected figure (`results/ui_walkthrough/rules/`), and in LLM mode (`qwen2.5-coder:14b`) all 4 steps passed with direct LLM tool calls and passed numeric guardrails (`results/ui_walkthrough/llm/`). `scripts/ui_screenshots.py` signs in and takes rules-mode screenshots of 12 answers in `results/ui_screenshots/rules_mode/`. The headless tests in `tests/test_ui.py` check the header and footer on all four pages.

The full per-model results are in [eval_report.md](eval_report.md) and `results/eval/*.jsonl`.

**Model licenses** (checked on the license pages after the first benchmark runs; the license text packaged with each downloaded Ollama model is the same):

| Model | License | Restrictions that matter here |
|---|---|---|
| `qwen2.5-coder:14b` | Apache 2.0 ([license](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct/blob/main/LICENSE)) | None beyond attribution and notice |
| `gpt-oss:20b` | Apache 2.0 with OpenAI's gpt-oss usage policy ([license](https://huggingface.co/openai/gpt-oss-20b/blob/main/LICENSE), [policy](https://huggingface.co/openai/gpt-oss-20b/blob/main/USAGE_POLICY)) | The policy asks users to comply with applicable law |
| `llama3.1:8b` | Llama 3.1 Community License ([license](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE)) | Section 2: a licensee whose products had more than 700 million monthly active users on the release date must request a separate license from Meta; "Built with Llama" attribution (1.b.i); acceptable use policy (1.b.iv). It was evaluated on the earlier code (`results/eval/earlier/llama3.1-8b_before_narrative_checks.jsonl`) and is not part of later evaluations |

## 5. Caveats

- **Synthetic data.** All companies, people, figures and stories are invented; see `docs/assumptions.md`.
- **CPU latency.** Local LLMs ran on a shared CPU node, with no GPU. Interactive production use needs a GPU-backed or managed model endpoint.
- **Guardrail scope.** The guard checks that every number exists in the tool output, that a number next to a single month (or labelled restructuring / voluntary) matches that month or type, that small numbers stated as a difference exist, that the scope is not named more broadly than asked, and that causes name something in the data. It does not check:
  - which entity a number belongs to within the same period (two roles with numbers that both exist in the output);
  - numbers tied to a month that is more than a few words away, or clauses that name two months;
  - causes written without a cause phrase ("driven by", "due to", "reflecting", …) or a listed cause word.
  The table and the bullets always come straight from the data; the narrative should be read as a summary of them.
- **Workforce data.** Employee records exist for closed months only and have no budget, so workforce answers compare with the prior year only.
- **Personas.** Three personas demonstrate row-level security; production would map real entitlements (see `docs/production_migration.md`).

## 6. IRIS rebuild

The prototype was renamed IRIS (Intelligent Reporting & Insight System) and extended in nine steps. Each
step kept the semantic layer, row-level security, the SQL guard, the numeric guardrail and the evaluation
working.

| Step | What changed |
|---|---|
| Rebrand | Product name, logo, header on every page, sidebar footer and page title from `app/ui/branding.py` only (a test fails if another file hardcodes them); database, logins and Kubernetes names renamed; the public-tunnel and hosted-demo targets removed (`make tunnel` / `make hf` now explain why and stop) |
| Navigation | Top navigation (Chat, Data Catalog, User Guide, About), quick-guide dialog, hidden Deploy button, demo sign-in before any page |
| Margins | Operating margin on revenue and on production defined once; "profit %", "margin", "MAOP %" and similar words without a base return both side by side; zero or negative denominators show n/a |
| Sidebar filters | Cascading Region -> Country -> Product line -> Business -> BU, Version and Period, filtered by row-level security; they are the default context, the question's words win, and every answer lists where each filter came from |
| Data Catalog | Eight live tabs (coverage, organisation, lines and metrics, ratios, versions and close calendar, landing, data and sources, capabilities), the `describe_catalog` tool for discovery questions, and `docs/data_manual.md` from the same functions |
| Landing | Regenerated data with billing patterns, working-day calendars and planner bias; the landing engine, its backtest, four landing tools, three landing charts and the virtual version `LANDING` |
| User Guide | `docs/user_guide.md`, rendered in the app with clickable examples and screenshots; a first-visit welcome card |
| Conversations | The last 10 conversations per user with full answer payloads (reopened without the LLM or the database), rename, pin, delete, retention in one transaction, user isolation on every query |
| Tests and evaluation | 41 new golden questions, landing support in the independent SQL fixtures, row-level-security and landing sections in the report, and unit tests for every new part |

**Libraries added:** `statsmodels` (exponential smoothing, method M4 of the landing) and `holidays` (public
holiday calendars for working days). `bcrypt` was not needed: the demo access code is compared with
`hmac.compare_digest`, and no password is stored.

### What did not work at first, and the fix

| Problem | Cause | Fix |
|---|---|---|
| In the headless UI tests every run after the first rendered an empty page | The page modules lived in `app/ui/pages/`, a folder name Streamlit treats as the old multipage layout, which conflicts with `st.navigation` in the test runner | Pages moved to `app/ui/views/`; the same change keeps those modules from appearing as pages before sign-in |
| "Which business units are in Mexico?" was answered with a ranking | The discovery pattern did not cover "which ... are in ..." | Discovery questions of that form go to the catalog unless they name a measure or a condition ("in the red", "below budget") |
| A check that other countries do not appear failed for the United States Country Head | The region name "US & Canada" contains "Canada" | The golden question lists other countries (Mexico, Brazil, Chile, Argentina) |
| "November landing" could be read as November of last year | Month names default to the latest closed month of that name | In a landing question a month name means the open month of this year; closed months return actuals and future months the latest forecast |
| The group P10-P90 range was built with an unweighted average of BU errors as the common shock | Small, volatile BUs moved the group range as much as large ones | The common shock is weighted by BU size; the group range is still wider than needed (coverage 95.8%, reported in the backtest report) |
| Revenue and operating profit landings looked much worse than the forecast | The landing sets WIP to 0 in the landing month, while booked actuals include the month's WIP movement | The backtest also reports operating profit and margins like-for-like (WIP removed on both sides); both views are in the report |
| "Clear filters" did not always reset the sidebar | Widget state was cleared during the run instead of before it | The button and the persona selector use callbacks |
| In the first IRIS evaluation, gpt-oss:20b answered "What is the MOP % of the United States vs budget this year?" with the revenue margin only; the production margin appeared as "1.9 pp above Budget" without its value | The key-figure lines for the margin pair gave only the change against each comparison; the values were in a fact the model may rephrase or skip | One line per margin that starts with its actual value (like the P&L lines), and a note under every such answer: "No margin base was named, so both operating margins are shown" |
| gpt-oss:20b called the ratio tool for "MAOP for Canda env lab last month" (the router then answered correctly) | The prompt listed "MAOP %" as margin wording but did not say that "MAOP" alone is an amount | One sentence in the prompt: "MAOP" or "MOP" without "%" or "margin" is operating profit |
| "Which product lines can I ask about?" failed the text check although the answer named all eight | The check looked for the count only | The check passes when the text has the count or names every expected item (all models) |
| `make k8s-deploy`, `make k8s-env` and `make k8s-cronjob` failed with a shell quoting error | `#` starts a comment in a Makefile variable, so the manifest rendering stopped at the new workspace-path substitution (`s#...#...#`) | The substitution uses a vertical bar as separator; a test checks that every placeholder under `deploy/` is substituted |
| Streamlit printed an "External URL" with a public IP when the app container started | With `--server.address 0.0.0.0` in headless mode, Streamlit looks up the machine's public IP for its startup message. The app was not reachable there: the Service is ClusterIP and the pod uses no host port | `browser.serverAddress = "localhost"` in `.streamlit/config.toml`: no lookup, and the startup message shows the localhost URL |
| In the browser walkthrough, questions after a visit to About and Data Catalog were answered by the default LLM although the session had started with `?model=rules` | The model selector took its default from the URL parameter, and page switches in the top navigation drop URL parameters | The selector keeps its value in the session and reads the URL parameter once, on the first page load (headless UI test added) |
| In the demo script, "Which BUs are expected to miss budget this month?" right after the United States landing answered for the United States (7 of 16 BUs) instead of the group | Without a scope in the question it is a follow-up, and the conversation keeps the previous scope | The demo script starts a new conversation for that step and says why; the walkthrough checks both answers |

### Landing backtest

Measured by `make backtest` over November 2024 to October 2026 (24 closed months, each computed as of the
15th of its month with the data available then). Full tables in
[docs/landing_backtest_report.md](docs/landing_backtest_report.md).

- Group billing WAPE: 0.99% for the landing vs 2.28% for the latest forecast as published (goal met).
- BU billing WAPE: 6.42% vs 7.92%; BU actuals inside P10-P90: 73.7% (goal 70-90%, met). The group-level
  coverage is 95.8%, above the band.
- Operating profit like-for-like (excluding WIP), group: 6.95% vs 8.55%. As booked: 19.21% vs 8.66%.
- Lumpy project BUs: 19.37% vs 17.75% for the latest forecast, the one pattern class where the forecast is
  better.
- The pattern classes found by the engine agree with the generator for 106 of 106 BUs; the estimated
  working-day elasticity is 0.68 (the generator uses 0.7).
- November 2026 (the open month, one month only): group billing P50 USD 120.46M vs the generator's hidden
  month-end USD 121.08M (-0.51%); the latest forecast is USD 121.86M (+0.64%).
