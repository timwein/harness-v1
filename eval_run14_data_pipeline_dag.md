# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:21:28 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| data_pipeline_dag | data_engineering | 42.1% | 63.9% | +21.8% | 6 | 175s | 2880s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+21.8%** |
| Median lift | +21.8% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| multi_source_sensor_config | Multi-Source Integration Patterns | +66.2% | 1 |
| performance_monitoring_integration | Cross-Cutting Integration | +60.0% | 1 |
| connection_secret_management | Security and Configuration | +60.0% | 1 |
| comprehensive_retry_logic | Error Handling & Resilience | +48.7% | 1 |
| monitoring_alerting_framework | Monitoring & Alerting Framework | +46.2% | 1 |
| performance_anti_pattern_avoidance | Performance & Resource Optimization | +30.0% | 1 |
| task_granularity_atomicity | DAG Architecture & Design | +0.0% | 1 |
| schema_evolution_detection | Schema Evolution & Drift Handling | +0.0% | 1 |
| data_quality_enforcement | Data Quality & Validation | +0.0% | 1 |
| idempotency_quality_alignment | Cross-Cutting Integration | +0.0% | 1 |
| dependency_parallelization_design | DAG Architecture & Design | -8.7% | 1 |
| idempotent_upsert_implementation | Idempotency & Data Consistency | -10.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 175s | 2880s |
| Avg time / task | 175s | 2880s |
| Input tokens (total) | 63 | ~48,000 (est.) |
| Output tokens (total) | 4,096 | ~9,000 (est.) |
| Est. cost (USD) | $0.0616 | ~$0.2790 (est.) |
| Avg iterations | 1 | 6.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.