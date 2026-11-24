# Evaluation report

135 golden questions (tests/golden_questions.yaml), backend `mssql`, as-of date 2026-11-16. Expected numbers are computed by raw SQL on the base tables (tests/eval_dsl.py), independently of the semantic layer. Default model: `ollama/qwen2.5-coder:14b`. All local models ran on CPU (Ollama, no GPU).

## Model comparison

| Model | Questions | Status as expected | Tool choice (final) | Tool choice (LLM alone) | Numbers in tool output | Headline number in answer text | RLS pass rate | Guardrail first pass / rewrite / redacted / template | Latency p50 / p95 (s) |
|:---|---:|---:|---:|---:|---:|---:|---:|:---|:---|
| `ollama/gpt-oss:20b` | 135 | 100% (135/135) | 100% (127/127) | 99% (126/127) | 98% (122/124) | 99% (121/122) | 100% (11/11) | 93% / 6% / 0% / 2% | 15.3 / 26.2 |
| `ollama/qwen2.5-coder:14b` | 135 | 100% (135/135) | 100% (127/127) | 99% (126/127) | 100% (124/124) | 100% (122/122) | 100% (11/11) | 87% / 4% / 2% / 8% | 25.6 / 37.5 |
| `rules` (no LLM, deterministic router + templated text) | 135 | 100% (135/135) | 100% (127/127) | n/a | 100% (124/124) | 100% (122/122) | 100% (11/11) | n/a | 0.1 / 0.5 |

How to read the columns:

- **Tool choice (final)**: the tool that produced the answer is in the accepted list. When the LLM returns no usable tool call (or its call fails), a deterministic router supplies one.
- **Tool choice (LLM alone)**: the LLM's own first tool call was valid and accepted, without the router.
- **Numbers in tool output**: every expected value (SQL ground truth) is present in the table / tool output, within 1 USD or 1e-6 for ratios.
- **Headline number in answer text**: the headline value(s) appear in the written answer within display rounding (for example USD 54.4M or 17.0%).
- **Guardrail**: share of LLM answers that passed the numeric check first time, passed after one rewrite, passed after dropping the sentences with unsupported numbers, or were replaced by the templated answer.

## Narrative checks

Answers whose drafts the guard rejected, by reason (an answer can have several), and sentences dropped from accepted answers because they gave causes that the data does not contain.

| Model | LLM answers | Number not in data | Number tied to the wrong month or leaver type | Scope named too broadly | Cause not in data (headline) | Sentences dropped (answers) |
|:---|---:|---:|---:|---:|---:|---:|
| `ollama/gpt-oss:20b` | 127 | 6 | 1 | 0 | 0 | 20 (20) |
| `ollama/qwen2.5-coder:14b` | 127 | 17 | 1 | 0 | 0 | 36 (33) |

## Per category: `ollama/gpt-oss:20b`

| Category | Questions | Status | Tool | Numbers (data) | Numbers (text) | p50 latency (s) |
|:---|---:|---:|---:|---:|---:|---:|
| pnl | 10 | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 20.2 |
| trend | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 21.2 |
| ratio | 11 | 100% (11/11) | 100% (11/11) | 100% (11/11) | 100% (11/11) | 9.7 |
| drivers | 8 | 100% (8/8) | 100% (8/8) | 88% (7/8) | 100% (8/8) | 16.9 |
| ranking | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 13.8 |
| versions | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 14.0 |
| cockpit | 4 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 19.5 |
| followup | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 16.7 |
| conversation | 12 | 100% (12/12) | 100% (10/10) | 90% (9/10) | 90% (9/10) | 14.9 |
| rls | 7 | 100% (7/7) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 13.3 |
| clarification | 2 | 100% (2/2) | n/a | n/a | n/a | 0.0 |
| robustness | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 17.6 |
| workforce | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 14.0 |
| catalog | 10 | 100% (10/10) | 100% (10/10) | 100% (7/7) | 100% (6/6) | 8.5 |
| margin | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (5/5) | 10.4 |
| sidebar | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 18.6 |
| resume | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 20.0 |
| landing | 15 | 100% (15/15) | 100% (14/14) | 100% (14/14) | 100% (14/14) | 19.6 |

Questions with at least one failed check: 2

| id | status | tool | data | text | note |
|:---|:---|:---|:---|:---|:---|
| drv_co_personnel_split | ok (exp. ok) | variance_drivers | False | True | expected 1.44e+07 (eur) not in output not in text; expected 3.269e+06 (eur) not in output not in text |
| conv_not_ytd_full_year | ok (exp. ok) | get_pnl | False | False | expected 1.52e+07 (eur) not in output not in text |

## Per category: `ollama/qwen2.5-coder:14b`

| Category | Questions | Status | Tool | Numbers (data) | Numbers (text) | p50 latency (s) |
|:---|---:|---:|---:|---:|---:|---:|
| pnl | 10 | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 33.0 |
| trend | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 37.1 |
| ratio | 11 | 100% (11/11) | 100% (11/11) | 100% (11/11) | 100% (11/11) | 17.8 |
| drivers | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 27.2 |
| ranking | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 21.5 |
| versions | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 24.5 |
| cockpit | 4 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 24.9 |
| followup | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 26.7 |
| conversation | 12 | 100% (12/12) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 27.1 |
| rls | 7 | 100% (7/7) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 17.9 |
| clarification | 2 | 100% (2/2) | n/a | n/a | n/a | 0.0 |
| robustness | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 24.9 |
| workforce | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 22.7 |
| catalog | 10 | 100% (10/10) | 100% (10/10) | 100% (7/7) | 100% (6/6) | 13.3 |
| margin | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (5/5) | 17.7 |
| sidebar | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 28.5 |
| resume | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 29.6 |
| landing | 15 | 100% (15/15) | 100% (14/14) | 100% (14/14) | 100% (14/14) | 26.3 |

Questions with at least one failed check: 0


## Per category: `rules`

| Category | Questions | Status | Tool | Numbers (data) | Numbers (text) | p50 latency (s) |
|:---|---:|---:|---:|---:|---:|---:|
| pnl | 10 | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 0.2 |
| trend | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.2 |
| ratio | 11 | 100% (11/11) | 100% (11/11) | 100% (11/11) | 100% (11/11) | 0.2 |
| drivers | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.1 |
| ranking | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.3 |
| versions | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 0.1 |
| cockpit | 4 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 0.4 |
| followup | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 0.1 |
| conversation | 12 | 100% (12/12) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 0.1 |
| rls | 7 | 100% (7/7) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 0.1 |
| clarification | 2 | 100% (2/2) | n/a | n/a | n/a | 0.0 |
| robustness | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 0.1 |
| workforce | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.1 |
| catalog | 10 | 100% (10/10) | 100% (10/10) | 100% (7/7) | 100% (6/6) | 0.0 |
| margin | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (5/5) | 0.2 |
| sidebar | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 0.1 |
| resume | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 0.1 |
| landing | 15 | 100% (15/15) | 100% (14/14) | 100% (14/14) | 100% (14/14) | 0.3 |

Questions with at least one failed check: 0


## Row-level security

Questions asked by a restricted persona (United States Country Head or Environmental Lab Testing PL Leader): out-of-scope requests must be refused without a table or SQL; in-scope requests must return the scoped numbers, and other units' names must not appear.

| Model | RLS questions | Passed | Refusals correct | Scoped answers correct |
|:---|---:|---:|---:|---:|
| `ollama/gpt-oss:20b` | 11 | 100% (11/11) | 100% (4/4) | 100% (7/7) |
| `ollama/qwen2.5-coder:14b` | 11 | 100% (11/11) | 100% (4/4) | 100% (7/7) |
| `rules` | 11 | 100% (11/11) | 100% (4/4) | 100% (7/7) |

## Landing

Tool choice on the landing questions (category `landing`) and the landing engine's measured backtest accuracy (`make backtest`, last 24 closed months; docs/landing_backtest_report.md).

| Model | Landing questions | Tool choice (final) | Tool choice (LLM alone) | Numbers in tool output | Headline number in answer text |
|:---|---:|---:|---:|---:|---:|
| `ollama/gpt-oss:20b` | 15 | 100% (14/14) | 100% (14/14) | 100% (14/14) | 100% (14/14) |
| `ollama/qwen2.5-coder:14b` | 15 | 100% (14/14) | 100% (14/14) | 100% (14/14) | 100% (14/14) |
| `rules` | 15 | 100% (14/14) | n/a | 100% (14/14) | 100% (14/14) |

Backtest run 2026-11-16: group-level WAPE by method (lower is better).

| Method | Billing | Revenue | Operating profit (excl. WIP) | Operating profit (as booked) |
|:---|---:|---:|---:|---:|
| IRIS landing (weighted ensemble) | 0.99% | 3.13% | 6.95% | 19.21% |
| Latest forecast as published | 2.28% | 2.31% | 8.55% | 8.66% |
| Same month last year x recent growth | 1.09% | 3.02% | 7.49% | 18.42% |
| Trailing 12 months x seasonal index | 2.10% | 4.15% | 11.70% | 23.53% |
| Latest forecast x the BU's forecast accuracy | 1.25% | 2.53% | 8.91% | 16.00% |
| Exponential smoothing (ETS) | 1.44% | 3.28% | 8.09% | 19.37% |

Share of actuals inside the P10-P90 range (billing, target 70-90%): BU 73.7%; Business 78.7%; Country 87.9%; Group 95.8%; Product line 87.0%; Region 93.3%.

