# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:20:12 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| ml_experiment_report | technical_writing | 33.5% | 83.4% | +49.9% | 4 | 245s | 2666s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+49.9%** |
| Median lift | +49.9% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| statistical_significance_reporting | Statistical Analysis & Significance | +100.0% | 1 |
| data_leakage_prevention | Experimental Methodology | +93.8% | 1 |
| failure_analysis_mitigation_coherence | Cross-cutting Coherence | +93.8% | 1 |
| multidimensional_evaluation_framework | Evaluation Framework & Metrics | +80.0% | 1 |
| construct_validity_assessment | Evaluation Methodology | +75.0% | 1 |
| domain_specific_benchmark_validation | Evaluation Framework & Metrics | +71.2% | 1 |
| systematic_ablation_methodology | Ablation Studies & Component Analysis | +70.0% | 1 |
| domain_data_quality_assessment | Dataset Construction & Preprocessing | +61.3% | 1 |
| systematic_failure_characterization | Failure Analysis & Error Characterization | +46.2% | 1 |
| hyperparameter_sensitivity_analysis | Ablation Studies & Component Analysis | +42.5% | 1 |
| computational_efficiency_optimization | Training Implementation & Architecture | +41.2% | 1 |
| hyperparameter_optimization_rigor | Experimental Methodology | +36.0% | 1 |
| preprocessing_documentation_completeness | Dataset Construction & Preprocessing | +24.0% | 1 |
| bias_evaluation_framework | Responsible AI & Ethics Framework | +0.0% | 1 |
| reproducibility_implementation_completeness | Reproducibility & Documentation | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 245s | 2666s |
| Avg time / task | 245s | 2666s |
| Input tokens (total) | 45 | ~32,000 (est.) |
| Output tokens (total) | 4,096 | ~6,000 (est.) |
| Est. cost (USD) | $0.0616 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.