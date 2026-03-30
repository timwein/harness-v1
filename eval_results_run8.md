# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-03-30 23:40:26 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| cold_outreach_email | cold_outreach_email | 50.7% | 50.7% | -0.1% | 4 | 72s | 318s |
| csv_parser | code_generation | 47.2% | 61.4% | +14.1% | 4 | 89s | 594s |
| exec_summary | summarization | 42.4% | 57.5% | +15.2% | 4 | 36s | 276s |
| sql_ltv_query | sql_query | 50.1% | 60.0% | +9.9% | 4 | 56s | 443s |
| agi_counterargument | argumentation | 34.3% | 62.5% | +28.2% | 4 | 52s | 436s |
| billing_schema | schema_design | 50.1% | 59.2% | +9.1% | 4 | 84s | 610s |
| attention_explanation | explanation | 67.9% | 71.2% | +3.4% | 8 | 74s | 1140s |
| startup_naming | creative_naming | 47.9% | 60.4% | +12.5% | 3 | 55s | 511s |
| bash_backup | bash_scripting | 63.7% | 56.8% | -6.9% | 4 | 102s | 814s |
| investment_memo | investment_memo | 35.7% | 78.5% | +42.8% | 3 | 83s | 428s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 10 |
| Mean lift | **+12.8%** |
| Median lift | +11.2% |
| Std dev | 14.2% |
| Improved (>1%) | 8/10 |
| Neutral (±1%) | 1/10 |
| Regressed (<-1%) | 1/10 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| sum_exec_value | utility | +75.0% | 1 |
| arg_steelman | intellectual_honesty | +75.0% | 1 |
| memo_risks | diligence | +75.0% | 1 |
| email_subject | engagement | +53.8% | 1 |
| arg_counter_quality | argumentation | +51.2% | 1 |
| code_robustness | reliability | +46.2% | 1 |
| memo_thesis | conviction | +42.5% | 1 |
| memo_deal_terms | practicality | +42.5% | 1 |
| email_value_prop | persuasion | +38.7% | 1 |
| name_variety | range | +37.5% | 1 |
| memo_structure | format | +35.4% | 1 |
| email_social_proof | credibility | +35.0% | 1 |
| schema_extensibility | architecture | +30.0% | 1 |
| sum_fidelity | accuracy | +27.5% | 1 |
| memo_market | analysis | +25.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 10 | 10 |
| Total wall time | 702s | 5570s |
| Avg time / task | 70s | 557s |
| Input tokens (total) | 270 | ~336,000 (est.) |
| Output tokens (total) | 14,705 | ~63,000 (est.) |
| Est. cost (USD) | $0.2214 | ~$1.9530 (est.) |
| Avg iterations | 1 | 4.2 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.