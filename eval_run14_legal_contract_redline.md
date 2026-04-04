# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:17:08 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| legal_contract_redline | legal_analysis | 47.9% | 70.3% | +22.4% | 4 | 304s | 2454s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+22.4%** |
| Median lift | +22.4% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| comprehensive_dpa_evaluation | Data Privacy & Security Compliance | +61.3% | 1 |
| indemnification_scope_analysis | Liability & Indemnification Framework | +40.0% | 1 |
| security_audit_rights_adequacy | Risk Identification Accuracy | +37.5% | 1 |
| justification_quality_analysis | Contract Language Precision | +32.5% | 1 |
| commercial_legal_balance | Cross-cutting Analysis | +28.8% | 1 |
| sla_performance_framework | Service Level & Performance Governance | +21.2% | 1 |
| business_continuity_impact | Business Impact Analysis | +12.5% | 1 |
| termination_data_portability | Termination & Data Rights | +10.0% | 1 |
| vendor_security_accountability_mechanisms | Security and Compliance | +10.0% | 1 |
| risk_remediation_coherence | Cross-cutting Analysis | +8.7% | 1 |
| liability_limitation_risk_analysis | Risk Identification Accuracy | -2.0% | 1 |
| pricing_escalation_and_fee_clarity | Commercial Terms | -8.7% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 304s | 2454s |
| Avg time / task | 304s | 2454s |
| Input tokens (total) | 42 | ~32,000 (est.) |
| Output tokens (total) | 1,490 | ~6,000 (est.) |
| Est. cost (USD) | $0.0225 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.