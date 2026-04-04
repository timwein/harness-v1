# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:12:55 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| negotiation_playbook | business_strategy | 64.9% | 78.0% | +13.1% | 4 | 191s | 2336s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+13.1%** |
| Median lift | +13.1% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| shadow_it_prevention_controls | Procurement Governance | +75.0% | 1 |
| anchoring_market_intelligence | Anchoring & Price Discovery Tactics | +33.8% | 1 |
| contract_renewal_protection | Contract Risk Management | +25.0% | 1 |
| negotiation_stakeholder_execution | Negotiation Process & Execution | +20.0% | 1 |
| financial_tco_modeling | Financial Impact Modeling | +15.0% | 1 |
| batna_quantified_alternatives_analysis | BATNA Analysis & Alternatives Quantification | +8.8% | 1 |
| batna_margin_structure_alignment | BATNA Analysis & Alternatives Quantification | +8.7% | 1 |
| vendor_objection_enterprise_responses | Vendor Objection Response Framework | +0.0% | 1 |
| risk_mitigation_contract_protection | Risk Mitigation & Contract Protection | +0.0% | 1 |
| compliance_sox_governance | Compliance & Governance Alignment | -6.0% | 1 |
| saas_concession_levers | SaaS-Specific Concession Strategy | -8.7% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 191s | 2336s |
| Avg time / task | 191s | 2336s |
| Input tokens (total) | 51 | ~32,000 (est.) |
| Output tokens (total) | 2,811 | ~6,000 (est.) |
| Est. cost (USD) | $0.0423 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.