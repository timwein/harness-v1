# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:21:42 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| csv_parser | code_generation | 59.3% | 75.4% | +16.1% | 6 | 153s | 2777s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+16.1%** |
| Median lift | +16.1% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| data_lineage_audit_trail | Error Handling & Data Lineage | +66.2% | 1 |
| bom_encoding_handling | Cross-platform Compatibility | +65.0% | 1 |
| streaming_performance_optimization | Performance & Scalability | +48.8% | 1 |
| performance_vs_pandas | Performance Optimization | +47.5% | 1 |
| header_schema_inference | Header & Schema Inference | +23.8% | 1 |
| data_quality_statistical_validation | Data Integrity & Validation | +6.2% | 1 |
| defensive_programming_patterns | Code Architecture & Design Patterns | +6.0% | 1 |
| rfc4180_dialect_detection | RFC 4180 Compliance & Standards | +0.0% | 1 |
| malformed_data_recovery | Edge Case & Malformed Data Handling | +0.0% | 1 |
| production_error_handling | Error Handling & Data Lineage | +0.0% | 1 |
| mixed_delimiter_quoted_fields | Edge Case & Malformed Data Handling | -0.0% | 1 |
| rfc4180_field_consistency | RFC 4180 Compliance & Standards | -20.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 153s | 2777s |
| Avg time / task | 153s | 2777s |
| Input tokens (total) | 27 | ~48,000 (est.) |
| Output tokens (total) | 3,065 | ~9,000 (est.) |
| Est. cost (USD) | $0.0461 | ~$0.2790 (est.) |
| Avg iterations | 1 | 6.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.