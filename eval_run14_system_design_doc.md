# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:13:22 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| system_design_doc | system_design | 38.4% | 81.6% | +43.2% | 4 | 232s | 2224s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+43.2%** |
| Median lift | +43.2% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| memory_optimization_strategies | Memory & Resource Management | +68.8% | 1 |
| monitoring_alerting_capacity_planning | Operational Resilience & Production Engineering | +67.5% | 1 |
| partition_tolerance_design | Consistency Models & CAP Theorem Implications | +67.5% | 1 |
| crdt_mathematical_correctness | Algorithm Correctness & Mathematical Rigor | +66.2% | 1 |
| protocol_efficiency_optimization | Real-time Networking & Protocol Design | +65.0% | 1 |
| operational_architecture_integration | Cross-Cutting Coherence | +60.0% | 1 |
| operation_propagation_latency_design | Scalability Architecture & Performance | +52.5% | 1 |
| websocket_connection_management | Real-time Networking & Protocol Design | +51.2% | 1 |
| operation_log_storage_compaction | Persistence Layer & Data Management | +48.8% | 1 |
| database_design_high_write_throughput | Persistence Layer & Data Management | +37.5% | 1 |
| operational_transform_vs_crdt_justification | Algorithm Correctness & Mathematical Rigor | +35.0% | 1 |
| operational_resilience_failure_handling | Operational Resilience & Production Engineering | +33.3% | 1 |
| horizontal_scaling_architecture | Scalability Architecture & Performance | +31.2% | 1 |
| consistency_model_implementation | Consistency Models & CAP Theorem Implications | +25.0% | 1 |
| conflict_resolution_edge_cases | Conflict Resolution & Edge Case Handling | +25.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 232s | 2224s |
| Avg time / task | 232s | 2224s |
| Input tokens (total) | 47 | ~32,000 (est.) |
| Output tokens (total) | 4,096 | ~6,000 (est.) |
| Est. cost (USD) | $0.0616 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.