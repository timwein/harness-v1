# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 20:53:26 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| investment_memo | investment_memo | 6.9% | 32.3% | +25.3% | 4 | 400s | 7779s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+25.3%** |
| Median lift | +25.3% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| dual_use_revenue_strategy | Dual-Use Commercial Strategy | +100.0% | 1 |
| itar_compliance_cost_modeling | Defense Regulatory & Compliance Framework | +93.8% | 1 |
| security_clearance_scaling_analysis | Defense Regulatory & Compliance Framework | +92.5% | 1 |
| defense_financial_modeling_realism | Defense-Specific Financial Modeling | +92.5% | 1 |
| policy_geopolitical_risk_analysis | Policy & Geopolitical Risk Analysis | +92.5% | 1 |
| manufacturing_excellence_capability | Operational Capabilities | +90.0% | 1 |
| procurement_cycle_pathway_analysis | DOD Procurement & Sales Strategy | +85.0% | 1 |
| defense_partnership_ecosystem_strategy | Defense Partnership & Integration Strategy | +85.0% | 1 |
| defense_market_program_validation | Defense Program-Specific Market Analysis | +75.0% | 1 |
| technical_feasibility_risk_assessment | Technical Risk Analysis | +65.0% | 1 |
| technical_differentiation_incumbents | Technical Differentiation & Competitive Moats | +16.7% | 1 |
| defense_team_credentials_assessment | Defense-Qualified Team Assessment | +0.0% | 1 |
| corporate_venture_strategy | Strategic Partnerships | +0.0% | 1 |
| investor_credibility_strategy | Investment Structure | +0.0% | 1 |
| defense_unit_economics_modeling | Financial Analysis | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 400s | 7779s |
| Avg time / task | 400s | 7779s |
| Input tokens (total) | 27 | ~32,000 (est.) |
| Output tokens (total) | 786 | ~6,000 (est.) |
| Est. cost (USD) | $0.0119 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.