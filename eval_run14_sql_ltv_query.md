# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 18:59:05 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| sql_ltv_query | sql_query | 58.5% | 86.8% | +28.3% | 3 | 123s | 1591s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+28.3%** |
| Median lift | +28.3% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| index_strategy_optimization | Query Performance & Optimization | +93.8% | 1 |
| security_and_access_control | Security & Compliance Framework | +91.2% | 1 |
| scalability_architecture | Scalability & Enterprise Architecture | +82.5% | 1 |
| temporal_analysis_methodology | Analytical Methodology & Reporting Standards | +62.5% | 1 |
| data_integrity_and_null_handling | Data Integrity & Edge Case Handling | +40.0% | 1 |
| normalization_and_relationships | Schema Design & Data Modeling | +37.5% | 1 |
| query_execution_efficiency | Query Performance & Optimization | +21.2% | 1 |
| dimensional_modeling_architecture | Schema Design & Data Modeling | +0.0% | 1 |
| lifetime_value_calculation_accuracy | Business Logic & Calculation Accuracy | +0.0% | 1 |
| schema_query_coherence | Cross-Cutting Integration | +0.0% | 1 |
| sargable_predicate_usage | Performance Architecture | -10.0% | 1 |
| sql_standards_and_code_quality | SQL Standards & Code Quality | -25.0% | 1 |
| implicit_conversion_prevention | Performance Architecture | -50.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 123s | 1591s |
| Avg time / task | 123s | 1591s |
| Input tokens (total) | 31 | ~24,000 (est.) |
| Output tokens (total) | 1,502 | ~4,500 (est.) |
| Est. cost (USD) | $0.0226 | ~$0.1395 (est.) |
| Avg iterations | 1 | 3.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.