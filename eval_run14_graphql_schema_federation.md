# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:13:15 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| graphql_schema_federation | api_design | 48.7% | 78.5% | +29.9% | 4 | 194s | 2313s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+29.9%** |
| Median lift | +29.9% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| network_security_controls | Security Configuration | +85.0% | 1 |
| error_resilience_patterns | Error Handling & Resilience | +75.0% | 1 |
| security_resilience_integration | Cross-Cutting Integration | +75.0% | 1 |
| validation_error_handling | Schema Design Patterns | +58.8% | 1 |
| auth_performance_coherence | Cross-Cutting Integration | +37.5% | 1 |
| schema_composition_validity | Federation Specification Compliance | +33.3% | 1 |
| entity_key_stability | Entity Modeling & Design | +31.2% | 1 |
| auth_directive_implementation | Authorization & Security | +23.7% | 1 |
| dataloader_implementation | Performance Optimization | +22.5% | 1 |
| security_compliance | Authorization & Security | +20.0% | 1 |
| federation_directive_implementation | Federation Specification Compliance | +16.2% | 1 |
| domain_boundary_separation | Entity Modeling & Design | +12.5% | 1 |
| type_design_consistency | Schema Design Patterns | +0.0% | 1 |
| query_execution_efficiency | Query Composition & Planning | +0.0% | 1 |
| federation_domain_alignment | Cross-Cutting Integration | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 194s | 2313s |
| Avg time / task | 194s | 2313s |
| Input tokens (total) | 52 | ~32,000 (est.) |
| Output tokens (total) | 4,096 | ~6,000 (est.) |
| Est. cost (USD) | $0.0616 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.