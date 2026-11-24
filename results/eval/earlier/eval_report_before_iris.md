# Evaluation report

94 golden questions (tests/golden_questions.yaml), backend `mssql`, as-of date 2026-11-12. Expected numbers are computed by raw SQL on the base tables (tests/eval_dsl.py), independently of the semantic layer. Default model: `ollama/qwen2.5-coder:14b`. All local models ran on CPU (Ollama, no GPU).

## Model comparison

| Model | Questions | Status as expected | Tool choice (final) | Tool choice (LLM alone) | Numbers in tool output | Headline number in answer text | RLS pass rate | Guardrail first pass / rewrite / redacted / template | Latency p50 / p95 (s) |
|:---|---:|---:|---:|---:|---:|---:|---:|:---|:---|
| `ollama/gpt-oss:20b` | 94 | 100% (94/94) | 100% (87/87) | 100% (87/87) | 97% (84/87) | 98% (85/87) | 100% (7/7) | 94% / 5% / 0% / 1% | 15.0 / 23.9 |
| `ollama/qwen2.5-coder:14b` | 94 | 100% (94/94) | 99% (86/87) | 99% (86/87) | 99% (86/87) | 100% (87/87) | 100% (7/7) | 80% / 8% / 5% / 7% | 23.7 / 52.9 |
| `rules` (no LLM, deterministic router + templated text) | 94 | 100% (94/94) | 100% (87/87) | n/a | 100% (87/87) | 100% (87/87) | 100% (7/7) | n/a | 0.1 / 0.3 |

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
| `ollama/gpt-oss:20b` | 87 | 4 | 0 | 0 | 1 | 13 (13) |
| `ollama/qwen2.5-coder:14b` | 87 | 16 | 1 | 0 | 0 | 31 (28) |

## Per category: `ollama/gpt-oss:20b`

| Category | Questions | Status | Tool | Numbers (data) | Numbers (text) | p50 latency (s) |
|:---|---:|---:|---:|---:|---:|---:|
| pnl | 10 | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 21.6 |
| trend | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 13.2 |
| ratio | 11 | 100% (11/11) | 100% (11/11) | 100% (11/11) | 100% (11/11) | 7.0 |
| drivers | 8 | 100% (8/8) | 100% (8/8) | 88% (7/8) | 100% (8/8) | 15.2 |
| ranking | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 12.3 |
| versions | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 17.2 |
| cockpit | 4 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 18.5 |
| followup | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 15.4 |
| conversation | 12 | 100% (12/12) | 100% (10/10) | 80% (8/10) | 80% (8/10) | 16.7 |
| rls | 7 | 100% (7/7) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 12.9 |
| clarification | 2 | 100% (2/2) | n/a | n/a | n/a | 0.0 |
| robustness | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 14.2 |
| workforce | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 13.6 |

Questions with at least one failed check: 3

| id | status | tool | data | text | note |
|:---|:---|:---|:---|:---|:---|
| drv_co_personnel_split | ok (exp. ok) | variance_drivers | False | True | expected 1.44e+07 (eur) not in output not in text; expected 3.284e+06 (eur) not in output not in text |
| conv_not_ytd_full_year | ok (exp. ok) | get_pnl | False | False | expected 1.548e+07 (eur) not in output not in text |
| conv_meant_other_country | ok (exp. ok) | get_pnl | False | False | expected 3.926e+06 (eur) not in output not in text |

## Per category: `ollama/qwen2.5-coder:14b`

| Category | Questions | Status | Tool | Numbers (data) | Numbers (text) | p50 latency (s) |
|:---|---:|---:|---:|---:|---:|---:|
| pnl | 10 | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 30.8 |
| trend | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 44.0 |
| ratio | 11 | 100% (11/11) | 100% (11/11) | 100% (11/11) | 100% (11/11) | 17.1 |
| drivers | 8 | 100% (8/8) | 100% (8/8) | 88% (7/8) | 100% (8/8) | 26.9 |
| ranking | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 25.4 |
| versions | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 19.0 |
| cockpit | 4 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 27.4 |
| followup | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 23.0 |
| conversation | 12 | 100% (12/12) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 22.9 |
| rls | 7 | 100% (7/7) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 16.2 |
| clarification | 2 | 100% (2/2) | n/a | n/a | n/a | 0.0 |
| robustness | 5 | 100% (5/5) | 80% (4/5) | 100% (5/5) | 100% (5/5) | 23.7 |
| workforce | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 20.3 |

Questions with at least one failed check: 2

| id | status | tool | data | text | note |
|:---|:---|:---|:---|:---|:---|
| drv_co_personnel_split | ok (exp. ok) | variance_drivers | False | True | expected 1.44e+07 (eur) not in output not in text; expected 3.284e+06 (eur) not in output not in text |
| typo_canada_env_lab | ok (exp. ok) | get_ratio | True | True |  |

## Per category: `rules`

| Category | Questions | Status | Tool | Numbers (data) | Numbers (text) | p50 latency (s) |
|:---|---:|---:|---:|---:|---:|---:|
| pnl | 10 | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 0.1 |
| trend | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.1 |
| ratio | 11 | 100% (11/11) | 100% (11/11) | 100% (11/11) | 100% (11/11) | 0.1 |
| drivers | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.1 |
| ranking | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.3 |
| versions | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 0.1 |
| cockpit | 4 | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 0.3 |
| followup | 6 | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) | 0.1 |
| conversation | 12 | 100% (12/12) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 0.1 |
| rls | 7 | 100% (7/7) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 0.1 |
| clarification | 2 | 100% (2/2) | n/a | n/a | n/a | 0.0 |
| robustness | 5 | 100% (5/5) | 100% (5/5) | 100% (5/5) | 100% (5/5) | 0.1 |
| workforce | 8 | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 0.1 |

Questions with at least one failed check: 0


