# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:35:55 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| board_deck_narrative | business_communication | 23.0% | 27.9% | +4.9% | 4 | 212s | 3658s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+4.9%** |
| Median lift | +4.9% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| rule_of_40_compliance_depth | Unit Economics & SaaS Metrics | +58.7% | 1 |
| arr_growth_trajectory_modeling | Financial Projections & ARR Trajectory | +51.2% | 1 |
| product_roadmap_alignment | Product Roadmap & Market Expansion | +42.5% | 1 |
| competitive_risk_product_alignment | Cross-Cutting Coherence | +41.2% | 1 |
| valuation_metrics_justification | Cross-Cutting Coherence | +18.8% | 1 |
| competitive_moat_durability | Competitive Positioning & Defensibility | +1.2% | 1 |
| revenue_quality_recognition | Financial Projections & ARR Trajectory | +0.0% | 1 |
| risk_assessment_mitigation | Risk Assessment & Mitigation | +0.0% | 1 |
| investment_thesis_narrative | Investment Thesis & Narrative Flow | +0.0% | 1 |
| financial_operational_coherence | Cross-Cutting Coherence | +0.0% | 1 |
| market_strategy_depth | Strategic Analysis | +0.0% | 1 |
| executive_communication_quality | Presentation Excellence | +0.0% | 1 |
| investment_sophistication | Investment Analysis | +0.0% | 1 |
| competitive_intelligence_depth | Strategic Analysis | +0.0% | 1 |
| organizational_scaling_execution | Operational Planning | +0.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 212s | 3658s |
| Avg time / task | 212s | 3658s |
| Input tokens (total) | 55 | ~32,000 (est.) |
| Output tokens (total) | 1,926 | ~6,000 (est.) |
| Est. cost (USD) | $0.0291 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.