# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:13:49 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| regulatory_gap_analysis | compliance | 61.7% | 75.9% | +14.2% | 4 | 191s | 2344s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+14.2%** |
| Median lift | +14.2% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| cloud_architecture_security_assessment | SaaS Architecture and Integration Controls | +67.5% | 1 |
| cuec_identification_documentation | Complementary User Entity Controls Documentation | +41.2% | 1 |
| tsc_poc_granular_mapping | Trust Services Criteria Mapping Accuracy | +25.0% | 1 |
| control_design_effectiveness_assessment | Control Design and Implementation Assessment | +17.5% | 1 |
| evidence_collection_strategy | Audit Preparation and Evidence Strategy | +8.8% | 1 |
| tsc_criteria_remediation_implementation_integration | Cross-Cutting Analysis | +8.7% | 1 |
| risk_severity_remediation_sequencing | Remediation Prioritization and Resource Allocation | +3.8% | 1 |
| saas_specific_control_alignment | Trust Services Criteria Mapping Accuracy | +0.0% | 1 |
| multi_tenancy_data_isolation_controls | SaaS Architecture and Integration Controls | +0.0% | 1 |
| startup_appropriate_control_scaling | Remediation Prioritization and Resource Allocation | +0.0% | 1 |
| control_gap_remediation_coherence | Cross-Cutting Analysis | +0.0% | 1 |
| startup_scale_audit_requirement_balance | Cross-Cutting Analysis | +0.0% | 1 |
| control_implementation_complexity_assessment | Timeline Feasibility and Type II Readiness | -10.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 191s | 2344s |
| Avg time / task | 191s | 2344s |
| Input tokens (total) | 54 | ~32,000 (est.) |
| Output tokens (total) | 2,941 | ~6,000 (est.) |
| Est. cost (USD) | $0.0443 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.