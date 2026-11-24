# Earlier evaluation runs

These runs are kept so the changes described in [APPENDIX.md](../../../APPENDIX.md) can be compared with raw
answers. They use the same models and hardware as the final results in [`results/eval/`](../); the agent
code, the number of questions and (for the runs before IRIS) the synthetic data differ.

| File | Questions | Agent code and data |
|---|---|---|
| `*_before_iris.jsonl`, `summary_before_iris.json`, `eval_report_before_iris.md` | the 94 questions before IRIS, as-of 2026-11-12 | The code and data just before the IRIS rebuild (after the conversation fixes). This is the baseline the IRIS results are compared with. The data was regenerated for IRIS (billing patterns, working-day calendars, forecast bias), so expected values differ between the two runs; the question wording is the same |
| `gpt-oss-20b_before_margin_answer_fix.jsonl` | all 135 IRIS questions, as-of 2026-11-16 | The first run of the IRIS code. Answers that showed both margins listed the production margin without its own value when the model's text named only one margin; plain "MAOP" was once read as a ratio; and the text check for list questions accepted only the count, not a list that names every item |
| `*_before_narrative_checks.jsonl` | the 82 questions before the test conversations were added | Before the narrative checks: numbers were checked for existence only (not for their month, leaver type or scope), causes were not checked, leaver facts had no per-type change, "highest first" breakdowns listed zero values, and customer terms from the question were repeated in answers |
| `summary_before_narrative_checks.json` | same | Summary of those runs, in the same format as `results/eval/summary.json` |
| `rules_before_conversation_fixes.jsonl` | the 12 test conversations only (category `conversation`), rules mode | Before the conversation fixes: negations were ignored, "compare with last year" changed the period, follow-ups lost the P&L line asked about, only short or "now / and / what about" questions counted as follow-ups, and pushback re-ran the question |

The final runs in `results/eval/*.jsonl` use the final code. Llama 3.1 was not part of the IRIS evaluations;
its earlier run is `llama3.1-8b_before_narrative_checks.jsonl`.
