# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:05:58 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| exec_summary | summarization | 29.0% | 66.6% | +37.6% | 4 | 195s | 1839s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+37.6%** |
| Median lift | +37.6% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| investment_transparency | Resource Planning | +75.0% | 1 |
| contextual_business_environment | Strategic Context | +75.0% | 1 |
| contextual_feasibility_assessment | Strategic Realism | +75.0% | 1 |
| solution_specificity_authenticity | Content Authenticity | +75.0% | 1 |
| competitive_differentiation_specificity | Strategic Positioning | +75.0% | 1 |
| executive_communication_hierarchy | Executive Readiness | +67.5% | 1 |
| executive_decision_synthesis | Cross-cutting Coherence | +65.0% | 1 |
| balanced_risk_context | Executive Context | +62.5% | 1 |
| strategic_portfolio_logic | Strategic Coherence | +62.5% | 1 |
| competitive_impact_consistency | Cross-cutting Coherence | +60.0% | 1 |
| quantitative_credibility | Accuracy | +60.0% | 1 |
| strategic_substance_depth | Content Quality | +60.0% | 1 |
| decision_context_completeness | Strategic Value | +55.0% | 1 |
| critical_insight_prioritization | Completeness & Prioritization | +50.0% | 1 |
| strategic_technical_coherence | Cross-cutting Coherence | +50.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 195s | 1839s |
| Avg time / task | 195s | 1839s |
| Input tokens (total) | 28 | ~32,000 (est.) |
| Output tokens (total) | 128 | ~6,000 (est.) |
| Est. cost (USD) | $0.0020 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.