# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:13:50 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| terraform_multi_env | infrastructure_as_code | 42.1% | 81.4% | +39.3% | 5 | 146s | 2427s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+39.3%** |
| Median lift | +39.3% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| vpc_endpoints_private_api | network_security | +100.0% | 1 |
| monitoring_security_integration | observability_security | +95.0% | 1 |
| iam_policy_composition | security_architecture | +70.0% | 1 |
| alb_security_integration | application_security | +56.2% | 1 |
| module_architecture_design | infrastructure_design | +40.0% | 1 |
| ecs_security_configuration | container_security | +26.2% | 1 |
| rds_security_hardening | database_security | +25.0% | 1 |
| workspace_configuration_strategy | environment_management | +23.7% | 1 |
| terraform_anti_patterns | infrastructure_reliability | +22.5% | 1 |
| resource_tagging_strategy | governance_compliance | +20.0% | 1 |
| role_based_credential_architecture | authentication_design | +3.7% | 1 |
| state_management_security | operational_security | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 146s | 2427s |
| Avg time / task | 146s | 2427s |
| Input tokens (total) | 56 | ~40,000 (est.) |
| Output tokens (total) | 4,096 | ~7,500 (est.) |
| Est. cost (USD) | $0.0616 | ~$0.2325 (est.) |
| Avg iterations | 1 | 5.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.