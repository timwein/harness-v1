# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:48:44 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| debugging_walkthrough | debugging | 27.3% | 76.4% | +49.1% | 8 | 208s | 4409s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+49.1%** |
| Median lift | +49.1% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| production_debugging_safety | Production Safety | +100.0% | 1 |
| postgresql_cancellation_handling | Database Safety | +100.0% | 1 |
| postgresql_connection_internals | PostgreSQL Internals & Performance | +93.8% | 1 |
| circuit_breaker_resilience | Error Handling & Resilience Patterns | +87.5% | 1 |
| memory_leak_profiling | Node.js Production Practices | +83.8% | 1 |
| sre_golden_signals_alignment | SRE Framework Compliance | +76.2% | 1 |
| metrics_monitoring_implementation | Observability & Monitoring | +66.2% | 1 |
| async_error_boundary_implementation | Error Handling & Resilience Patterns | +65.0% | 1 |
| systematic_debugging_approach | Debugging Methodology | +52.5% | 1 |
| load_testing_reproduction | Debugging Methodology | +48.7% | 1 |
| pool_config_depth | Connection Pool Engineering | +45.0% | 1 |
| structured_logging_correlation | Observability & Monitoring | +42.5% | 1 |
| nodejs_event_loop_optimization | Node.js Production Practices | +16.3% | 1 |
| connection_antipattern_detection | Connection Pool Engineering | +0.0% | 1 |
| transaction_isolation_analysis | Race Condition Analysis | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 208s | 4409s |
| Avg time / task | 208s | 4409s |
| Input tokens (total) | 48 | ~64,000 (est.) |
| Output tokens (total) | 3,795 | ~12,000 (est.) |
| Est. cost (USD) | $0.0571 | ~$0.3720 (est.) |
| Avg iterations | 1 | 8.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.