# Rubric Harness Eval Results

The rubric harness is a generation-verification loop that generates task-specific scoring rubrics grounded in web research, then iterates generation and verification until a quality threshold is met. For each task it runs a baseline (single-shot generation) and a harness run (iterative regeneration guided by the rubric), then reports the score delta.

---

## Methodology Note: Rubric Generation Upgrade (Run 5+)

> **Starting from Run 5, the rubric generation pipeline was upgraded.** Rubrics are now generated using multi-pass hierarchical generation with adversarial coverage audits and expert panel simulation. This produces more comprehensive rubrics that are significantly harder to score against — criteria are broader in scope, more discriminating, and less forgiving of partial compliance.
>
> **Scores and deltas from Run 5 onward are not directly comparable to Run 4 and earlier.** Lower baselines and smaller deltas in later runs may reflect harder rubrics rather than a regression in harness performance. Treat each run's scores as internally consistent but cross-run comparisons as approximate.

---

## Run 12 Results

Run 12 is the first eval where every task generates a fresh rubric via the full pipeline (research, multi-pass generation, negotiation, tradeoff detection, quality gate). No sample rubrics used. All 10 scoring fixes from the Run 10 debug analysis are active. 22 of 25 tasks scored (2 had 0% harness output from generation failures, 1 rate-limit error retried successfully but cold_outreach_email and investment_memo failed to produce harness output).

| Task | Description | Baseline | Harness | Delta | Iters |
|---|---|---|---|---|---|
| api_rate_limiter | Implement a distributed rate limiter with sliding window | 59.8% | 86.5% | +26.7pp | 2 |
| rust_concurrent_cache | Implement a thread-safe LRU cache in Rust with TTL expiration | 55.7% | 78.8% | +23.1pp | 6 |
| debugging_walkthrough | Write a debugging walkthrough for a memory leak in a Node.js service | 75.6% | 95.6% | +20.0pp | 1 |
| data_pipeline_dag | Design an Airflow DAG for an ETL pipeline with SLA monitoring | 50.8% | 68.7% | +17.9pp | 7 |
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 59.3% | 76.9% | +17.5pp | 6 |
| board_deck_narrative | Write the narrative section of a Series B board deck | 69.6% | 86.0% | +16.4pp | 2 |
| negotiation_playbook | Create a negotiation playbook for an enterprise SaaS deal | 65.1% | 77.9% | +12.8pp | 4 |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value | 79.4% | 92.1% | +12.7pp | 1 |
| comp_analysis_memo | Write a competitive analysis memo for a fintech startup | 67.8% | 80.0% | +12.2pp | 4 |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review | 50.0% | 62.0% | +12.0pp | 4 |
| csv_parser | Generate a Python function that parses messy CSV data | 62.5% | 68.7% | +6.2pp | 4 |
| system_design_doc | Write a system design doc for a real-time notifications service | 70.5% | 75.5% | +5.0pp | 4 |
| bash_backup | Write a bash script that backs up a PostgreSQL database to S3 | 84.0% | 86.8% | +2.8pp | 3 |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 77.6% | 79.3% | +1.7pp | 4 |
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 53.6% | 54.0% | +0.4pp | 4 |
| terraform_multi_env | Write Terraform modules for a multi-environment AWS deployment | 79.5% | 74.8% | -4.6pp | 7 |
| legal_contract_redline | Redline a vendor SaaS agreement from the buyer's perspective | 74.8% | 69.7% | -5.1pp | 2 |
| ml_experiment_report | Write an ML experiment report comparing fine-tuning approaches | 46.6% | 40.9% | -5.7pp | 5 |
| graphql_schema_federation | Design a federated GraphQL schema for a multi-service e-commerce platform | 58.1% | 52.0% | -6.1pp | 3 |
| incident_postmortem | Write a blameless postmortem for a 4-hour payment processing outage | 90.7% | 82.8% | -7.9pp | 2 |
| regulatory_gap_analysis | Perform a GDPR gap analysis for a US SaaS company expanding to the EU | 73.3% | 64.6% | -8.7pp | 4 |
| security_threat_model | Create a STRIDE threat model for a healthcare API handling PHI | 90.9% | 74.8% | -16.1pp | 3 |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 63.5% | — | — | — |
| investment_memo | Draft a 1-page investment memo on a Series A defense drone startup | 70.4% | — | — | — |
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system | — | — | ERROR | — |
| **MEAN (22 scored)** | | **68.0%** | **74.0%** | **+6.1pp** | **3.6** |

### Run 12 Observations

- **First fresh-rubric-generation eval** — Every task generated its own rubric via research, multi-pass generation, negotiation, quality gate, and tradeoff detection. No sample rubrics used.
- **Higher baselines (68.0% vs 64.7% in Run 11)** — Generated rubrics produced higher baseline scores, suggesting they may be better calibrated for the task but also leaving less room for improvement.
- **More regressions (7/22 vs 3/25)** — Fresh rubrics introduced criteria conflicts the harness couldn't resolve. security_threat_model (-16.1pp) and regulatory_gap_analysis (-8.7pp) both regressed, likely due to rubric criteria that conflicted or were too strict.
- **sql_ltv_query recovered (+12.7pp)** — The perennial regression task finally showed strong improvement with a fresh rubric, confirming the old sample rubric was the bottleneck.
- **2 harness failures** — cold_outreach_email and investment_memo generated rubrics but the harness produced 0% output, indicating a generation pipeline issue with certain rubric structures.
- **Fresh rubrics need tuning** — The +6.1pp delta vs +19.7pp in Run 11 (same fixes, sample rubrics) shows the generation pipeline produces rubrics that are harder to improve against. The quality gate and tradeoff detection need further calibration for generated rubrics.

---

## Run 11 Results

Run 11 applied 10 scoring/rubric fixes from the Run 10 debug analysis. Used sample rubrics (not generated). All 25 tasks completed with 0 errors after retrying 4 rate-limited tasks.

**Fixes applied:** (1) Removed 1.0 prohibition — full 0-1.0 scale, (2) Fixed violation filtering bug in _flatten_scores, (3) Penalty sum capping at 1.3x, (4) --generate-rubrics flag, (5) Preserve threshold 75%→90%, (6) Re-scoring with shared scorer, (7) Deterministic bash/SQL verifiers, (8) Learning persistence, (9) Quality gate warnings, (10) Postamble stripping.

| Task | Description | Baseline | Harness | Delta | Iters |
|---|---|---|---|---|---|
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system | 21.1% | 100.0% | +78.9pp | 1 |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 31.8% | 94.1% | +62.2pp | 1 |
| rust_concurrent_cache | Implement a thread-safe LRU cache in Rust with TTL expiration | 56.7% | 99.3% | +42.6pp | 3 |
| ml_experiment_report | Write an ML experiment report comparing fine-tuning approaches | 57.7% | 96.5% | +38.8pp | 1 |
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 46.3% | 78.3% | +32.0pp | 3 |
| negotiation_playbook | Create a negotiation playbook for an enterprise SaaS deal | 67.4% | 98.3% | +30.9pp | 1 |
| csv_parser | Generate a Python function that parses messy CSV data | 62.9% | 90.9% | +28.0pp | 1 |
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 58.9% | 85.8% | +26.9pp | 3 |
| security_threat_model | Create a STRIDE threat model for a healthcare API handling PHI | 75.4% | 100.0% | +24.6pp | 1 |
| regulatory_gap_analysis | Perform a GDPR gap analysis for a US SaaS company expanding to the EU | 72.1% | 96.8% | +24.7pp | 1 |
| debugging_walkthrough | Write a debugging walkthrough for a memory leak in a Node.js service | 75.2% | 99.2% | +23.9pp | 1 |
| graphql_schema_federation | Design a federated GraphQL schema for a multi-service e-commerce platform | 64.3% | 84.1% | +19.8pp | 2 |
| system_design_doc | Write a system design doc for a real-time notifications service | 58.2% | 77.8% | +19.6pp | 3 |
| investment_memo | Draft a 1-page investment memo on a Series A defense drone startup | 73.1% | 92.0% | +19.0pp | 2 |
| legal_contract_redline | Redline a vendor SaaS agreement from the buyer's perspective | 73.5% | 90.4% | +16.9pp | 1 |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review | 50.0% | 64.6% | +14.6pp | 4 |
| bash_backup | Write a bash script that backs up a PostgreSQL database to S3 | 82.6% | 94.5% | +11.9pp | 1 |
| incident_postmortem | Write a blameless postmortem for a 4-hour payment processing outage | 86.8% | 97.1% | +10.3pp | 1 |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value | 79.4% | 88.8% | +9.4pp | 1 |
| comp_analysis_memo | Write a competitive analysis memo for a fintech startup | 65.5% | 74.5% | +9.0pp | 4 |
| api_rate_limiter | Implement a distributed rate limiter with sliding window | 60.5% | 69.5% | +9.0pp | 3 |
| terraform_multi_env | Write Terraform modules for a multi-environment AWS deployment | 86.2% | 87.5% | +1.3pp | 1 |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 77.6% | 76.9% | -0.7pp | 5 |
| data_pipeline_dag | Design an Airflow DAG for an ETL pipeline with SLA monitoring | 56.7% | 55.9% | -0.8pp | 3 |
| board_deck_narrative | Write the narrative section of a Series B board deck | 76.6% | 15.4% | -61.2pp | 3 |
| **MEAN (25 tasks)** | | **64.7%** | **84.3%** | **+19.7pp** | **2.0** |

### Run 11 Observations

- **Massive improvement from scoring fixes** — Mean harness score jumped from 68.2% (Run 10) to 84.3%, and mean delta from +14.7pp to +19.7pp. The 10 fixes had dramatic impact.
- **billing_schema: +78.9pp** — The violation filtering fix (Fix 2) completely resolved the perma-zero penalty bug. Score went from 21.1% to 100.0% in a single iteration.
- **cold_outreach_email: +62.2pp** — Previously stuck at +6.0pp (Run 10). The penalty filtering fix and raised preserve threshold unlocked this task.
- **Three 100% scores** — billing_schema, security_threat_model scored perfect 100%. This likely reflects the 1.0 scale unlock (Fix 1) allowing sub-attributes to reach full marks.
- **Fast convergence (avg 2.0 iters)** — 13 tasks converged in a single iteration, suggesting the fixes made first-attempt scoring much more accurate.
- **board_deck_narrative: -61.2pp** — Severe regression where the harness output scored 15.4%. The re-scoring step (Fix 6) may have produced a very different score than the in-loop scorer, or the output genuinely degraded. Needs investigation.
- **22/25 improved, 3 regressed** — attention_explanation (-0.7pp) and data_pipeline_dag (-0.8pp) are near-neutral. Only board_deck_narrative is a true regression.

---

## Run 10 Results

Run 10 is the first eval on the expanded 25-task suite (up from 10). All 25 tasks completed with 0 errors. Tasks were run in parallel (25 concurrent processes); 7 initially hit 429 rate limits and were retried successfully.

| Task | Description | Baseline | Harness | Delta | Iters | Rubric | Output |
|---|---|---|---|---|---|---|---|
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system | 21.1% | 57.6% | +36.6pp | 3 | [rubric](eval_run10_artifacts/rubric_billing_schema.md) | [output](eval_run10_artifacts/output_billing_schema.md) |
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 36.8% | 70.5% | +33.7pp | 4 | [rubric](eval_run10_artifacts/rubric_exec_summary.md) | [output](eval_run10_artifacts/output_exec_summary.md) |
| graphql_schema_federation | Design a federated GraphQL schema for a multi-service e-commerce platform | 40.4% | 71.5% | +31.1pp | 5 | [rubric](eval_run10_artifacts/rubric_graphql_schema_federation.md) | [output](eval_run10_artifacts/output_graphql_schema_federation.md) |
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 35.0% | 61.9% | +26.9pp | 3 | [rubric](eval_run10_artifacts/rubric_agi_counterargument.md) | [output](eval_run10_artifacts/output_agi_counterargument.md) |
| rust_concurrent_cache | Implement a thread-safe LRU cache in Rust with TTL expiration | 45.5% | 69.9% | +24.4pp | 6 | [rubric](eval_run10_artifacts/rubric_rust_concurrent_cache.md) | [output](eval_run10_artifacts/output_rust_concurrent_cache.md) |
| legal_contract_redline | Redline a vendor SaaS agreement from the buyer's perspective | 54.3% | 75.0% | +20.7pp | 5 | [rubric](eval_run10_artifacts/rubric_legal_contract_redline.md) | [output](eval_run10_artifacts/output_legal_contract_redline.md) |
| security_threat_model | Create a STRIDE threat model for a healthcare API handling PHI | 56.2% | 75.0% | +18.8pp | 3 | [rubric](eval_run10_artifacts/rubric_security_threat_model.md) | [output](eval_run10_artifacts/output_security_threat_model.md) |
| terraform_multi_env | Write Terraform modules for a multi-environment AWS deployment | 50.0% | 67.0% | +17.0pp | 4 | [rubric](eval_run10_artifacts/rubric_terraform_multi_env.md) | [output](eval_run10_artifacts/output_terraform_multi_env.md) |
| csv_parser | Generate a Python function that parses messy CSV data | 63.5% | 79.5% | +16.0pp | 5 | [rubric](eval_run10_artifacts/rubric_csv_parser.md) | [output](eval_run10_artifacts/output_csv_parser.md) |
| regulatory_gap_analysis | Perform a GDPR gap analysis for a US SaaS company expanding to the EU | 58.1% | 74.1% | +16.0pp | 5 | [rubric](eval_run10_artifacts/rubric_regulatory_gap_analysis.md) | [output](eval_run10_artifacts/output_regulatory_gap_analysis.md) |
| investment_memo | Draft a 1-page investment memo on a Series A defense drone startup | 62.7% | 78.0% | +15.2pp | 5 | [rubric](eval_run10_artifacts/rubric_investment_memo.md) | [output](eval_run10_artifacts/output_investment_memo.md) |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review | 45.8% | 60.4% | +14.6pp | 4 | [rubric](eval_run10_artifacts/rubric_startup_naming.md) | [output](eval_run10_artifacts/output_startup_naming.md) |
| board_deck_narrative | Write the narrative section of a Series B board deck | 61.2% | 74.8% | +13.7pp | 4 | [rubric](eval_run10_artifacts/rubric_board_deck_narrative.md) | [output](eval_run10_artifacts/output_board_deck_narrative.md) |
| negotiation_playbook | Create a negotiation playbook for an enterprise SaaS deal | 62.2% | 75.0% | +12.8pp | 4 | [rubric](eval_run10_artifacts/rubric_negotiation_playbook.md) | [output](eval_run10_artifacts/output_negotiation_playbook.md) |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 62.7% | 74.7% | +12.0pp | 3 | [rubric](eval_run10_artifacts/rubric_attention_explanation.md) | [output](eval_run10_artifacts/output_attention_explanation.md) |
| data_pipeline_dag | Design an Airflow DAG for an ETL pipeline with SLA monitoring | 50.2% | 62.1% | +11.9pp | 3 | [rubric](eval_run10_artifacts/rubric_data_pipeline_dag.md) | [output](eval_run10_artifacts/output_data_pipeline_dag.md) |
| comp_analysis_memo | Write a competitive analysis memo for a fintech startup | 54.7% | 64.9% | +10.2pp | 4 | [rubric](eval_run10_artifacts/rubric_comp_analysis_memo.md) | [output](eval_run10_artifacts/output_comp_analysis_memo.md) |
| api_rate_limiter | Implement a distributed rate limiter with sliding window | 54.9% | 62.4% | +7.5pp | 5 | [rubric](eval_run10_artifacts/rubric_api_rate_limiter.md) | [output](eval_run10_artifacts/output_api_rate_limiter.md) |
| ml_experiment_report | Write an ML experiment report comparing fine-tuning approaches | 73.3% | 80.4% | +7.1pp | 3 | [rubric](eval_run10_artifacts/rubric_ml_experiment_report.md) | [output](eval_run10_artifacts/output_ml_experiment_report.md) |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 48.0% | 53.9% | +6.0pp | 3 | [rubric](eval_run10_artifacts/rubric_cold_outreach_email.md) | [output](eval_run10_artifacts/output_cold_outreach_email.md) |
| system_design_doc | Write a system design doc for a real-time notifications service | 60.2% | 66.0% | +5.9pp | 3 | [rubric](eval_run10_artifacts/rubric_system_design_doc.md) | [output](eval_run10_artifacts/output_system_design_doc.md) |
| debugging_walkthrough | Write a debugging walkthrough for a memory leak in a Node.js service | 69.7% | 75.0% | +5.3pp | 4 | [rubric](eval_run10_artifacts/rubric_debugging_walkthrough.md) | [output](eval_run10_artifacts/output_debugging_walkthrough.md) |
| bash_backup | Write a bash script that backs up a PostgreSQL database to S3 | 49.8% | 52.8% | +3.1pp | 3 | [rubric](eval_run10_artifacts/rubric_bash_backup.md) | [output](eval_run10_artifacts/output_bash_backup.md) |
| incident_postmortem | Write a blameless postmortem for a 4-hour payment processing outage | 57.6% | 60.6% | +3.0pp | 4 | [rubric](eval_run10_artifacts/rubric_incident_postmortem.md) | [output](eval_run10_artifacts/output_incident_postmortem.md) |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value | 63.9% | 62.5% | -1.4pp | 4 | [rubric](eval_run10_artifacts/rubric_sql_ltv_query.md) | [output](eval_run10_artifacts/output_sql_ltv_query.md) |
| **MEAN (25 tasks)** | | **53.5%** | **68.2%** | **+14.7pp** | **3.9** | | |

### Run 10 Observations

- **First 25-task eval** — Expanded from 10 to 25 tasks covering code (Rust, Python, Terraform, GraphQL), business writing (board deck, comp analysis, negotiation, legal), technical docs (system design, postmortem, debugging, ML report), and domain analysis (security, regulatory, threat model).
- **24/25 improved, 1 regression** — sql_ltv_query was the sole regression (-1.4pp), consistent with its near-ceiling behavior in prior runs. Every other task showed positive lift.
- **billing_schema recovered (+36.6pp)** — After a catastrophic -26.7pp regression in Run 7, billing_schema was the biggest winner this run, jumping from 21.1% to 57.6%.
- **New tasks performed well** — The 15 new tasks averaged +13.5pp delta, comparable to the original 10 tasks (+16.2pp), suggesting the harness generalizes across domains.
- **Highest-scoring tasks** — ml_experiment_report (80.4%), csv_parser (79.5%), and investment_memo (78.0%) led in absolute harness scores. Tasks with high baselines (>60%) tended to show smaller deltas, consistent with a ceiling effect.
- **Code tasks show strong gains** — graphql_schema_federation (+31.1pp), rust_concurrent_cache (+24.4pp), and csv_parser (+16.0pp) all benefited from iterative refinement, suggesting the harness works well for structured code generation.
- **Parallel execution** — Running 25 tasks concurrently cut wall-clock time significantly vs sequential, though 7 tasks hit API rate limits and required retry.

---

## Run 8 Results

Run 8 re-ran all 10 tasks after the preamble-stripping fix (`d7c7235`) that prevents LLM meta-commentary from leaking into generated output. This was the biggest single-commit improvement — cold_outreach_email jumped from +0pp to +32.6pp now that preamble text no longer pollutes re-scoring. All 10 tasks improved; 0 regressions.

| Task | Description | Baseline | Harness | Delta | Iters | Rubric | Output |
|---|---|---|---|---|---|---|---|
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing | 21.1% | 56.1% | +35.0pp | 4 | [rubric](eval_run8_artifacts/rubric_billing_schema.md) | [output](eval_run8_artifacts/output_billing_schema.md) |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 46.9% | 79.5% | +32.6pp | 4 | [rubric](eval_run8_artifacts/rubric_cold_outreach_email.md) | [output](eval_run8_artifacts/output_cold_outreach_email.md) |
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 26.3% | 58.0% | +31.7pp | 4 | [rubric](eval_run8_artifacts/rubric_exec_summary.md) | [output](eval_run8_artifacts/output_exec_summary.md) |
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 35.0% | 61.1% | +26.1pp | 3 | [rubric](eval_run8_artifacts/rubric_agi_counterargument.md) | [output](eval_run8_artifacts/output_agi_counterargument.md) |
| csv_parser | Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers | 38.0% | 61.4% | +23.3pp | 3 | [rubric](eval_run8_artifacts/rubric_csv_parser.md) | [output](eval_run8_artifacts/output_csv_parser.md) |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review for mid-market law firms | 43.8% | 64.6% | +20.8pp | 6 | [rubric](eval_run8_artifacts/rubric_startup_naming.md) | [output](eval_run8_artifacts/output_startup_naming.md) |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define | 50.1% | 62.5% | +12.4pp | 4 | [rubric](eval_run8_artifacts/rubric_sql_ltv_query.md) | [output](eval_run8_artifacts/output_sql_ltv_query.md) |
| investment_memo | Draft a 1-page investment memo on a hypothetical Series A company in the defense drone space | 66.5% | 78.0% | +11.5pp | 3 | [rubric](eval_run8_artifacts/rubric_investment_memo.md) | [output](eval_run8_artifacts/output_investment_memo.md) |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 64.1% | 73.6% | +9.4pp | 7 | [rubric](eval_run8_artifacts/rubric_attention_explanation.md) | [output](eval_run8_artifacts/output_attention_explanation.md) |
| bash_backup | Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications | 52.0% | 55.2% | +3.2pp | 3 | [rubric](eval_run8_artifacts/rubric_bash_backup.md) | [output](eval_run8_artifacts/output_bash_backup.md) |
| **MEAN (10 tasks)** | | **44.4%** | **65.0%** | **+20.6pp** | **4.1** | | |

### Run 8 Observations

- **First run with 10/10 positive deltas** — Every task improved. No regressions or neutral results. The preamble-stripping fix (`d7c7235`) was the key enabler, preventing LLM meta-commentary from polluting output and causing re-scoring failures.
- **cold_outreach_email biggest recovery (+32.6pp)** — In the pre-fix run, preamble text caused this task to score 50.7% (effectively 0pp delta). With the fix, it now scores 79.5% — the highest absolute harness score in this run.
- **billing_schema strongest delta (+35.0pp)** — Jumped from 21.1% baseline to 56.1%. The `schema_completeness` and `schema_correctness` criteria drove most of the gain (+75pp each).
- **Mean lift +20.6pp** — A significant improvement over the pre-fix Run 8 (+12.8pp) and the best mean delta since Run 5+ methodology was adopted.
- **bash_backup weakest delta (+3.2pp)** — Consistent with prior runs. The `bash_safety` criterion (set -euo pipefail detection) scored 0% across all iterations, suggesting the generation agent struggles with this specific requirement.
- **attention_explanation required most iterations (7)** — The harness cycled through multiple attempts to satisfy competing `expl_accuracy` and `expl_engagement` constraints before converging at 73.6%.

---

## Run 7 Results

Run 7 completed all 10 tasks with 0 errors — the first fully clean run since Run 3. Used the same resilient eval wrapper as Run 6.

| Task | Description | Baseline | Harness | Delta | Iters |
|---|---|---|---|---|---|
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 36.8% | 65.4% | +28.6pp | 4 |
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 32.9% | 61.4% | +28.5pp | 3 |
| investment_memo | Draft a 1-page investment memo on a hypothetical Series A company in the defense drone space | 60.9% | 80.7% | +19.8pp | 3 |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 30.3% | 47.0% | +16.7pp | 4 |
| csv_parser | Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers | 45.0% | 61.4% | +16.4pp | 4 |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review for mid-market law firms | 45.8% | 60.4% | +14.6pp | 3 |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 61.2% | 71.0% | +9.8pp | 4 |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define | 52.5% | 60.0% | +7.5pp | 4 |
| bash_backup | Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications | 50.8% | 55.2% | +4.4pp | 4 |
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing | 47.8% | 78.3% | +30.5pp | 5 |
| **MEAN (10 tasks)** | | **46.4%** | **64.1%** | **+17.7pp** | **3.8** |

### Run 7 Observations

- **First error-free run since Run 3** — All 10 tasks completed successfully. csv_parser and startup_naming (which errored in Run 6) both finished cleanly.
- **billing_schema corrected (+30.5pp)** — Originally reported as -26.7pp due to a bug where the eval harness redundantly re-scored the loop output with a fresh LLM call whose JSON response failed to parse, producing 21.1%. The loop's actual best iteration (iter 3 of 5) scored 78.3%. Fix: [#8](https://github.com/timwein/auto-verifier/pull/8).
- **exec_summary and agi_counterargument strongest gains (+28.6pp, +28.5pp)** — Both had low baselines and benefited from iterative refinement. agi_counterargument continues to be one of the harness's best tasks across all runs.
- **investment_memo highest absolute score (80.7%)** — The best harness score in this run, converging in just 3 iterations.
- **attention_explanation recovered (+9.8pp)** — After regressing in Run 6 (-2.7pp), this task now shows a positive delta, suggesting the new rubric was better constructed.
- **Harness average 64.1%** — Below the 72-73% range seen in Runs 3-6, but consistent with harder rubrics from the Run 5+ methodology upgrade.
- **Lower iteration counts (avg 3.6)** — Convergence/plateau detection kicked in earlier this run compared to prior runs (avg 4.5-4.6), suggesting the harness is stopping sooner when it detects diminishing returns.

---

## Run 6 Results

Run 6 used the resilient eval wrapper (`run_eval_resilient.sh`) which auto-restarts stalled tasks after 8 minutes. 6 of 8 tasks completed successfully; 2 tasks errored out.

| Task | Description | Baseline | Harness | Delta | Iters |
|---|---|---|---|---|---|
| agi_counterargument | Write a counterargument to the claim 'AGI will arrive before 2030' | 39.6% | 83.1% | +43.6pp | 4 |
| billing_schema | Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing | 53.2% | 77.9% | +24.7pp | 5 |
| exec_summary | Summarize a 2,000-word technical blog post into a 3-bullet executive summary | 51.2% | 69.1% | +17.9pp | 5 |
| sql_ltv_query | Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define | 59.9% | 77.5% | +17.6pp | 4 |
| cold_outreach_email | Write a cold outreach email to a Series A founder pitching angel investment | 51.6% | 68.8% | +17.2pp | 5 |
| attention_explanation | Explain transformer attention mechanisms to a smart 16-year-old | 61.1% | 58.4% | -2.7pp | 4 |
| csv_parser | Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers | 53.8% | ERROR | — | — |
| startup_naming | Generate 5 names for a startup that does AI-powered contract review for mid-market law firms | 44.4% | ERROR | — | — |
| **MEAN (6 valid)** | | **52.8%** | **72.5%** | **+19.7pp** | **4.5** |

### Run 6 Observations

- **agi_counterargument biggest win (+43.6pp)** — Consistent with prior runs; the harness excels at driving intellectual honesty and steelman criteria that baseline generation misses entirely.
- **attention_explanation regression (-2.7pp)** — The only negative delta. The harness iterations degraded quality rather than improving it, suggesting the rubric may have introduced conflicting criteria for this explanatory task.
- **csv_parser timeout** — Failed with an Anthropic API timeout during the harness phase. Code generation tasks with large outputs remain vulnerable to the 300-second timeout ceiling.
- **startup_naming error** — Harness phase failed to complete. No error details captured.

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

### Run 5 Observations

**Why the delta shrank vs Run 4:** Run 5 baselines are meaningfully higher (53.1% vs 46.9%) because the new multi-pass rubric pipeline generates harder, more comprehensive rubrics that are more demanding of the baseline. The harness recovered well on most tasks, but the higher floor leaves less room for gain.

**attention_explanation regression (−20.3pp):** This is the first outright regression across all runs. The harness overfit to rubric feedback and produced output that scored worse on `expl_accuracy` (correctness) and `expl_accessibility` (audience fit) than the baseline. The rubric may have over-constrained the rewrite toward technical depth at the expense of the 16-year-old framing. Needs investigation.

**agi_counterargument remains the strongest task (+37.5pp):** The steelman criterion, which scored 0% at baseline, drove most of the lift. Consistent across runs.

**sql_ltv_query near-neutral (+2.0pp):** The harness barely moved the needle, similar to Run 4 (where it also stalled at 67.2% final). This task may be near a ceiling for the current rubric design.

---

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

## Cross-Run Comparison

Rubrics are regenerated from scratch each run, so baselines differ across runs.

| Run | Tasks (valid) | Mean Baseline | Mean Harness | Mean Delta | Notes |
|---|---|---|---|---|---|
| Run 3 | 10 | 54.7% | 73.3% | +18.5pp | Initial eval |
| Run 4 | 9 | 46.9% | 72.9% | +26.0pp | Added learning features |
| Run 5 | 9 | 53.1% | 68.8% | +15.7pp | Multi-pass rubric pipeline, 1 regression; **harder rubrics (Run 5+ methodology)** |
| Run 6 | 6 | 52.8% | 72.5% | +19.7pp | Resilient wrapper, 2 errors; **harder rubrics (Run 5+ methodology)** |
| Run 7 | 10 | 46.4% | 64.1% | +17.7pp | First clean 10/10 run since Run 3 |
| Run 8 | 10 | 44.4% | 65.0% | +20.6pp | Preamble-stripping fix; **10/10 positive deltas, best post-Run 5 mean delta** |
| Run 10 | 25 | 53.5% | 68.2% | +14.7pp | First 25-task eval; 24/25 improved; parallel execution |
| Run 11 | 25 | 64.7% | 84.3% | +19.7pp | **10 scoring fixes; sample rubrics; 22/25 improved; best harness avg** |
| Run 12 | 22 | 68.0% | 74.0% | +6.1pp | First fresh-rubric-gen eval; 15/22 improved; harder generated rubrics |

> **Cross-run scores are not directly comparable after Run 4.** The rubric generation upgrade introduced in Run 5 (multi-pass hierarchical generation, adversarial coverage audits, expert panel simulation) produces harder rubrics that compress scores and deltas. See the [Methodology Note](#methodology-note-rubric-generation-upgrade-run-5) above.

**Run 11** is the best-performing run to date, with 84.3% mean harness score and +19.7pp delta across all 25 tasks. The 10 scoring fixes (1.0 scale, violation filtering, penalty capping, preserve threshold, deterministic verifiers, etc.) dramatically improved both scoring accuracy and the harness's ability to iterate. **Run 12** introduced fresh rubric generation for every task, which produced harder, more comprehensive rubrics (higher baselines at 68.0%) but the harness struggled more (+6.1pp delta, 7 regressions). The rubric generation pipeline needs further calibration to produce rubrics the harness can effectively improve against.

---

## Key Observations

- **bash_backup harness failure (Run 4)** — The harness run failed to complete for `bash_backup`. Only the baseline output (73.0%) is available. This was the highest baseline score of any task, suggesting the rubric may have been too strict for the regeneration loop to handle, or a runtime error interrupted the harness.

- **sql_ltv_query regression gap** — The best iteration during the harness run reached 79.2%, but the final reported score is 67.2%. This is the largest regression gap of any task and indicates a within-run regression: the model overfit to feedback signals and degraded previously working criteria. The `correctness` criterion plateaued at 50% despite earlier gains.

- **agi_counterargument biggest improvement (+46.9pp in Run 4)** — The steelman criterion, which scored 0% at baseline, reached 70%+ after harness iteration. This task had the most room for improvement and the harness effectively directed the model toward the intellectual honesty requirements that baseline generation missed.

- **New features in Run 4** — This run introduced four learning capabilities:
  - **Regression recovery learning** — the harness detects when a new iteration scores lower than the previous best and applies targeted recovery prompts rather than continuing blind iteration
  - **Preserve-what-works constraint** — improvement prompts explicitly lock in criteria already scoring above threshold so regeneration doesn't regress them
  - **Feedback persistence** — criterion-level feedback is carried across iterations rather than regenerated each time, enabling cumulative directed improvement
  - **Rubric negotiation** — the rubric generation step now incorporates signals from prior run data (via `.rubric_feedback/`) to avoid generating criteria that historically fail to discriminate
