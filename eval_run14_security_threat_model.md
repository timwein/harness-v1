# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:18:13 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| security_threat_model | security_analysis | 52.9% | 68.7% | +15.8% | 4 | 217s | 2568s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+15.8%** |
| Median lift | +15.8% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| mobile_platform_owasp_coverage | Mobile Platform Security | +45.0% | 1 |
| api_oauth_security_analysis | API and Third-Party Integration Security | +45.0% | 1 |
| api_rate_limiting_ddos_protection | API and Third-Party Integration Security | +45.0% | 1 |
| advanced_attack_scenarios | Advanced Threat Vectors | +40.0% | 1 |
| payment_infrastructure_tokenization | Payment Infrastructure Security | +27.5% | 1 |
| stride_threat_coverage_depth | STRIDE Methodology Application | +25.0% | 1 |
| biometric_liveness_detection_threats | Biometric Authentication Security | +25.0% | 1 |
| mobile_crypto_key_management | Mobile Platform Security | +25.0% | 1 |
| regulatory_compliance_threat_integration | Cross-Cutting Analysis | +25.0% | 1 |
| platform_payment_security_integration | Cross-Cutting Analysis | +25.0% | 1 |
| biometric_template_cryptographic_protection | Biometric Authentication Security | +25.0% | 1 |
| quantitative_risk_assessment_methodology | Risk Assessment and Prioritization | +20.0% | 1 |
| stride_regulatory_compliance_alignment | STRIDE Methodology Application | +0.0% | 1 |
| threat_intelligence_integration | Risk Assessment and Prioritization | +0.0% | 1 |
| fraud_detection_integration | Payment Infrastructure Security | -25.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 217s | 2568s |
| Avg time / task | 217s | 2568s |
| Input tokens (total) | 49 | ~32,000 (est.) |
| Output tokens (total) | 2,325 | ~6,000 (est.) |
| Est. cost (USD) | $0.0350 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.