# IRIS - Intelligent Reporting & Insight System

*See your business clearly.* Developed and maintained by Rohan Luniya.

IRIS is a conversational analytics prototype for a fictional Testing, Inspection & Certification group: ask
about the monthly management P&L in plain English and get a short insight, a finance table, a chart, the
filters used, and a current-month landing estimate. On 135 golden questions the deterministic router passes
every check, and the current-month landing beats the latest published forecast on group billing in a 24-month
backtest (WAPE 0.99% vs 2.28%). All data is synthetic.

## Model, framework and hardware

| Part | What is used |
|---|---|
| Language models | `gpt-oss:20b` (20.9B parameters, mixture of experts, MXFP4 weights) and `qwen2.5-coder:14b` (14.8B dense, Q4_K_M), both on CPU through Ollama 0.40.16; `rules` = no LLM (deterministic router and templated text) |
| What the LLM does | Chooses a typed tool and writes 2-4 sentences from pre-computed facts; every number comes from a tool and a numeric guardrail checks the text |
| Landing engine | Deterministic Python (NumPy, pandas, statsmodels ETS, `holidays` calendars); never the LLM |
| App stack | Streamlit UI, LangGraph agent, LiteLLM, SQLAlchemy semantic layer, SQL Server 2022 with row-level security (DuckDB alternative), Plotly |
| Hardware | Kubernetes CPU node pool (2 x 44 vCPU nodes, shared); no GPU. Only `kubectl` runs on the laptop; the UI is reached through an authenticated port-forward |

Model licenses: `gpt-oss:20b` Apache 2.0 with OpenAI's usage policy; `qwen2.5-coder:14b` Apache 2.0 (details and
links in [APPENDIX.md](APPENDIX.md#4-evaluation-details)). Llama 3.1 was not considered for these evaluations.

## Main results

**Golden-question evaluation** (135 questions, SQL Server backend, as-of 2026-11-16; expected values from raw
SQL on the base tables, independent of the semantic layer). The 94 questions of the earlier version plus 41
new ones: data catalog, both margins, sidebar filters, resumed conversations and the current-month landing.

| Model | Status as expected | Tool choice | Numbers in tool output | Headline in text | Row-level security | Latency p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|
| rules (no LLM) | **135/135** | **127/127** | **124/124** | **122/122** | **11/11** | 0.2 s / 0.5 s |
| gpt-oss:20b | **135/135** | **127/127** | 122/124 | 121/122 | **11/11** | 15.3 s / 26.2 s |
| qwen2.5-coder:14b | **135/135** | **127/127** | **124/124** | **122/122** | **11/11** | 25.6 s / 37.5 s |

Before IRIS (same evaluation method, the 94 earlier questions): rules 94/94 status and 87/87 on every number
check; gpt-oss:20b 87/87 tool choice, 84/87 numbers in output; qwen2.5-coder:14b 86/87 tool choice, 86/87
numbers in output; 7/7 row-level security for all three.

**Current-month landing** (`make backtest`: the last 24 closed months, each computed with only the data
available at the time):

| Measure | IRIS landing | Latest forecast as published |
|---|---:|---:|
| Group billing WAPE | **0.99%** | 2.28% |
| BU billing WAPE | **6.42%** | 7.92% |
| BU actuals inside the P10-P90 range (target 70-90%) | **73.7%** | n/a |

The landing is weaker than the latest forecast for lumpy project BUs and for revenue and operating profit as
booked (the landing assumes WIP = 0 in the landing month); see
[docs/landing_backtest_report.md](docs/landing_backtest_report.md).

**Data checks:** 0 mismatches in 300 leaf-vs-subtotal checks ([report](results/reconcile_report_mssql.md));
234 automated tests pass.

## How to reproduce

On one machine with Docker (SQL Server in a container, everything on localhost):

```bash
cp .env.example .env        # set the SQL Server passwords and APP_ACCESS_CODE
make setup db-up
make data load landing run  # generate, load, compute the landing, serve on http://127.0.0.1:8501
make reconcile backtest data-manual test
make eval MODELS=rules,ollama/gpt-oss:20b,ollama/qwen2.5-coder:14b
```

On Kubernetes (how the results above were produced; only `kubectl` on the laptop, every Service ClusterIP):

```bash
cp .deploy.env.example .deploy.env   # cluster, namespace, node pool, kubeconfig path
make k8s-deploy k8s-models k8s-sync k8s-env
make k8s-make T="setup db-up data load landing reconcile backtest data-manual test"
make k8s-ready                       # start Streamlit in the app container
make k8s-access-code                 # the demo sign-in code (random, kept in the Kubernetes Secret)
make k8s-forward                     # UI on http://localhost:8501 (authenticated port-forward)
make k8s-make T="eval MODELS=rules,ollama/gpt-oss:20b,ollama/qwen2.5-coder:14b"
make k8s-pull                        # copy results, reports and generated docs back
```

| Make target | What it does |
|---|---|
| `data`, `load`, `reconcile` | Generate the synthetic data, load SQL Server (or DuckDB), check leaf sums against subtotals |
| `landing` | Current-month landing for the as-of date (`AS_OF=2026-09-15` for another date); idempotent |
| `backtest` | Landing backtest over the last 24 closed months; writes the report |
| `data-manual` | `docs/data_manual.md` from the live catalog |
| `test`, `eval`, `demo` | Unit, integration and headless UI tests; golden-question evaluation; saved demo answers |
| `run`, `k8s-forward` | UI on localhost only |
| `k8s-cronjob` | Optional private daily landing refresh |

Sign-in is a demo (display name + `APP_ACCESS_CODE`); production would use single sign-on.

## More detail

- [APPENDIX.md](APPENDIX.md): constraints, progression, what worked and what did not, evaluation method, caveats.
- [eval_report.md](eval_report.md): results per model and category, the row-level-security and landing
  sections, and every failed check; raw records in [`results/`](results/).
- [docs/](docs/): [user guide](docs/user_guide.md), [data manual](docs/data_manual.md),
  [architecture](docs/architecture.md), [landing methodology](docs/landing_methodology.md),
  [landing backtest report](docs/landing_backtest_report.md), [demo script](docs/demo_script.md),
  [demo stories](docs/demo_stories.md), data model, semantic layer, assumptions and the production path.
- [presentation_kit/](presentation_kit/): 12-slide executive presentation deck (`.pptx` and `.html`), 1080p demo video snippets (`videos/`), and companion screenshots (`screenshots/`).
