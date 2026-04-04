# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:30:30 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| rust_concurrent_cache | systems_programming | 41.8% | 70.9% | +29.1% | 9 | 149s | 3438s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+29.1%** |
| Median lift | +29.1% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| memory_ordering_correctness | Concurrency Correctness | +66.2% | 1 |
| lru_ordering_correctness | Cache Algorithms & Data Structures | +65.0% | 1 |
| performance_safety_tradeoff_analysis | Cross-Cutting Analysis | +38.8% | 1 |
| error_handling_system_coherence | Cross-Cutting Analysis | +27.5% | 1 |
| deadlock_prevention_design | Concurrency Correctness | +22.0% | 1 |
| rust_api_guidelines_compliance | Rust Language Idioms & Safety | +20.0% | 1 |
| ttl_expiry_system | TTL Expiry System | +16.3% | 1 |
| concurrency_correctness_integration | Cross-Cutting Analysis | +12.5% | 1 |
| memory_bounds_enforcement | Memory Management & Bounded Resources | +6.2% | 1 |
| async_runtime_integration | Async Runtime Integration | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 149s | 3438s |
| Avg time / task | 149s | 3438s |
| Input tokens (total) | 51 | ~72,000 (est.) |
| Output tokens (total) | 4,096 | ~13,500 (est.) |
| Est. cost (USD) | $0.0616 | ~$0.4185 (est.) |
| Avg iterations | 1 | 9.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.