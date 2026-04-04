# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:06:13 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| billing_schema | schema_design | 38.3% | 77.3% | +38.9% | 4 | 127s | 2050s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+38.9%** |
| Median lift | +38.9% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| tenant_isolation_schema_architecture | Tenant Isolation & Data Segregation | +58.7% | 1 |
| compliance_security_standards | Compliance & Security Standards | +51.3% | 1 |
| scalability_performance_optimization | Scalability & Performance Optimization | +41.2% | 1 |
| billing_operations_integrity | Billing Operations & Data Integrity | +35.0% | 1 |
| tm_forum_sid_alignment | Standards Compliance | +32.5% | 1 |
| usage_metering_aggregation_design | Usage Metering & Event Handling | +25.0% | 1 |
| pricing_model_abstraction_flexibility | Pricing Model Abstraction | +11.3% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 127s | 2050s |
| Avg time / task | 127s | 2050s |
| Input tokens (total) | 30 | ~32,000 (est.) |
| Output tokens (total) | 4,096 | ~6,000 (est.) |
| Est. cost (USD) | $0.0615 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.