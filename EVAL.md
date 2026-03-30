# Rubric Harness Eval — Run 5

The rubric harness is a generation-verification loop that generates task-specific scoring rubrics grounded in web research, then iterates generation and verification until a quality threshold is met. For each task it runs a baseline (single-shot generation) and a harness run (iterative regeneration guided by the rubric), then reports the score delta.

---

## Run 5 Results

| Task | Description | Baseline | Harness | Delta | Iters | Rubric | Output |
|---|---|---|---|---|---|---|---|
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 42.6% | 80.1% | +37.5pp | 4 | [rubric](eval_run5_artifacts/rubric_agi_counterargument.md) | [output](eval_run5_artifacts/output_agi_counterargument.md) |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 56.7% | 36.4% | −20.3pp | 5 | [rubric](eval_run5_artifacts/rubric_attention_explanation.md) | [output](eval_run5_artifacts/output_attention_explanation.md) |
| bash_backup | Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications | 62.4% | 80.7% | +18.3pp | 5 | [rubric](eval_run5_artifacts/rubric_bash_backup.md) | [output](eval_run5_artifacts/output_bash_backup.md) |
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing | 69.5% | 80.3% | +10.7pp | 5 | [rubric](eval_run5_artifacts/rubric_billing_schema.md) | [output](eval_run5_artifacts/output_billing_schema.md) |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 53.9% | 69.2% | +15.3pp | 4 | [rubric](eval_run5_artifacts/rubric_cold_outreach_email.md) | [output](eval_run5_artifacts/output_cold_outreach_email.md) |
| csv_parser | Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers | 55.2% | 73.5% | +18.3pp | 4 | [rubric](eval_run5_artifacts/rubric_csv_parser.md) | [output](eval_run5_artifacts/output_csv_parser.md) |
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 38.2% | 71.1% | +32.9pp | 4 | [rubric](eval_run5_artifacts/rubric_exec_summary.md) | [output](eval_run5_artifacts/output_exec_summary.md) |
| investment_memo | Draft a 1-page investment memo on a hypothetical Series A company in the defense drone space | 49.4% | 76.2% | +26.8pp | 3 | [rubric](eval_run5_artifacts/rubric_investment_memo.md) | [output](eval_run5_artifacts/output_investment_memo.md) |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define | 65.2% | 67.2% | +2.0pp | 3 | [rubric](eval_run5_artifacts/rubric_sql_ltv_query.md) | [output](eval_run5_artifacts/output_sql_ltv_query.md) |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review for mid-market law firms | 38.2% | 53.5% | +15.3pp | 4 | [rubric](eval_run5_artifacts/rubric_startup_naming.md) | [output](eval_run5_artifacts/output_startup_naming.md) |
| **MEAN (9 improved + 1 regressed)** | | **53.1%** | **68.8%** | **+15.7pp** | **4.1** | | |

---

## Run 4 → Run 5 Comparison

| Run | Mean Baseline | Mean Harness | Mean Delta | Tasks Improved |
|---|---|---|---|---|
| Run 4 | 46.9% | 72.9% | +26.0pp | 9/10 (1 FAILED) |
| Run 5 | 53.1% | 68.8% | +15.7pp | 9/10 (1 regressed) |

**Why the delta shrank:** Run 5 baselines are meaningfully higher (53.1% vs 46.9%) because the new multi-pass rubric pipeline generates harder, more comprehensive rubrics that are more demanding of the baseline. The harness recovered well on most tasks, but the higher floor leaves less room for gain.

**attention_explanation regression (−20.3pp):** This is the first outright regression across all runs. The harness overfit to rubric feedback and produced output that scored worse on `expl_accuracy` (correctness) and `expl_accessibility` (audience fit) than the baseline. The rubric may have over-constrained the rewrite toward technical depth at the expense of the 16-year-old framing. Needs investigation.

**agi_counterargument remains the strongest task (+37.5pp):** The steelman criterion, which scored 0% at baseline, drove most of the lift. Consistent across runs.

**sql_ltv_query near-neutral (+2.0pp):** The harness barely moved the needle, similar to Run 4 (where it also stalled at 67.2% final). This task may be near a ceiling for the current rubric design.

---

---

# Rubric Harness Eval — Run 4

## Run 4 Results

| Task | Description | Baseline | Harness | Delta | Iters | Rubric | Output |
|---|---|---|---|---|---|---|---|
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 36.4% | 83.3% | +46.9pp | 4 | [rubric](eval_run4_artifacts/rubric_agi_counterargument.md) | [output](eval_run4_artifacts/output_agi_counterargument.md) |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 55.4% | 63.2% | +7.8pp | 4 | [rubric](eval_run4_artifacts/rubric_attention_explanation.md) | [output](eval_run4_artifacts/output_attention_explanation.md) |
| bash_backup | Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications | 73.0% | FAILED | — | — | [rubric](eval_run4_artifacts/rubric_bash_backup.md) | [output](eval_run4_artifacts/output_bash_backup.md) |
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing | 62.2% | 78.3% | +16.1pp | 4 | [rubric](eval_run4_artifacts/rubric_billing_schema.md) | [output](eval_run4_artifacts/output_billing_schema.md) |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 47.3% | 71.9% | +24.6pp | 5 | [rubric](eval_run4_artifacts/rubric_cold_outreach_email.md) | [output](eval_run4_artifacts/output_cold_outreach_email.md) |
| csv_parser | Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers | 48.4% | 76.1% | +27.8pp | 5 | [rubric](eval_run4_artifacts/rubric_csv_parser.md) | [output](eval_run4_artifacts/output_csv_parser.md) |
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 40.5% | 71.1% | +30.5pp | 4 | [rubric](eval_run4_artifacts/rubric_exec_summary.md) | [output](eval_run4_artifacts/output_exec_summary.md) |
| investment_memo | Draft a 1-page investment memo on a hypothetical Series A company in the defense drone space | 40.1% | 78.3% | +38.2pp | 5 | [rubric](eval_run4_artifacts/rubric_investment_memo.md) | [output](eval_run4_artifacts/output_investment_memo.md) |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define | 55.6% | 67.2% | +11.7pp | 5 | [rubric](eval_run4_artifacts/rubric_sql_ltv_query.md) | [output](eval_run4_artifacts/output_sql_ltv_query.md) |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review for mid-market law firms | 36.1% | 66.7% | +30.6pp | 5 | [rubric](eval_run4_artifacts/rubric_startup_naming.md) | [output](eval_run4_artifacts/output_startup_naming.md) |
| **MEAN (9 valid)** | | **46.9%** | **72.9%** | **+26.0pp** | **4.6** | | |

---

## Run 3 vs Run 4 Comparison

Rubrics are regenerated from scratch each run, so baselines differ. The improvement in mean delta from Run 3 to Run 4 reflects better rubric quality and the new learning features introduced in Run 4.

| Run | Mean Baseline | Mean Harness | Mean Delta |
|---|---|---|---|
| Run 3 | 54.7% | 73.3% | +18.5pp |
| Run 4 | 46.9% | 72.9% | +26.0pp |

Run 4 baselines are lower on average (harder rubrics), yet harness scores remain comparable — meaning the harness recovered more ground. Mean delta improved by +7.5pp run-over-run.

---

## Key Observations

- **bash_backup harness failure** — The harness run failed to complete for `bash_backup`. Only the baseline output (73.0%) is available. This was the highest baseline score of any task, suggesting the rubric may have been too strict for the regeneration loop to handle, or a runtime error interrupted the harness.

- **sql_ltv_query regression gap** — The best iteration during the harness run reached 79.2%, but the final reported score is 67.2%. This is the largest regression gap of any task and indicates a within-run regression: the model overfit to feedback signals and degraded previously working criteria. The `correctness` criterion plateaued at 50% despite earlier gains.

- **agi_counterargument biggest improvement (+46.9pp)** — The steelman criterion, which scored 0% at baseline, reached 70%+ after harness iteration. This task had the most room for improvement and the harness effectively directed the model toward the intellectual honesty requirements that baseline generation missed.

- **New features in Run 4** — This run introduced four learning capabilities:
  - **Regression recovery learning** — the harness detects when a new iteration scores lower than the previous best and applies targeted recovery prompts rather than continuing blind iteration
  - **Preserve-what-works constraint** — improvement prompts explicitly lock in criteria already scoring above threshold so regeneration doesn't regress them
  - **Feedback persistence** — criterion-level feedback is carried across iterations rather than regenerated each time, enabling cumulative directed improvement
  - **Rubric negotiation** — the rubric generation step now incorporates signals from prior run data (via `.rubric_feedback/`) to avoid generating criteria that historically fail to discriminate
