# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 18:57:59 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| incident_postmortem | incident_management | 65.5% | 99.3% | +33.8% | 2 | 178s | 1457s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+33.8%** |
| Median lift | +33.8% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| mttr_mtbf_metrics_integration | Performance Metrics | +100.0% | 1 |
| incident_impact_quantification | Incident Impact Quantification | +52.5% | 1 |
| observability_three_pillar_gaps | Observability and Monitoring Gaps | +47.5% | 1 |
| cascading_failure_propagation | Cascading Failure Analysis | +46.2% | 1 |
| timeline_precision_correlation | Timeline Precision and Data Correlation | +42.5% | 1 |
| resilience_patterns_application | Resilience Engineering | +41.3% | 1 |
| contributing_factors_depth | Root Cause Analysis Methodology | +25.0% | 1 |
| action_item_tracking_mechanisms | Follow-up Process | +22.5% | 1 |
| blameless_language_systems_focus | Blameless Culture Adherence | +0.0% | 1 |
| action_items_systemic_remediation | Action Item Quality and Ownership | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 178s | 1457s |
| Avg time / task | 178s | 1457s |
| Input tokens (total) | 51 | ~16,000 (est.) |
| Output tokens (total) | 1,657 | ~3,000 (est.) |
| Est. cost (USD) | $0.0250 | ~$0.0930 (est.) |
| Avg iterations | 1 | 2.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.