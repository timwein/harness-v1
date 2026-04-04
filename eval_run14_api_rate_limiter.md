# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:15:08 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| api_rate_limiter | code_generation | 37.0% | 62.0% | +25.0% | 4 | 217s | 2430s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+25.0%** |
| Median lift | +25.0% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| circuit_breaker_implementation | Graceful Degradation | +91.2% | 1 |
| prometheus_monitoring | Production Reliability | +53.8% | 1 |
| degradation_coordination_coherence | Cross-cutting Integration | +42.5% | 1 |
| performance_reliability_alignment | Cross-cutting Integration | +40.0% | 1 |
| multi_dimensional_rate_limiting | Algorithmic Design | +40.0% | 1 |
| token_refill_atomicity | Algorithm Correctness | +37.5% | 1 |
| partition_tolerance_strategy | Distributed Coordination | +33.8% | 1 |
| performance_optimization | Performance & Scalability | +17.5% | 1 |
| redis_hot_key_prevention | Distributed Systems | +15.0% | 1 |
| redis_cluster_operations | Redis Atomicity & Concurrency | +10.0% | 1 |
| fallback_strategies | Graceful Degradation | +2.5% | 1 |
| burst_overflow_mathematics | Algorithm Correctness | +0.0% | 1 |
| toctou_race_prevention | Redis Atomicity & Concurrency | +0.0% | 1 |
| sliding_window_precision | Sliding Window Implementation | +0.0% | 1 |
| redis_algorithm_consistency | Cross-cutting Integration | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 217s | 2430s |
| Avg time / task | 217s | 2430s |
| Input tokens (total) | 39 | ~32,000 (est.) |
| Output tokens (total) | 4,096 | ~6,000 (est.) |
| Est. cost (USD) | $0.0616 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.