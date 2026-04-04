# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:27:23 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| agi_counterargument | argumentation | 15.4% | 91.1% | +75.7% | 5 | 180s | 3175s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+75.7%** |
| Median lift | +75.7% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| intellectual_contribution_depth | Analytical Quality | +100.0% | 1 |
| argument_engagement_specificity | Argumentative Quality | +100.0% | 1 |
| probabilistic_reasoning_calibration | forecasting_methodology | +92.5% | 1 |
| epistemic_rigor_assessment | Reasoning Quality | +92.5% | 1 |
| computational_complexity_constraints | Computational Complexity Analysis | +91.2% | 1 |
| substantive_content_depth | Content Quality | +90.0% | 1 |
| counterargument_depth_analysis | Argumentative Rigor | +85.0% | 1 |
| agi_benchmark_methodology | Capabilities Evaluation Framework | +83.8% | 1 |
| empirical_forecasting_methodology | Empirical Evidence Quality | +81.2% | 1 |
| ood_generalization_failure_analysis | Technical Bottleneck Analysis | +75.0% | 1 |
| reasoning_transparency | Logical Structure | +75.0% | 1 |
| economic_deployment_feasibility | Economic and Deployment Constraints | +53.8% | 1 |
| capability_safety_integration | Cross-Cutting Analysis | +52.5% | 1 |
| alignment_safety_timeline_impact | Alignment and Safety Integration | +25.0% | 1 |
| stakeholder_incentive_analysis | sociotechnical_factors | +25.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 180s | 3175s |
| Avg time / task | 180s | 3175s |
| Input tokens (total) | 26 | ~40,000 (est.) |
| Output tokens (total) | 390 | ~7,500 (est.) |
| Est. cost (USD) | $0.0059 | ~$0.2325 (est.) |
| Avg iterations | 1 | 5.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.